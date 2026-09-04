# 六阶段开发计划与人员分工

## 人员分工

| 人员 | 固定责任 | 主要目录 |
|---|---|---|
| A | 架构、MySQL、FastAPI 公共层、收藏、反馈、模型指标、Windows、集成、文档 | `docs/`、`backend/app` 公共层、`sql/`、`scripts/` |
| B | CNewSum、离线 Seq2Seq 训练、权重、ROUGE、性能基准 | `model_training/`、`runtime/datasets/`、`runtime/models/` |
| C | 预处理、BERT、TextRank、Token Budget、在线 Transformer、流水线和 AI 测试 | `backend/app/ai/` |
| D | 两个新闻源、正文提取、映射、去重、新闻业务、Worker、新闻 API | `backend/app/crawlers/`、新闻和摘要服务/API、`worker.py` |
| E | 完整 HarmonyOS 客户端 | `frontend_harmony/` |

## 阶段 1：需求冻结、架构、MySQL、接口、工程初始化

主负责人 A。完成工程目录、REQUIREMENTS、ARCHITECTURE、DEVELOPMENT_PLAN、API、DATABASE、AI_PIPELINE、TEST_PLAN、WINDOWS_SETUP、AI_PROMPTS、MySQL 配置、SQLAlchemy 模型、`.env.example`、FastAPI 初始化、`GET /api/health`、全部模块骨架和 TODO。阶段结束后冻结数据库字段、API 地址和 JSON 字段、`SummaryPipeline`、`RawArticle` 及目录结构。

## 阶段 2：CNewSum、Transformer、BERT、TextRank、模型评价

B 真实处理 CNewSum，训练唯一 Seq2Seq Transformer，完成 ROUGE 与 Benchmark。C 实现 BERT、TextRank、在线 Transformer 和 SummaryPipeline。验收真实 CNewSum、ROUGE-L ≥ 0.40、单篇摘要少于 1.5 秒，并将指标写入 `model_evaluations`。

## 阶段 3：新闻采集、新闻业务、Worker、FastAPI

D 实现两个真实新闻源、正文提取、清洗、分类映射、SHA-256 去重、入库、Worker、新闻列表/详情/手动摘要 API。A 并行完成收藏、反馈、模型指标 API 和数据库公共功能。

## 阶段 4：HarmonyOS 完整客户端

E 实现 Client ID、首页分类、新闻列表、分页、刷新、详情、摘要、全文、收藏列表、反馈、模型信息、网络异常、加载与空数据状态。

## 阶段 5：完整端到端联调

A 主导，全员参加。真实跑通“新闻网站→Crawler→清洗→MySQL→Worker→BERT→TextRank→Transformer→MySQL 摘要→FastAPI→HarmonyOS”，同时联调收藏、反馈、模型评价。所有 Mock 在此阶段删除。

## 阶段 6：测试、性能优化、文档、视频、最终提交

A 负责 Windows、数据库、集成、README、打包；B 负责 CNewSum、训练说明、ROUGE、性能；C 负责 AI 测试和 AI 文档；D 负责 Crawler、Worker、新闻 API 测试；E 负责 HarmonyOS 测试、截图和演示视频；全员完成实践文档、AI 提示词与答辩材料。
