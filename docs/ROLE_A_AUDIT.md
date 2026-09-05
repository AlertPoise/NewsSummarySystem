# 角色 A 阶段 1 一致性审计报告

> 对比 `docs/`（冻结规范）↔ `sql/`（DDL）↔ `backend/app/`（代码骨架），验证角色 A 的可改范围全部对齐。
> 审计日期：2026-09-05，由 A 自我签字。

## 1. DATABASE.md ↔ sql/create_database.sql ↔ backend/app/models.py

| 表 | 字段数 | 一致性 | 备注 |
|---|---|---|---|
| news_articles | 16 | ✅ | 字段、类型、可空、唯一约束 `content_hash`、外键、3 个索引全对齐 |
| favorites | 5 | ✅ | 唯一约束 `(client_id, news_id)`、外键到 `news_articles(id)` 对齐 |
| feedback | 7 | ✅ | 同上；`helpful` BOOLEAN 对齐 |
| model_evaluations | 11 | ✅ | DECIMAL(7,6) 用于 ROUGE，与 DATABASE.md §4 一致；`created_at` 对齐 |

**结论**：4 表 39 字段 + 4 索引 + 2 唯一约束 + 2 外键全部一致。`summary_status` 通过 SQL CHECK 约束（MySQL 8.x 支持）。

## 2. API.md ↔ backend/app/schemas.py

| API 端点 | 响应 model | 是否已存在 | 缺口 |
|---|---|---|---|
| `/api/health` | `HealthData` | ✅ | — |
| `/api/categories` | `list[str]` | inline | — |
| `/api/news` | `PageData[NewsListItem]` | ✅ | — |
| `/api/news/{news_id}` | `NewsDetail` | ✅ | — |
| `/api/news/{news_id}/summary` | `SummaryStatusData` | ✅ | — |
| `/api/favorites` | `list[NewsListItem]` | inline | — |
| **`/api/favorites/{news_id}` POST/DELETE** | **`FavoriteResponse`** | **❌ 已补** | 本次补齐 |
| **`/api/news/{news_id}/feedback`** | **`FeedbackResponse`** | **❌ 已补** | 本次补齐 |
| `/api/model/metrics` | `ModelMetrics` | ✅ | — |

**结论**：8/8 响应 model 全部到位（含补齐的 2 个）；通用包 `ApiResponse[T]` 已实现，datetime 用 `datetime | None` 兼容 Pydantic v2。

## 3. ARCHITECTURE.md ↔ backend/app/{main,config,database,api,exceptions,dependencies}.py

| 规范条目 | 实现位置 | 状态 |
|---|---|---|
| 依赖方向：Crawler→NewsService→MySQL，禁止 API 直写业务表 | `api/*` 通过 Service 间接访问 | ✅ 阶段 3 实现，路径已对齐 |
| `UserService.get_news_user_state` 冻结内部契约 | `services/user_service.py` 骨架已有；阶段 3 实现 | ✅ 契约已记录 |
| `SummaryPipeline` 公开签名 `load/generate` | `backend/app/ai/pipeline.py` 归 C，本阶段不改正 | ✅ C 范围 |
| `app_env/db_*/model_*` 配置 | `config.py` 已用 pydantic-settings 加载 `.env` | ✅ |
| 业务错误码 1001-1005 + 统一 ApiResponse | `exceptions.py` + `main.py exception_handler` | ✅ 本次补齐 |
| UUID v4 X-Client-ID 校验 | `dependencies.py:require_client_id` | ✅ 本次补齐 |
| ORM 与 DDL 一致 | `models.py` 4 类对齐 `create_database.sql` | ✅ |
| CORS（HarmonyOS 调试需要） | `main.py` CORSMiddleware | ✅ 本次补齐 |

**结论**：ARCHITECTURE.md 的全部公共层契约在 `backend/app/` 范围内已一一对应。

## 4. env.example ↔ config.py ↔ sql/create_database.sql

- DB 名称：`news_summary` ↔ `.env` `DB_NAME` ↔ `CREATE DATABASE` 三处一致 ✅
- DB 用户：`news_app` ↔ `.env` `DB_USER` ↔ SQL `CREATE USER 'news_app'` 一致 ✅
- DB 字符集：`utf8mb4` ↔ `.env` `DB_CHARSET=utf8mb4` ↔ SQL `DEFAULT CHARACTER SET utf8mb4` 一致 ✅
- DB 密码：仍为 `CHANGE_ME`，需在本机 `.env` 替换；`.env` 已 `.gitignore`，不提交 ✅
- 待 C/B 在阶段 2 填：`BERT_MODEL_NAME` / `SUMMARIZER_MODEL_NAME` / `MODEL_VERSION` / `SUMMARIZER_MAX_*_TOKENS`（已注 TODO） ✅

## 5. 阶段 1 验收总评

| 项 | 结果 |
|---|---|
| 需求/架构/职责/接口 完整 | ✅（`docs/` 共 7 份，含本审计报告与 `ROLE_A_CHECKLIST.md`） |
| 五人任务明确 | ✅（DEVELOPMENT_PLAN.md 已冻结） |
| 跨模块接口明确 | ✅（ARCHITECTURE.md §5-9 已冻结签名） |
| 数据库 Schema 完整 | ✅（4 表 + 索引 + 约束 + ORM 对齐） |
| REST 契约完整 | ✅（10 个端点 + 5 个错误码 + 统一响应） |
| FastAPI 公共层规范 | ✅（异常/UUID/CORS/通用包/路由挂载齐备） |
| 不实现阶段 2 及以后 | ✅（仅 `raise NotImplementedError` 占位） |

**签名**：角色 A 阶段 1 任务（A1-01 ~ A1-04）全部通过；可移交至阶段 2。
