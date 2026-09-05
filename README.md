# 基于自然语言处理的新闻文章自动摘要系统设计与实现

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python: 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)
![MySQL: 8.x](https://img.shields.io/badge/MySQL-8.x-orange.svg)
![HarmonyOS: 5](https://img.shields.io/badge/Client-HarmonyOS%205-green.svg)
![Stage: 1+2 基建完成](https://img.shields.io/badge/Stage-%E6%AE%A1%E6%94%AF%E5%A1%AB%E5%AE%9E-lightgrey.svg)

## 目录

- [项目简介](#项目简介)
- [最终核心功能](#最终核心功能)
- [技术栈](#技术栈)
- [总体数据流](#总体数据流)
- [五人职责概览](#五人职责概览)
- [六阶段概览](#六阶段概览)
- [快速开始](#快速开始)
- [目录结构](#目录结构)
- [文档阅读顺序](#文档阅读顺序)
- [Windows 基础开发环境](#windows-基础开发环境)
- [CNewSum 与模型目录](#cnewsum-与模型目录)
- [硬性指标与当前阶段](#硬性指标与当前阶段)
- [贡献与变更日志](#贡献与变更日志)

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

## 快速开始

> 当前为阶段 1+2 基建完成 + 阶段 3 业务实现（角色 A 部分）状态；以下仅给出**最小复现**所需的命令，完整端到端由 [`scripts/run_e2e.ps1`](scripts/run_e2e.ps1) 一键驱动。

```powershell
# 1. 克隆仓库
git clone https://github.com/<owner>/NewsSummarySystem.git
cd NewsSummarySystem

# 2. 后端虚拟环境与依赖
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
cd ..

# 3. MySQL 8.x 起服务并创建数据库（用户名/密码与 backend/.env 一致）
mysql -uroot -p -e "CREATE DATABASE news_summary CHARACTER SET utf8mb4;"

# 4. 配置 backend/.env（不提交）
# DATABASE_URL=mysql+pymysql://<user>:<pwd>@127.0.0.1:3306/news_summary?charset=utf8mb4

# 5. 一次性端到端验证（自动灌种子 + 起 uvicorn + 9 项 REST 契约 + 32 项 pytest MySQL）
powershell -ExecutionPolicy Bypass -File scripts\run_e2e.ps1
```

期望输出尾行：

```text
[7/7] summary :: ALL GREEN
```

完整系统运行条件、客户端导入、训练脚本等按 [WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md) 执行；模型训练与评价的硬性指标见 [硬性指标与当前阶段](#硬性指标与当前阶段)。

## 目录结构

```text
NewsSummarySystem/
├── README.md                    本文件（GitHub 入口）
├── CHANGELOG.md                 阶段性变更日志
├── CONTRIBUTING.md              5 人组贡献与 PR 流程
├── LICENSE                      MIT 许可证
├── VIBECODING_PROMPT.md         AI 编码硬性约束
├── .gitignore                   Python / IDE / runtime 产物
├── docs/                        需求、架构、计划、API、数据库、AI 记录
│   ├── REQUIREMENTS.md
│   ├── ARCHITECTURE.md
│   ├── DEVELOPMENT_PLAN.md
│   ├── API.md
│   ├── DATABASE.md
│   ├── AI_PROMPTS.md            AI 使用记录（共享权威源）
│   ├── AI_PROMPTS_我的.md       AI 使用记录（个人归档副本）
│   └── WINDOWS_SETUP.md
├── backend/                     已冻结的后端骨架（FastAPI + SQLAlchemy）
├── model_training/              已冻结的离线训练骨架
├── frontend_harmony/            阶段4正式客户端位置
├── sql/   scripts/              后续阶段使用的基础设施文件
├── runtime/                     数据集、模型、缓存、日志，均不提交 Git
└── .github/                     Issue 与 PR 模板（GitHub 自动识别）
```

## 文档阅读顺序

所有成员首先阅读本文件、[REQUIREMENTS.md](docs/REQUIREMENTS.md) 和 [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) 中自己的角色部分。涉及跨模块接口时阅读 [ARCHITECTURE.md](docs/ARCHITECTURE.md)；涉及 REST 时阅读 [API.md](docs/API.md)；涉及 MySQL 时阅读 [DATABASE.md](docs/DATABASE.md)；AI 使用记录写入 [AI_PROMPTS.md](docs/AI_PROMPTS.md)。

## Windows 基础开发环境

固定环境为 Windows 10/11 x64、Python 3.11、MySQL 8、DevEco Studio、PyTorch 与 Transformers。CUDA/GPU 的正式版本和安装命令由 B、C 在阶段2经真实训练与推理验证后填写。本阶段不要求运行任何数据库、后端或 Worker 初始化脚本。

## CNewSum 与模型目录

正式原始 CNewSum 目录固定为 `runtime/datasets/CNewSum_v2/final/`；当前发现的原始文件包括 `dev.simple.label.jsonl`、`test.simple.anno.label.jsonl`、`test.simple.label.jsonl`、`test2017.simple.label.jsonl`、`test2018.simple.label.jsonl`、`train.simple.label.jsonl` 和 `LICENSE.md`。这些文件的字段、编码及最终 train/validation/test 映射均待 B2-01 按真实数据格式和数据集说明验证，后续脚本只能从 `runtime/datasets/` 读取，数据集不得提交 Git。

`runtime/models/news_summarizer/` 是唯一正式模型目录，最终包含可由 Hugging Face 直接加载的正式模型与 Tokenizer 文件，以及 B 交付给 C 的 `model_metadata.json`。该元信息契约、训练/在线参数一致性和 C 的读取责任以 [ARCHITECTURE.md](docs/ARCHITECTURE.md) 为准；本阶段不创建虚假的元信息或模型。`runtime/training_runs/` 是 B 唯一正式实验运行记录目录，保存可追溯的训练、验证、评价和性能运行记录；`runtime/hf_cache/` 存放模型缓存。上述运行时产物均不得提交 Git，后端不得在线训练。

## 硬性指标与当前阶段

CNewSum test 上完整正式摘要流水线的 `corpus_rougeL` 必须不低于 0.40，且单样本 ROUGE-L 达标率 `quality_pass_rate` 必须不低于 0.95。模型加载、GPU 预热后，`SummaryPipeline.generate(article)` 在 batch_size=1 下单篇生成必须小于 1.5 秒；性能达标率 `latency_pass_rate` 必须不低于 0.95，且 `p95_generation_time_ms < 1500`。完整验收、候选排序和调参停止规则见 [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)。

- **当前状态**：阶段 1 冻结（文档 / 职责 / 接口）已完成；阶段 2 模型与训练等待正式交付；阶段 3 角色 A 部分（UserService / ModelService / 5 个 API 路由 / 32 项 pytest）已落地并通过本机 MySQL 端到端 14/14 验证；其他角色的后续工作按 [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) 推进。

## 贡献与变更日志

- 本项目为 5 人课程工程，协作流程、分支策略与 PR 规范见 [CONTRIBUTING.md](CONTRIBUTING.md)
- AI 编码硬性约束见 [VIBECODING_PROMPT.md](VIBECODING_PROMPT.md)
- 阶段性变更、里程碑、不可变改动记录见 [CHANGELOG.md](CHANGELOG.md)
- AI 协助修改的逐次记录见 [docs/AI_PROMPTS.md](docs/AI_PROMPTS.md)；个人归档副本在 [docs/AI_PROMPTS_我的.md](docs/AI_PROMPTS_我的.md)
- Issue / PR 模板位于 [`.github/`](.github/) 目录；提交缺陷时按 [bug_report.md](.github/ISSUE_TEMPLATE/bug_report.md) 模板填写
