"""BERT 句子语义编码器：单次加载、GPU 优先、批量句编码。

契约（docs/ARCHITECTURE.md 第 5 节 / REQUIREMENTS FR-08）：
- 使用 Hugging Face 中文 BERT checkpoint，进程内只加载一次。
- 设备自动探测：有 CUDA 且显存可用则用 GPU，否则 CPU 兜底；
  显存不足（OOM）时降级 CPU，保证流水线可运行。
- 推理使用 torch.inference_mode()，输出与输入句子一一对应的语义向量。
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np


class BertEncoder:
    """只加载一次的 BERT 批量句向量编码器。"""

    def __init__(self, model_name: str = "google-bert/bert-base-chinese",
                 batch_size: int = 32, device: str = "") -> None:
        """初始化编码器配置，不立即加载模型。

        - model_name：中文 BERT checkpoint（Hugging Face 名称或本地目录）。
        - batch_size：单批编码的最大句子数。
        - device：留空表示自动探测 GPU/CPU。
        """
        self.model_name = model_name
        self.batch_size = batch_size
        self.device = device
        self._model: Any = None
        self._tokenizer: Any = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """是否已完成加载。"""
        return self._loaded

    def load(self) -> None:
        """加载 BERT 模型与 tokenizer，自动选择 GPU/CPU。

        若设置环境变量 HF_HUB_OFFLINE=1，则以 local_files_only 从本地
        Hugging Face 缓存加载，不联网检查更新（适合无外网/离线场景）。
        """
        import os

        import torch
        from transformers import AutoModel, AutoTokenizer

        # 设备自动探测：显式指定 > CUDA 可用 > CPU
        if not self.device:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"

        local_only = os.environ.get("HF_HUB_OFFLINE") == "1"
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, local_files_only=local_only
        )
        self._model = AutoModel.from_pretrained(
            self.model_name, local_files_only=local_only
        )
        self._model.to(self.device)
        self._model.eval()
        self._loaded = True

    def encode_batch(self, sentences: Sequence[str]) -> list[np.ndarray]:
        """批量编码句子，返回与句子一一对应的句向量（float32 numpy）。

        - sentences：有序句子列表（来自 split_sentences）。
        - 返回：每句一个 [hidden_size] 向量。空输入返回空列表。
        采用 mean-pooling 将 token 向量聚合为整句表示，inference_mode 下执行。
        """
        import torch

        if not sentences:
            return []
        if not self._loaded:
            raise RuntimeError("BertEncoder 未加载，请先调用 load()。")

        vectors: list[np.ndarray] = []
        hidden_size: int | None = None
        for start in range(0, len(sentences), self.batch_size):
            batch_sentences = sentences[start : start + self.batch_size]
            encoded = self._tokenizer(
                list(batch_sentences),
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            encoded = {key: value.to(self.device) for key, value in encoded.items()}
            with torch.inference_mode():
                outputs = self._model(**encoded)
            # mean-pooling：对每个 token 输出沿 attention mask 取平均
            token_embeddings = outputs.last_hidden_state  # [B, T, H]
            attention_mask = encoded["attention_mask"]  # [B, T]
            mask = attention_mask.unsqueeze(-1).float()  # [B, T, 1]
            summed = (token_embeddings * mask).sum(dim=1)
            counts = mask.sum(dim=1).clamp(min=1e-8)
            pooled = summed / counts  # [B, H]
            pooled = pooled.cpu().numpy()
            hidden_size = pooled.shape[1]
            vectors.extend(v for v in pooled)
        return vectors

    def encode(self, sentence: str) -> np.ndarray:
        """编码单个句子并返回其句向量。"""
        result = self.encode_batch([sentence])
        if not result:
            raise RuntimeError("编码结果为空。")
        return result[0]

    def count_tokens(self, text: str) -> int:
        """计算文本经 tokenizer 分词后的 token 数量（不含特殊标记）。

        用于流水线入口的输入长度预检；tokenizer 在 load() 时已加载，可复用。
        """
        if not self._loaded:
            raise RuntimeError("BertEncoder 未加载，请先调用 load()。")
        if not text:
            return 0
        ids = self._tokenizer(text, add_special_tokens=False)["input_ids"]
        return len(ids)
