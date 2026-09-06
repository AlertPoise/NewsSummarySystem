"""在线 Seq2Seq Transformer 推理接口：加载 B 的正式模型并生成最终摘要。

B → C 契约（docs/ARCHITECTURE.md 第 4/5 节）：
- 唯一正式模型目录 `runtime/models/news_summarizer/`，内含可由 Hugging Face
  直接加载的模型与 Tokenizer，以及唯一正式元信息 `model_metadata.json`。
- C 只读该目录，参数（max_input_tokens/max_new_tokens/generation_config）以
  元信息 JSON 为准，不得自行改写或猜测。
- 正式模型尚未交付时，加载抛明确可定位的"AI 不可用"异常，绝不伪造摘要。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class AiUnavailableError(RuntimeError):
    """正式 AI 组件缺失或不可用（对应 API 错误码 1004 / HTTP 503）。"""


class TransformerSummarizer:
    """加载正式摘要模型并生成最终摘要的封装。"""

    def __init__(self, model_dir: str | Path) -> None:
        """初始化只读模型目录，不立即加载。

        - model_dir：B 交付的 `runtime/models/news_summarizer` 目录。
        """
        self.model_dir = Path(model_dir)
        self.model_version = ""
        self.device = "cpu"
        self._tokenizer: Any = None
        self._model: Any = None
        self._metadata: dict[str, Any] = {}
        self._loaded = False

    @property
    def metadata(self) -> dict[str, Any]:
        """返回已解析的正式模型元信息；未加载时为空字典。"""
        return self._metadata

    @property
    def is_loaded(self) -> bool:
        """是否已完成加载。"""
        return self._loaded

    def load(self) -> None:
        """读取正式元信息并加载模型与 tokenizer；缺正式模型则抛 AiUnavailableError。"""
        metadata_path = self.model_dir / "model_metadata.json"
        if not metadata_path.exists():
            raise AiUnavailableError(
                f"正式模型元信息不存在：{metadata_path}。"
                "等待 B 交付 runtime/models/news_summarizer/model_metadata.json 后重试。"
            )
        with metadata_path.open("r", encoding="utf-8") as fh:
            self._metadata = json.load(fh)

        # 元信息必要字段校验（缺失即视为交付不完整，不猜测默认值）
        required = ["model_name", "model_version", "dataset", "max_input_tokens", "max_new_tokens"]
        missing = [key for key in required if key not in self._metadata]
        if missing:
            raise AiUnavailableError(
                f"正式模型元信息缺少必要字段：{missing}。请 B 按 ARCHITECTURE 契约补齐。"
            )
        self.model_version = self._metadata["model_version"]

        # 权重文件校验（存在任一格式即可）
        has_weights = any(
            (self.model_dir / name).exists()
            for name in ("pytorch_model.bin", "model.safetensors", "tf_model.h5")
        )
        if not has_weights:
            raise AiUnavailableError(
                f"正式模型权重不存在于 {self.model_dir}。等待 B 交付模型文件后重试。"
            )

        self._load_transformers()

    def _load_transformers(self) -> None:
        """使用 Hugging Face Transformers 加载 Seq2Seq 模型与 tokenizer。

        模型自动放置到 CUDA GPU（可用时），与 BertEncoder 的设备策略一致；
        无 GPU 则退回 CPU。
        """
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir))
        self._model = AutoModelForSeq2SeqLM.from_pretrained(str(self.model_dir))
        self._model.to(self.device)
        self._model.eval()
        self._loaded = True

    def generate(self, selected_text: str) -> str:
        """以 Token Budget 选取的文本为输入，生成最终摘要字符串。

        前提：已调用 load() 完成加载；未加载则抛 AiUnavailableError。
        生成参数以正式元信息为准（generation_config / max_new_tokens），
        不使用自定义生成参数猜测。
        """
        if not self._loaded:
            raise AiUnavailableError("TransformerSummarizer 未加载，请先调用 load()。")
        metadata = self._metadata
        max_input_tokens = int(metadata["max_input_tokens"])
        max_new_tokens = int(metadata["max_new_tokens"])
        generation_config: dict[str, Any] = metadata.get("generation_config") or {}

        # 禁止静默截断：tokenize 不做 truncation，若实际超出正式输入上限则显式失败
        inputs = self._tokenizer(
            selected_text,
            add_special_tokens=True,
            truncation=False,
            return_tensors="pt",
        )
        if inputs["input_ids"].shape[-1] > max_input_tokens:
            raise AiUnavailableError(
                f"送入 Transformer 的文本超长：{inputs['input_ids'].shape[-1]} token，"
                f"超过正式最大输入 {max_input_tokens} token（禁止静默截断）。"
            )
        inputs = {key: value.to(self._model.device) for key, value in inputs.items()}
        import torch

        with torch.inference_mode():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                **generation_config,
            )
        summary = self._tokenizer.decode(output_ids[0], skip_special_tokens=True)
        return summary.strip()

    def count_tokens(self, text: str) -> int:
        """用正式摘要模型 tokenizer 对文本做未截断计数（含特殊标记）。

        用于 Pipeline 输入长度预检：与正式模型 max_input_tokens 同源，
        保证"<=512 允许、>512 拒绝"判定口径与模型一致。
        """
        if not self._loaded:
            raise AiUnavailableError("TransformerSummarizer 未加载，请先调用 load()。")
        if not text:
            return 0
        encoded = self._tokenizer(
            text,
            add_special_tokens=True,
            truncation=False,
        )
        return len(encoded["input_ids"])
