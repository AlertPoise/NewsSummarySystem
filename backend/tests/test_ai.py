"""AI 模块契约、错误路径与流水线异常测试。

- 契约测试：SummaryResult 字段与 SummaryPipeline 方法已冻结，不可改动。
- 错误路径：用临时目录制造"缺元信息/缺权重"场景，验证 C 侧在 B 未交付时
  抛 AiUnavailableError（对应 API 1004 / 503），而不是返回伪造摘要。
- 本文件不下载模型、不联网；真正需要 BERT/Transformer 的集成测试在
  tests/test_ai_integration.py（@pytest.mark.slow，单独运行）。
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ai.pipeline import SummaryPipeline, SummaryResult
from app.ai.summarizer import AiUnavailableError, TransformerSummarizer


class TestFrozenContract:
    """公共接口冻结契约（禁止修改，见 ARCHITECTURE 第 5 节）。"""

    def test_summaryresult_fields_frozen(self) -> None:
        """SummaryResult 固定包含 summary/generation_time_ms/model_version。"""
        result = SummaryResult(summary="测试摘要", generation_time_ms=12, model_version="v0")
        assert result.summary == "测试摘要"
        assert result.generation_time_ms == 12
        assert result.model_version == "v0"
        assert callable(SummaryPipeline.load)
        assert callable(SummaryPipeline.generate)


class TestAiUnavailable:
    """正式组件缺失时的错误行为。"""

    def test_summarizer_missing_metadata(self, tmp_path: Path) -> None:
        """缺少 model_metadata.json 时抛 AiUnavailableError。"""
        summarizer = TransformerSummarizer(model_dir=tmp_path)
        with pytest.raises(AiUnavailableError):
            summarizer.load()

    def test_summarizer_metadata_missing_fields(self, tmp_path: Path) -> None:
        """元信息缺少必要字段时抛 AiUnavailableError。"""
        (tmp_path / "model_metadata.json").write_text(
            json.dumps({"model_name": "x"}), encoding="utf-8"
        )
        summarizer = TransformerSummarizer(model_dir=tmp_path)
        with pytest.raises(AiUnavailableError):
            summarizer.load()

    def test_summarizer_metadata_but_no_weights(self, tmp_path: Path) -> None:
        """元信息存在但权重缺失时抛 AiUnavailableError。"""
        (tmp_path / "model_metadata.json").write_text(
            json.dumps(
                {
                    "model_name": "dummy",
                    "model_version": "v0",
                    "dataset": "CNewSum",
                    "max_input_tokens": 512,
                    "max_new_tokens": 128,
                    "tokenizer": {"name_or_path": "dummy"},
                }
            ),
            encoding="utf-8",
        )
        summarizer = TransformerSummarizer(model_dir=tmp_path)
        with pytest.raises(AiUnavailableError):
            summarizer.load()

    def test_summarizer_generate_before_load(self, tmp_path: Path) -> None:
        """未加载时 generate 抛 AiUnavailableError。"""
        summarizer = TransformerSummarizer(model_dir=tmp_path)
        with pytest.raises(AiUnavailableError):
            summarizer.generate("测试正文")

    def test_pipeline_generate_before_load(self) -> None:
        """未 load() 的 Pipeline.generate 抛 AiUnavailableError（而非假摘要）。"""
        pipeline = SummaryPipeline()
        with pytest.raises(AiUnavailableError):
            pipeline.generate("测试新闻正文。包含句子。")

    def test_pipeline_load_missing_formal_model_is_ai_unavailable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """正式 Transformer 未交付时 load() 报告 AI 不可用，不静默降级。

        BERT 用桩隔离；正式模型目录不存在时，load() 应在 BERT 加载后、
        到达 TransformerSummarizer 加载步骤时抛 AiUnavailableError。
        """
        # 桩 BERT：仅验证 encode 可用，避免真实下载 checkpoint
        class FakeBert:
            def __init__(self, **kwargs: object) -> None:
                self.is_loaded = False

            def load(self) -> None:
                self.is_loaded = True

            def encode_batch(self, sentences: list[str]) -> list[object]:
                import numpy as np

                return [np.zeros(4) for _ in sentences]

        monkeypatch.setattr("app.ai.pipeline.BertEncoder", FakeBert)
        model_dir = tmp_path / "no_formal_model"
        pipeline = SummaryPipeline(model_dir=str(model_dir))
        with pytest.raises(AiUnavailableError):
            pipeline.load()
