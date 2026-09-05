"""AI 模块慢速集成测试：真实下载 BERT 并验证句向量编码。

- 使用 @pytest.mark.slow 标记，默认被 pytest.ini 排除。
- 运行方式：.venv/Scripts/python.exe -m pytest backend/tests/test_ai_integration.py -m slow -v
- BERT 使用 google-bert/bert-base-chinese，优先命中本机 HF 缓存
  （~/.cache/huggingface），未命中时才联网下载。
- 正式摘要模型未交付时不在此测试（对应错误路径已在 test_ai.py 覆盖）。
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.bert_encoder import BertEncoder


@pytest.mark.slow
class TestBertEncoderReal:
    """真实 BERT 句编码集成测试。"""

    def test_encodes_sentences_one_vector_each(self) -> None:
        """真实 BERT 为每个句子返回一个向量，数量与句子对应。"""
        encoder = BertEncoder(model_name="google-bert/bert-base-chinese")
        encoder.load()
        try:
            # 前两句同为天气话题，后两句为无关话题（财报/比赛）
            sentences = [
                "今天天气晴朗阳光明媚。",
                "明天天气转凉要多穿衣服。",
                "公司发布了新的财报数据。",
                "球队赢得了今晚的比赛。",
            ]
            vectors = encoder.encode_batch(sentences)
            assert len(vectors) == len(sentences)
            # BERT-base 隐藏维度为 768
            assert vectors[0].shape == (768,)
            assert vectors[0].dtype == np.float32
            # 同主题句对的相似度应显著高于跨主题句对
            same_topic = _cosine(vectors[0], vectors[1])
            cross_topic = max(_cosine(vectors[0], vectors[2]), _cosine(vectors[0], vectors[3]))
            assert same_topic > cross_topic
        finally:
            # 显式释放，便于同一进程内多次测试
            del encoder

    def test_single_encode(self) -> None:
        """单句编码返回一个有效向量。"""
        encoder = BertEncoder(model_name="google-bert/bert-base-chinese")
        encoder.load()
        try:
            vector = encoder.encode("这是一条测试句子。")
            assert vector.shape == (768,)
            assert float(np.linalg.norm(vector)) > 0
        finally:
            del encoder


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """计算两个向量的余弦相似度。"""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
