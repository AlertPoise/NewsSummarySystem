# 终版需求冻结

## 项目与边界

项目名称为《基于自然语言处理的新闻文章自动摘要系统设计与实现》，工程根目录为 `NewsSummarySystem`。运行环境固定为 Windows 10/11 x64、Python 3.11、FastAPI、SQLAlchemy 2.x、PyMySQL、MySQL 8.x、PyTorch、Hugging Face Transformers 与 HarmonyOS ArkTS/ArkUI。禁止 Redis、Kafka、Celery、Docker、Kubernetes、Elasticsearch、微服务、JWT、密码登录、在线训练及以大模型 API 代替正式模型。

## 既定最终功能

1. D 接入至少两个真实新闻来源，采集标题、正文、来源、原始 URL、发布时间和分类；清除 HTML、广告、导航及推荐噪声，映射为科技、财经、社会、体育、国内、国际六类，以正文 SHA-256 去重并写入 MySQL。
2. C 实现 `clean_text(text)` 和 `split_sentences(text)`，处理标准化、中文分句、空白、控制与异常字符及文本长度检查。
3. C 真实使用 Hugging Face BERT 批量编码新闻句子；模型只加载一次，支持 GPU 与推理模式。
4. C 以 BERT 句向量余弦相似度构图并真实运行 TextRank/PageRank；依据 Seq2Seq 的 `max_input_tokens` 选取关键句，再恢复原文顺序，不能固定句数。
5. B 使用 CNewSum、PyTorch 和 Transformers 完成真正的 Seq2Seq Transformer 微调，唯一正式权重保存于 `runtime/models/news_summarizer/`；后端不得在线训练。
6. 在线摘要必须为“正文→清洗→分句→BERT→TextRank→Token Budget→Seq2Seq→摘要”，业务层只调用 `SummaryPipeline.generate(article)`。
7. E 的 HarmonyOS 客户端实现分类新闻、刷新、分页、详情、收藏、反馈和真实模型指标展示；客户端 UUID 持久化为 `client_id` 并通过 `X-Client-ID` 请求用户状态。
8. 同一客户端对同一新闻只有一个收藏和一个当前反馈；反馈再次提交更新，用于后续离线分析和再训练，不能触发在线训练。
9. B 在 CNewSum test 计算 ROUGE-1、ROUGE-2、ROUGE-L，写入 `model_evaluations`；验收 ROUGE-L ≥ 0.40。预热后按 `SummaryPipeline.generate(article)` 计时，batch size=1，平均和 P95 写库，单篇低于 1.5 秒。

阶段 1 已冻结目录、数据库字段、API URL/JSON 字段、`RawArticle` 与 `SummaryPipeline` 接口。尚未实现业务必须使用负责人和阶段齐全的中文 TODO，不得伪造任何新闻、摘要、指标或已加载模型。
