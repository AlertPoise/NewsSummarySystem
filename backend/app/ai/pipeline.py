"""唯一对业务层暴露的在线摘要流水线接口。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SummaryResult:
    """一次真实摘要生成的标准结果。"""

    summary: str
    generation_time_ms: int
    model_version: str


class SummaryPipeline:
    """串联预处理、BERT、TextRank、Token Budget 与摘要模型。"""

    def load(self) -> None:
        """加载并预热正式在线摘要组件。"""
        # TODO(C-阶段2)：按清洗、分句、BERT、TextRank、Token Budget、Transformer 顺序加载和预热组件；输入为 config.py 已冻结配置，输出为可复用的已加载流水线，必须遵守 docs/ARCHITECTURE.md。
        raise NotImplementedError("阶段2由C加载正式摘要流水线")

    def generate(self, article: str) -> SummaryResult:
        """为一篇新闻正文生成真实摘要结果。"""
        # TODO(C-阶段2)：实现全链路真实推理和从本方法开始的毫秒计时；输入为新闻正文 article，输出为 SummaryResult，必须遵守 docs/ARCHITECTURE.md、max_input_tokens 和唯一业务接口约束。
        raise NotImplementedError("阶段2由C生成真实摘要")
