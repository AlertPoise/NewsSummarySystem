# AI 使用记录

## 统一记录模板

```text
日期：
人员：
角色：
阶段：
任务编号：
使用工具：
任务目的：
完整Prompt：
涉及文件：
AI生成内容：
人工检查：
人工修改：
最终结果：
```

每次使用 AI 协助修改项目时，责任人须在同一工作周期内按模板追加记录；记录必须列出真实涉及文件与人工检查结果。

若原始 Prompt 超过 500 字，`完整Prompt` 字段改为不超过 200 字的中文概括，并明确标注为“Prompt 概括”；概括必须覆盖任务目标、关键约束、允许范围和禁止事项，不得伪称原文。

## 初始化记录

日期：2026-09-04

人员：A

角色：项目架构与文档维护

阶段：阶段1

任务编号：A1-01

使用工具：Codex

任务目的：初始化《基于自然语言处理的新闻文章自动摘要系统设计与实现》的工程目录、文档、数据库和代码骨架。

完整Prompt：当前未保存第一次 Codex 初始化使用的完整 Prompt 原文。

涉及文件：README、docs、backend、model_training、frontend_harmony、sql、scripts、runtime。

AI生成内容：阶段1目录、初始中文文档、数据库 DDL、FastAPI 健康检查及后续模块骨架。

人工检查：目录、接口、数据库、TODO 格式、注释语言、密码占位符和伪造结果。

人工修改：待 A 记录。

最终结果：形成初始阶段1工程方案。

TODO(A-阶段1)：由A补充第一次Codex初始化使用的完整Prompt原文；输入为可追溯的首次会话记录，输出为本条“完整Prompt”的完整原文，必须遵守本文件统一记录模板。

## 本次文档维护记录

日期：2026-09-04

人员：A

角色：项目架构与文档维护

阶段：阶段1

任务编号：A1-01、A1-02、A1-03、A1-04

使用工具：Codex

任务目的：精简文档数量、固化跨模块接口、任务台账、REST 契约和字段职责。

完整Prompt：本次会话中用户粘贴的“你现在正在维护课程项目仓库：NewsSummarySystem”完整要求文本。

涉及文件：README.md、docs/REQUIREMENTS.md、docs/ARCHITECTURE.md、docs/DEVELOPMENT_PLAN.md、docs/API.md、docs/DATABASE.md、docs/AI_PROMPTS.md。

AI生成内容：重组现有 Markdown，删除已被吸收的三份文档，并记录文档与现有代码差异。

人工检查：文档数量、接口一致性、死链接、非 Markdown 修改和代码差异清单。

人工修改：待 A 验收补充。

最终结果：待本次阶段1维护验收。

## B 开发前契约整理记录

日期：2026-09-05

人员：A

角色：项目架构与文档维护

阶段：阶段1（阶段2正式开发前）

任务编号：A1-01

使用工具：Codex

任务目的：阶段2正式开发前，对 B 离线训练、自动实验、模型交付、指标、10轮调参和运行记录契约进行冻结。

Prompt 概括（原始 Prompt 超过 500 字）：阶段2前冻结 B 的数据路径、模型 JSON、实验记录、验收/排序和10轮规则；只改文档、忽略规则和 TODO。禁止训练、数据处理、下载、ROUGE/Benchmark、业务实现及修改架构、接口、Schema、职责或阶段。

涉及文件：README.md、VIBECODING_PROMPT.md、docs/REQUIREMENTS.md、docs/ARCHITECTURE.md、docs/DEVELOPMENT_PLAN.md、docs/AI_PROMPTS.md、.gitignore、model_training/config.yaml、model_training/prepare_cnewsum.py、model_training/train.py、model_training/evaluate.py、model_training/benchmark.py、backend 中仅含失效文档引用的 TODO 注释、runtime/training_runs/.gitkeep。

AI生成内容：B 离线训练数据位置、模型 JSON 交付、实验运行记录、质量/性能验收、候选排序、10轮调参、B/C 依赖与训练依赖边界的文档契约；训练骨架和阶段占位注释仅更新引用/说明。

人工检查：检查冻结架构和公共接口未改变；确认没有读取或处理数据集内容、没有训练、下载、ROUGE、Benchmark 或阶段2实现；检查死链接、Git 忽略、路径和文档字段一致性。

人工修改：待 A 验收补充。

最终结果：完成 B 开发前契约整理，未开始模型训练或阶段2正式实现。
