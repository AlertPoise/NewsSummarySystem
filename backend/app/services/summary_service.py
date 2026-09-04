"""新闻摘要协调业务骨架。"""


class SummaryService:
    """协调新闻记录状态与 SummaryPipeline 调用。"""

    # TODO(D-阶段3)：实现单新闻摘要状态机和并发互斥；输入为 SQLAlchemy Session、news_id 和 C 的 SummaryPipeline，输出为 completed、processing、pending 或 failed 状态及摘要结果，必须仅调用 SummaryPipeline.generate(article) 并遵守 docs/API.md。
    pass
