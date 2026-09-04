# 系统架构冻结

```text
真实新闻源 → Crawler(D) → NewsService(D) → MySQL
                                           ↓
HarmonyOS(E) ← FastAPI Route ← Service ← Worker(D) ← SummaryPipeline(C)
                                           ↓              ↓
                                  收藏/反馈/指标(A)   BERT→TextRank→Transformer
                                                          ↑
                                             CNewSum 训练/评价/基准(B)
```

## 模块边界

- API 仅解析 HTTP、返回统一 `ApiResponse`，不直接操作数据库、Tokenizer、BERT、TextRank 或 `model.generate`。
- Service 承担业务规则并通过 SQLAlchemy 访问 MySQL；`SummaryService` 是业务层到 `SummaryPipeline` 的唯一桥梁。
- `NewsSource.fetch_articles()` 仅返回 `RawArticle`；来源实现不得生成虚构新闻。
- `SummaryPipeline.generate(article)` 是在线 AI 的唯一公开业务接口，内部顺序固定为清洗、分句、BERT、TextRank、Token Budget 与 Transformer。
- HarmonyOS 只经 `HttpClient` 调用 FastAPI，不能访问 MySQL 或 Python AI。

## 数据流与状态

Crawler 写入 `news_articles` 时摘要状态为 `pending`。Worker 原子取得任务后更新为 `processing`；成功保存摘要、耗时、模型版本并更新为 `completed`，失败记录原因并更新为 `failed`。摘要请求对 `completed` 返回缓存结果，对 `processing` 返回当前状态，对 `pending` 与 `failed` 允许开始或重试，并防止同一新闻并发生成。

模型训练是离线流程，B 只写 `runtime/models/news_summarizer/` 和评价记录；在线后端只读取正式模型。数据库、路由、AI、采集和客户端的所有冻结字段见相应文档。
