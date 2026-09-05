# 贡献指南

> 本项目的工程级 AI 编码约束完整版见根目录 [`VIBECODING_PROMPT.md`](VIBECODING_PROMPT.md)。**VIBECODING_PROMPT.md 优先级高于本文件**；本文件只补充团队协作、PR 流程与 GitHub 维护规范。

## 1. 角色与文件边界

本项目按 [README.md](README.md) 表格将工程任务划分为五个角色：

| 角色 | 主要文件范围 |
|---|---|
| **A** | `docs/`、`backend/app/{main,config,database,models,schemas}.py`、`backend/app/api/{favorites,feedback,model}.py`、`backend/app/services/{user_service,model_service}.py`、`sql/`、`scripts/` |
| **B** | `model_training/`、`runtime/datasets/`、`runtime/models/` |
| **C** | `backend/app/ai/`、与 AI 直接相关的测试 |
| **D** | `backend/app/crawlers/`、`backend/app/services/{news_service,summary_service}.py`、`backend/app/api/news.py`、`backend/app/worker.py` |
| **E** | `frontend_harmony/` |

每人仅在自身职责范围内自主安排开发顺序与节奏，但有以下硬约束：

- 不得未经允许修改其他角色主要负责的文件
- 不得为方便本模块私自改动公共 REST 路径 / 字段 / 数据库 Schema
- 不得复制实现本应由其他角色负责的业务
- 跨角色修改前必须先向用户报告：问题 / 当前实现 / 冻结契约 / 影响角色 / 建议方案，等待用户决定

## 2. 文档阅读顺序

新人（或回归本项目的成员）按以下顺序阅读：

1. [`README.md`](README.md)
2. [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) —— 终版必须实现什么
3. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) —— 模块边界与跨模块接口
4. 涉及 REST 时读 [`docs/API.md`](docs/API.md)
5. 涉及 MySQL 时读 [`docs/DATABASE.md`](docs/DATABASE.md)
6. 涉及任务划分与验收时读 [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md)
7. AI 协助开发前最后读 [`VIBECODING_PROMPT.md`](VIBECODING_PROMPT.md)

如果文档与代码冲突，**以已冻结的需求和公共契约为依据，不得擅自重写公共接口来迁就当前实现**。先报告冲突和影响范围，再由用户决定如何处理。

## 3. 编码底线

- 文件名、类名、函数名、变量名、API 字段、数据库字段使用英文
- **所有代码注释使用中文**
- **所有 docstring 使用中文**
- **所有 TODO 使用中文**，建议格式：`TODO(角色)：说明待完成任务、输入、输出和依赖接口`
- 不硬编码数据库密码、个人 IP、个人绝对路径
- 不提交 `.env`
- 不提交 CNewSum 原始数据、模型权重、缓存、训练日志
- 不伪造新闻、摘要、ROUGE、性能指标或模型结果
- Mock 只能用于模块隔离测试，不能作为最终功能
- 优先只修改当前工作真正需要的文件，不顺手重构无关模块

## 4. Git 工作流

### 4.1 分支策略

- 主分支：`main`（仅放可交付状态，所有合并需 PR 流程）
- 角色分支：`feat/<role>/<task-id>-<short-desc>`（如 `feat/A/A3-01-user-service`、`feat/B/B2-03-cnewsum-prep`）
- 修复分支：`fix/<role>/<short-desc>`（如 `fix/A/run-e2e-ps1-splatted-args`）

### 4.2 提交规范

提交信息推荐格式：

```text
<type>(<scope>): <subject>

<body>

<footer>
```

- `type`：`feat` / `fix` / `docs` / `refactor` / `test` / `chore`
- `scope`：角色代字母 `A` / `B` / `C` / `D` / `E` 或模块名
- `subject`：中文短语，动宾结构，≤ 50 字
- `body`：动机 / 改动点 / 影响范围
- `footer`：关联任务编号、关联 issue

示例：

```text
feat(A): 实现 A3-01~A3-06 业务并接入本机 MySQL 端到端验证

- 完成 UserService / ModelService 五个静态方法
- 5 个 API 路由去 NotImplementedError
- 引入 SQLAlchemy 2.x with_variant 双 dialect
- conftest 升级为 SQLite + TEST_MYSQL_URL 双引擎
- 新增 sql/seed_test_data.sql 幂等灌种子
- 新增 scripts/run_e2e.ps1 一条命令跑 14/14 端到端
- 修复 backend/conftest.py 作为 pytest rootdir 锚点

Refs: A3-01 ~ A3-06
```

### 4.3 PR 流程

1. 从 `feat/<role>/...` 或 `fix/<role>/...` 向 `main` 提 PR
2. PR 标题遵循提交规范；正文按 `.github/PULL_REQUEST_TEMPLATE.md` 填写
3. 至少 1 名其他成员 Code Review 通过后合并（涉及公共契约改动的 PR 需全员知晓）
4. 合并方式默认 Squash；保留详细提交历史请改用 Rebase + Merge
5. PR 合并后请同步更新 `CHANGELOG.md` 和角色对应清单

### 4.4 重大变更门槛

下列任一情况必须**先在 `DEVELOPMENT_PLAN.md` 更新条目，并在 PR 描述里 link 对应章节**，再合入：

- REST 路径或公共字段变化
- 数据库 Schema 变化
- `RawArticle` / `SummaryPipeline` / `SummaryResult` / 模型交付字段变化
- 用户状态内部接口或摘要状态机变化
- 新增 / 替换冻结技术栈组件

## 5. AI 协助记录

每次实际使用 AI 对项目产生修改（含代码 / 文档 / 配置），**责任人**须在 AI_PROMPTS.md 同一工作周期内按 [`docs/AI_PROMPTS.md`](docs/AI_PROMPTS.md) 模板追加记录：

- 真实涉及文件
- AI 生成内容
- 人工检查项 + 实际检查方法
- 人工修改（哪怕只是删一个 AI 幻觉的字段名也要写）
- 最终结果（贴测试输出或 commit hash）

若原始 Prompt 超过 500 字，记录时须概括为不超过 200 字的中文摘要，不得伪造为原文或遗漏影响执行边界的限制。

个人归档副本可放 `docs/AI_PROMPTS_我的.md` 等命名，但**正式共享以 [`docs/AI_PROMPTS.md`](docs/AI_PROMPTS.md) 为权威源**。

## 6. 禁止事项（汇总）

- 不替换 CNewSum、不删 BERT / TextRank / Seq2Seq Transformer、不允许用大模型 API 替代正式摘要模型
- 不引入 Redis、Kafka、Celery、Docker、Kubernetes、微服务、JWT 等未冻结技术
- 不为"工程化"目的增加不必要的复杂层级
- 不增加推荐、评论、登录等与课程目标无关的系统
- 不得为了"先跑起来"擅自改公共契约
- 不得伪造 ROUGE、性能指标或模型结果

## 7. 反馈渠道

- GitHub Issue：缺陷、需求、文档问题
- GitHub Discussion（可选）：架构 / 设计选择讨论
- 课程组内部评审：阶段评审 + 答辩演示

收到反馈后由对应角色在 PR 流程内处理；跨角色问题纳入下一次阶段评审。
