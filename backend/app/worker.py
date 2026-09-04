"""新闻摘要后台任务骨架。"""


def run_worker() -> None:
    """运行待摘要新闻的后台处理循环。"""
    # TODO(D-阶段3)：实现 pending→processing→SummaryPipeline.generate(article)→completed 状态机；输入为待处理 NewsArticle 和 C 的 SummaryPipeline，输出为摘要、耗时、模型版本或失败原因，必须遵守 docs/DATABASE.md 与 docs/AI_PIPELINE.md。
    raise NotImplementedError("阶段3由D实现摘要后台任务")


if __name__ == "__main__":
    run_worker()
