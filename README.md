# 基于自然语言处理的新闻文章自动摘要系统设计与实现

## 项目简介

本工程是 Windows 10/11 x64 环境下运行的课程项目终版工程。系统采集两个真实新闻来源，将清洗后的新闻写入 MySQL，依次经中文预处理、BERT 句向量、TextRank、Transformer 输入 Token Budget 和 Seq2Seq Transformer 生成摘要，并由 HarmonyOS 客户端展示新闻、收藏、评价及模型指标。

当前仅完成阶段 1 的需求、架构、接口、数据库和代码骨架冻结；不会伪造新闻、摘要、模型指标或模型加载结果。

## 完整功能

- 两个真实新闻来源采集、网页正文提取、分类映射和 SHA-256 去重。
- 基于 CNewSum 的 Seq2Seq Transformer 训练、ROUGE 评价和性能基准测试。
- BERT 句向量、TextRank 排序、Token Budget 关键句选择及最终摘要生成。
- 新闻分类、分页、详情、摘要请求、收藏、反馈和模型指标 REST API。
- HarmonyOS 新闻浏览、收藏、评价、模型信息及异常状态展示。

## 技术栈

后端使用 Python 3.11、FastAPI、SQLAlchemy 2.x、PyMySQL 与 MySQL 8.x；AI 使用 PyTorch 和 Hugging Face Transformers；客户端使用 HarmonyOS、ArkTS、ArkUI 与 DevEco Studio。唯一正式训练和评价数据集为 CNewSum。

## 架构概览

`新闻源 → Crawler → MySQL → Worker → SummaryPipeline → MySQL → FastAPI → HarmonyOS`。详细边界见 [ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 目录结构

```text
NewsSummarySystem/
├── docs/                 中文冻结文档
├── backend/              FastAPI、数据模型、AI 和采集骨架
├── model_training/       CNewSum 训练、评价和性能测试骨架
├── frontend_harmony/     HarmonyOS 正式工程实施说明
├── sql/                  MySQL 建库脚本
├── scripts/              Windows 初始化与启动脚本
└── runtime/              本地数据集、模型、缓存和日志（不提交）
```

## 开发计划与职责

六阶段安排见 [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)，A/B/C/D/E 职责见其中“人员分工”。任何后续实现必须保持已冻结的目录、字段、路由和 `SummaryPipeline.generate(article)` 接口。

## Windows 运行环境

安装与配置见 [WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md)。阶段 1 可建立 Python 3.11 虚拟环境、安装后端依赖并启动健康检查；MySQL、AI 模型、Worker 与 HarmonyOS 的完整运行分别按其所属阶段完成。

## MySQL 基本配置

数据库名为 `news_summary`，服务地址为 `127.0.0.1:3306`，应用用户为 `news_app`，字符集为 `utf8mb4`。复制 `backend/.env.example` 为 `backend/.env` 后填入本机密码；密码不写入源码或 Git。执行 `scripts/init_database.ps1` 建立数据库结构。

## 后端与 Worker

在 `backend` 目录创建虚拟环境、安装 `requirements.txt` 后，运行 `../scripts/start_backend.ps1`。阶段 1 当前可用接口为 `GET /api/health`。Worker 最终由 `../scripts/run_worker.ps1` 启动，具体业务由 D 在阶段 3 完成。

## CNewSum 与模型目录

CNewSum 是唯一正式训练与评价数据集，原始数据位于 `runtime/datasets/`，不提交 Git。正式摘要权重保存到 `runtime/models/news_summarizer/`，不在线训练且不提交 Git；B 在阶段 2 完成训练，C 在阶段 2 完成在线加载。

## HarmonyOS

阶段 4 由 E 按 [frontend_harmony/README.md](frontend_harmony/README.md) 创建 DevEco Studio 正式工程，仅通过 FastAPI 访问数据和摘要能力。

## 测试与硬性指标

测试规划见 [TEST_PLAN.md](docs/TEST_PLAN.md)。最终须在 CNewSum test 达到 ROUGE-L ≥ 0.40，并且模型预热后 `SummaryPipeline.generate(article)` 单篇耗时小于 1.5 秒。

## 文档索引

- [需求冻结](docs/REQUIREMENTS.md)
- [系统架构](docs/ARCHITECTURE.md)
- [开发计划](docs/DEVELOPMENT_PLAN.md)
- [REST API](docs/API.md)
- [数据库设计](docs/DATABASE.md)
- [AI 流水线](docs/AI_PIPELINE.md)
- [测试计划](docs/TEST_PLAN.md)
- [Windows 环境](docs/WINDOWS_SETUP.md)
- [AI 使用记录](docs/AI_PROMPTS.md)
