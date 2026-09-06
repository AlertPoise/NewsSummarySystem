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

from app.ai.pipeline import InputTooLongError, SummaryPipeline, SummaryResult
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


class TestInputLengthLimit:
    """超长输入（超过 max_input_tokens）的拒绝行为。"""

    def _make_pipeline(
        self, monkeypatch: pytest.MonkeyPatch, fake_tokens: int
    ) -> SummaryPipeline:
        """构造已 load 的 Pipeline：BERT 桩提供 token 计数，Transformer 桩可生成。"""
        import numpy as np

        class FakeBert:
            def __init__(self, **kwargs: object) -> None:
                self.is_loaded = True

            def load(self) -> None:
                self.is_loaded = True

            def count_tokens(self, text: str) -> int:
                return fake_tokens

            def encode_batch(self, sentences: list[str]) -> list[object]:
                return [np.zeros(4) for _ in sentences]

        class FakeSummarizer:
            model_version = "test-v0"
            metadata = {
                "model_name": "dummy",
                "model_version": "test-v0",
                "dataset": "CNewSum",
                "max_input_tokens": 512,
                "max_new_tokens": 60,
            }

            def __init__(self, model_dir: object) -> None:
                pass

            def load(self) -> None:
                pass

            def count_tokens(self, text: str) -> int:
                # Pipeline 现在用 summarizer 的 tokenizer 计数长度
                return fake_tokens

            def generate(self, text: str) -> str:
                return "生成的摘要。"

        monkeypatch.setattr("app.ai.pipeline.BertEncoder", FakeBert)
        monkeypatch.setattr("app.ai.pipeline.TransformerSummarizer", FakeSummarizer)
        pipeline = SummaryPipeline(max_input_tokens=512)
        pipeline.load()
        return pipeline

    def test_overlong_input_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """超过 max_input_tokens 的输入抛 InputTooLongError，不生成摘要。"""
        pipeline = self._make_pipeline(monkeypatch, fake_tokens=800)
        with pytest.raises(InputTooLongError):
            pipeline.generate("这是一篇很长的新闻。")

    def test_normal_length_input_passes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """未超过上限的输入正常生成摘要。"""
        pipeline = self._make_pipeline(monkeypatch, fake_tokens=100)
        result = pipeline.generate("这是一篇正常长度的新闻。")
        assert result.summary == "生成的摘要。"
        assert result.generation_time_ms >= 0


class TestFactualGate:
    """硬事实校验门：摘要含源文不存在的硬事实时拒绝交付。"""

    def _make_pipeline(
        self, monkeypatch: pytest.MonkeyPatch, fake_tokens: int, fake_summary: str
    ) -> SummaryPipeline:
        """构造已 load 的 Pipeline：BERT 桩 + 定制摘要的 Transformer 桩。"""
        import numpy as np

        class FakeBert:
            def __init__(self, **kwargs: object) -> None:
                self.is_loaded = True

            def load(self) -> None:
                self.is_loaded = True

            def count_tokens(self, text: str) -> int:
                return fake_tokens

            def encode_batch(self, sentences: list[str]) -> list[object]:
                return [np.zeros(4) for _ in sentences]

        class FakeSummarizer:
            model_version = "test-v0"
            metadata = {
                "model_name": "dummy",
                "model_version": "test-v0",
                "dataset": "CNewSum",
                "max_input_tokens": 512,
                "max_new_tokens": 60,
            }

            def __init__(self, model_dir: object) -> None:
                pass

            def load(self) -> None:
                pass

            def count_tokens(self, text: str) -> int:
                return len(text)

            def generate(self, text: str) -> str:
                return fake_summary

        monkeypatch.setattr("app.ai.pipeline.BertEncoder", FakeBert)
        monkeypatch.setattr("app.ai.pipeline.TransformerSummarizer", FakeSummarizer)
        pipeline = SummaryPipeline(max_input_tokens=512)
        pipeline.load()
        return pipeline

    def test_hallucinated_time_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """摘要含源文不存在的"上半年"应被拒绝交付。"""
        pipeline = self._make_pipeline(monkeypatch, fake_tokens=50, fake_summary="上半年经济增长4.5%。")
        news = "8月份经济数据发布，增长4.5%。"
        with pytest.raises(AiUnavailableError) as exc:
            pipeline.generate(news)
        assert "硬事实校验未通过" in str(exc.value)

    def test_consistent_summary_passes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """摘要硬事实与源文一致时正常返回。"""
        pipeline = self._make_pipeline(monkeypatch, fake_tokens=50, fake_summary="8月经济增长4.5%。")
        news = "8月份经济数据发布，增长4.5%。"
        result = pipeline.generate(news)
        assert result.summary == "8月经济增长4.5%。"
