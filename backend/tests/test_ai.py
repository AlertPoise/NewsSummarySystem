"""AI 模块测试骨架。"""


def test_ai_contract_is_frozen() -> None:
    """验证摘要结果字段和流水线方法已冻结。"""
    from app.ai.pipeline import SummaryPipeline, SummaryResult

    result = SummaryResult(summary="", generation_time_ms=0, model_version="")
    assert result.summary == ""
    assert callable(SummaryPipeline.load)
    assert callable(SummaryPipeline.generate)


# TODO(C-阶段2)：补充文本清洗、中文分句、BERT、TextRank、Token Budget、异常处理与真实流水线单元测试；输入为 CNewSum 代表性样本，输出为可重复的 AI 验证结果，必须遵守 docs/ARCHITECTURE.md 与 docs/REQUIREMENTS.md。
