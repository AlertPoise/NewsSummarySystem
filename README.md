# 基于自然语言处理的新闻文章自动摘要系统设计与实现

## 项目简介

NewsSummarySystem 是一个终版课程项目：HarmonyOS 客户端通过 FastAPI 访问新闻、收藏、反馈和模型指标；后端以 MySQL 持久化真实新闻及摘要任务；在线摘要固定使用 BERT 句子语义表示、TextRank 关键句排序、Token Budget 与 Seq2Seq Transformer。CNewSum 是唯一正式训练和评价数据集。

## 最终核心功能

- 两个真实新闻来源的采集、正文提取、网页噪声清理、六类分类映射、SHA-256 去重和 MySQL 持久化。
- 新闻分类展示、分页、刷新、详情、全文、AI 摘要、收藏、摘要反馈与模型信息展示。
- 完整正式摘要路径：清洗、中文分句、BERT、余弦相似度、TextRank/PageRank、Token Budget、原文顺序恢复、Seq2Seq Transformer。
- CNewSum test 的 ROUGE-1、ROUGE-2、ROUGE-L 与完整流水线性能评价。

## 技术栈

| 层级 | 固定技术 |
|---|---|
| 客户端 | HarmonyOS、ArkTS、ArkUI、DevEco Studio |
| 后端 | Python 3.11、FastAPI、SQLAlchemy 2.x、PyMySQL |
| 数据库 | MySQL 8.x、utf8mb4 |
| AI | PyTorch、Hugging Face Transformers、BERT、TextRank、Seq2Seq Transformer |
| 数据集 | CNewSum |

## 总体数据流

`真实新闻网站 → Crawler[D] → NewsService[D] → MySQL → Worker[D] → SummaryPipeline[C] → MySQL → FastAPI[A/D] → HarmonyOS[E]`。B 在离线流程中训练并交付唯一正式摘要模型，详细边界见 [ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 五人职责概览

| 角色 | 终版责任 |
|---|---|
| A | 架构、数据库 Schema、FastAPI 公共规范、收藏、反馈、模型指标、集成与文档 |
| B | CNewSum、训练、模型交付、ROUGE、性能基准 |
| C | 文本预处理、BERT、TextRank、Token Budget、在线摘要流水线与 AI 测试 |
| D | 新闻源、网页处理、新闻业务、Worker、新闻 API 与摘要任务 |
| E | 完整 HarmonyOS 客户端 |

## 六阶段概览

阶段1冻结需求、架构、职责、数据库和接口；阶段2实现 CNewSum、正式模型与在线 AI；阶段3实现真实新闻业务、Worker 和后端业务 API；阶段4实现 HarmonyOS；阶段5端到端联调；阶段6测试、性能复核、实践文档、视频与提交。任务编号和验收见 [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)。

## 精简目录结构

```text
NewsSummarySystem/
├── README.md
├── docs/                         需求、架构、计划、API、数据库、AI记录
├── backend/                      已冻结的后端骨架
├── model_training/               已冻结的离线训练骨架
├── frontend_harmony/             阶段4正式客户端位置
├── sql/  scripts/                后续阶段使用的基础设施文件
└── runtime/                      数据集、模型、缓存、日志，均不提交 Git
```

## 文档阅读顺序

所有成员首先阅读本文件、[REQUIREMENTS.md](docs/REQUIREMENTS.md) 和 [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) 中自己的角色部分。涉及跨模块接口时阅读 [ARCHITECTURE.md](docs/ARCHITECTURE.md)；涉及 REST 时阅读 [API.md](docs/API.md)；涉及 MySQL 时阅读 [DATABASE.md](docs/DATABASE.md)；AI 使用记录写入 [AI_PROMPTS.md](docs/AI_PROMPTS.md)。

## Windows 基础开发环境

固定环境为 Windows 10/11 x64、Python 3.11、MySQL 8、DevEco Studio、PyTorch 与 Transformers。CUDA/GPU 的正式版本和安装命令由 B、C 在阶段2经真实训练与推理验证后填写。本阶段不要求运行任何数据库、后端或 Worker 初始化脚本。

## CNewSum 与模型目录

正式原始 CNewSum 目录固定为 `runtime/datasets/CNewSum_v2/final/`。已确认核心 split 为 train 275,596、dev 14,356、test 14,355，共 304,307；另有 test.anno、test2017、test2018。六个 JSONL 的行数和 322,662 不能视为互不重复样本数。B2-01 仍须真实核验编码、字段、ID、完整性及这些 test 文件的重叠/来源关系，数据集不得提交 Git。

`runtime/models/news_summarizer/` 是唯一正式模型目录，最终包含可由 Hugging Face 直接加载的正式模型与 Tokenizer 文件，以及 B 交付给 C 的 `model_metadata.json`。该元信息契约、训练/在线参数一致性和 C 的读取责任以 [ARCHITECTURE.md](docs/ARCHITECTURE.md) 为准；本阶段不创建虚假的元信息或模型。`runtime/training_runs/` 是 B 唯一正式实验运行记录目录，保存可追溯的训练、验证、评价和性能运行记录；`runtime/hf_cache/` 存放模型缓存。上述运行时产物均不得提交 Git，后端不得在线训练。

## 硬性指标与当前阶段

CNewSum test 上完整正式摘要流水线的 `corpus_rougeL` 必须不低于 0.40，且单样本 ROUGE-L 达标率 `quality_pass_rate` 必须不低于 0.95。模型加载、GPU 预热后，`SummaryPipeline.generate(article)` 在 batch_size=1 下单篇生成必须小于 1.5 秒；性能达标率 `latency_pass_rate` 必须不低于 0.95，且 `p95_generation_time_ms < 1500`。完整验收、候选排序和调参停止规则见 [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)。
