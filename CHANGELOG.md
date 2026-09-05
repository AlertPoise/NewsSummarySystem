# 更新日志

本项目所有对外可见的阶段性变更、里程碑、不可变改动都记录在此文件。版本号遵循 `MAJOR.MINOR.PATCH` 的语义版本规范：

- `MAJOR`：冻结架构 / 公共契约 / 技术栈发生破坏性变化
- `MINOR`：新增可交付能力（如完成阶段任务、引入新角色接口）
- `PATCH`：修复、文档校对、CI 改进等不破坏兼容性的小改动

## [未发布]

### 阶段 3（进行中）
- A：完成 A3-01~A3-06 业务实现（UserService / ModelService / 5 个 API 路由 / SQLAlchemy 2.x 双 dialect / conftest 双引擎 fixture / 32 项 pytest / 幂等 seed SQL）
- A：完成本机 MySQL 端到端验证（`scripts/run_e2e.ps1`），14/14 ALL GREEN（含 9 项 REST 契约 + 32 项 pytest MySQL 模式 + 收尾 verdict）
- 待 A3-07：`UserService.get_news_user_state` 被 D 调用方集成
- 待 A5 / A6：等 B/C 评价数据与 D/E 最终交付

### 文档维护
- 新增 `docs/AI_PROMPTS_我的.md`（个人 AI 使用归档副本，正式共享仍以 `AI_PROMPTS.md` 为权威源）
- 补充 GitHub 文档：`CHANGELOG.md`（本文件）、`CONTRIBUTING.md`、`.github/ISSUE_TEMPLATE/*`、`.github/PULL_REQUEST_TEMPLATE.md`
- `README.md` 顶部补充 License / 课程等徽标 + 目录

## [0.2.0] - 阶段 1+2 基建完成

### 阶段 1：冻结（已完成）
- 初始化工程目录与中文文档链
- 冻结五角色（A/B/C/D/E）职责边界、公共 REST 契约、数据库 Schema、技术栈
- 5 人职责边界明确写入 `VIBECODING_PROMPT.md`

### 阶段 2：模型与训练（部分）
- B：等待正式 CNewSum 训练与模型交付契约落地
- C：等待 `SummaryPipeline` 正式实现与 AI 端到端测试
- 待 `runtime/models/news_summarizer/` 内容填充与 `model_metadata.json` 校验

## [0.1.0] - 阶段 0 仓库初始化

### Added
- MIT `LICENSE`
- 基础 `README.md`
- 顶层 `VIBECODING_PROMPT.md`（AI 编码约束）
- 基础 `.gitignore`（Python 产物 / `.venv` / `runtime/datasets|models|hf_cache|logs|training_runs` / IDE 产物）
- `docs/` 初始结构：`REQUIREMENTS.md` / `ARCHITECTURE.md` / `DEVELOPMENT_PLAN.md` / `API.md` / `DATABASE.md` / `AI_PROMPTS.md`
- `backend/` 已冻结后端骨架
- `model_training/` 已冻结离线训练骨架
- `frontend_harmony/` 阶段 4 客户端预留位
- `sql/` 与 `scripts/` 基础设施文件
- `runtime/datasets/.gitkeep` / `runtime/models/.gitkeep` / `runtime/hf_cache/.gitkeep` / `runtime/logs/.gitkeep` / `runtime/training_runs/.gitkeep`

---

## 维护说明

- 每次里程碑达成或对外可见改动前，**先更新本文件**，再合并到主分支
- 复盘 / 答辩 / 提交前最后审一遍本文件，确保与 `ROLE_A_CHECKLIST.md`、`ROLE_A_AUDIT.md`、最新一次会话的 `AI_PROMPTS.md` 记录自洽
- 新增阶段请保留旧阶段记录，不允许覆写历史
