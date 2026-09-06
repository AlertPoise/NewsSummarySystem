# 角色 A 工作清单（阶段 1-6）

> 角色 A 的终版责任：**架构 + 数据库 Schema + FastAPI 公共规范 + 收藏/反馈/模型指标 + 集成/文档**。
> 本文件是角色 A 在 6 个阶段的唯一入口，每条任务都列出：输入、产出位置（文件名）、验收、与他人边界。

---

## 阶段 1 现状（当前所处阶段：文档与边界冻结）

| 编号 | 任务 | 状态 | 验证位置 |
|---|---|---|---|
| A1-01 | 项目文档与架构维护 | ✅ 6 份冻结文档 + 死链审查通过（2026-09-05：全仓 `docs/` 引用扫描，缺失项已全部修复；`docs/WINDOWS_SETUP.md` 已补写） | README, REQUIREMENTS, DEVELOPMENT_PLAN, ARCHITECTURE, API, DATABASE, AI_PROMPTS, WINDOWS_SETUP |
| A1-02 | MySQL Schema 维护 | ✅ DATABASE.md ↔ `sql/create_database.sql` ↔ `sql/init_news_summary.sql` ↔ `backend/app/models.py` 全对齐；DATABASE.md 已升级为可执行规范（§6-§13） | `DATABASE.md §1-§4` 字段表 + `§6-§10` 运行时规范 + `§13` 初始化脚本 |
| A1-03 | API 公共规范 | ✅ `docs/API.md` ↔ `backend/app/schemas.py`；`FavoriteResponse` 与 `FeedbackResponse` 已补；运行时验证 `{"code":0}` 包装生效 | `schemas.py` + 冒烟记录（下表） |
| A1-04 | FastAPI 公共层规范 | ✅ `main.py` 注册 `/api/health` + 4 router（10 条路由与 API.md 全对齐）、BusinessError/NotImplementedError 双全局 handler、CORS、UUID v4 校验依赖 | `main.py`、`exceptions.py`、`dependencies.py` |

**阶段 1 冒烟验证记录（2026-09-05，Python 3.13 venv + 轻量依赖）：**

| 用例 | 请求 | 结果 |
|---|---|---|
| 健康检查 | `GET /api/health` | ✅ 200 `{"code":0,"message":"ok","data":{"status":"healthy"}}` |
| 缺失 Header | `POST /api/favorites/1`（无 X-Client-ID） | ✅ 400 `{"code":1001,"message":"缺少 X-Client-ID Header"}` |
| 非法 UUID | `POST /api/favorites/1`（X-Client-ID: not-a-uuid） | ✅ 400 `{"code":1001,"message":"X-Client-ID 格式错误，必须为 UUID v4"}` |
| 未实现路由 | `GET /api/model/metrics` | ✅ 501 `{"code":1005,...}`（占位路由统一 501，不暴露裸 500） |
| 路由清单 | `GET /openapi.json` | ✅ 10 条路由与 API.md 冻结契约一致（含 DELETE /api/favorites/{news_id}） |

**阶段 1 遗留项处置（已全部闭环）：**

| 事项 | 处置 |
|---|---|
| `start_backend.ps1` 死链 `docs/WINDOWS_SETUP.md` | ✅ 已补写该文档（从零到跑通后端的完整指南） |
| `.env.example` 死链 `docs/AI_PIPELINE.md` | ✅ 改指 `docs/ARCHITECTURE.md` 第 4 节 |
| `scripts/init_database.ps1` 11 个解析错误 | ✅ 重写为 `sql/init_news_summary.sql` 的薄交互壳（根因：UTF-8 无 BOM 被 PS 5.1 按 GBK 误读；现 UTF-8 BOM + 0 解析错误） |
| `PHASE5_*` / `PHASE6_*` / `PRACTICE.md` 引用 | ✅ 非 dead link，为阶段 5/6 产出占位，维持现状 |

**阶段 1 验收（A 自我签字，2026-09-05 关账）：**
- 路径：所有 FastAPI 路径与 API.md §2 对齐（`/api/*` + X-Client-ID Header）——openapi.json 逐条核对 ✅
- JSON：所有响应符合 `{"code":0,...}` 包装——运行时验证 ✅
- 错误码：5 个业务错误码（1001-1005）通过统一 handler 自动返回——1001/1005 运行时验证 ✅
- 边界：API 不直连数据库业务表；通过 Service 层访问；不持有/调用 AI；不持有/调用 Pipeline——路由全部 raise NotImplementedError，无越界实现 ✅

---

## 阶段 3 现状（业务实现 + 配套单测）

| 范畴 | 状态 |
|---|---|
| `services/user_service.py`（add/remove/list/upsert/get_news_user_state） | ✅ 实现完成（DATABASE.md §2/§3/§6/§7/§10 全对齐） |
| `services/model_service.py`（get_latest_metrics） | ✅ 实现完成（DATABASE.md §9.5 取数规则） |
| 5 路由替换 NotImplementedError（favorites×3、feedback×1、model×1） | ✅ 全部接通真实业务 |
| `tests/conftest.py`（SQLite 内存 + PRAGMA foreign_keys=ON） | ✅ 新建 |
| `tests/test_api.py`（A 部分 15 用例） | ✅ 覆盖契约 + 错误码 + 边界 |
| `tests/test_database.py`（A 部分 12 用例） | ✅ 覆盖 Service 层 + 唯一约束 + FK |
| `backend/app/models.py` 类型别名 `BigIntUnsigned/Char64/MediumText/Decimal7x6` | ✅ 升级 SQLAlchemy 2.x 兼容写法，MySQL/SQLite 双 dialect 自适配 |

**阶段 3 验收（pytest 套件，2026-09-05）：**

```
tests/test_ai.py::test_ai_contract_is_frozen PASSED
tests/test_api.py::test_health_check PASSED
tests/test_api.py::test_add_favorite_success/idempotent/missing_client_id_returns_1001/invalid_uuid_returns_1001/news_not_found_returns_1002  (5 PASSED)
tests/test_api.py::test_remove_favorite_success/idempotent_when_no_record  (2 PASSED)
tests/test_api.py::test_list_favorites_returns_only_owned/missing_client_id_returns_1001  (2 PASSED)
tests/test_api.py::test_submit_feedback_insert_then_update/news_not_found_returns_1002/invalid_body_returns_422  (3 PASSED)
tests/test_api.py::test_get_model_metrics_success/no_record_returns_1002/returns_latest_only  (3 PASSED)
tests/test_database.py::test_database_models_are_available PASSED
tests/test_database.py::test_add_favorite_inserts_row/idempotent_at_service_layer/news_not_found_raises_1002  (3 PASSED)
tests/test_database.py::test_remove_favorite_deletes_row/no_record_is_noop  (2 PASSED)
tests/test_database.py::test_list_favorites_excludes_other_clients/empty  (2 PASSED)
tests/test_database.py::test_upsert_feedback_insert_then_update_preserves_created_at/news_not_found_raises_1002/feedback_unique_constraint_violates_on_raw_duplicate  (3 PASSED)
tests/test_database.py::test_get_news_user_state_none_client/no_records/only_favorite/favorite_and_feedback  (4 PASSED)
========================= 32 passed, 2 warnings in 0.31s =========================
```

**阶段 3 遗留项 / 待跟进：**

| 事项 | 状态 | 说明 |
|---|---|---|
| A3-07 与 D 集成（D3-10） | ⏸ | D 必须调 `UserService.get_news_user_state`；当前 D `api/news.py` 仍 raise NotImplementedError，等 D 进入阶段 3 |
| 真库冒烟（MySQL 8.0.16+） | 📋 可选 | pytest 已用 SQLite + PRAGMA FK 验证约束语义；建议阶段 5 联调时跑 `pytest --mysql`（需新增 `tests/conftest_mysql.py`） |
| `models.py` 字段类型升级 | ✅ 已落地 | SQLAlchemy 2.x 不允许主类型传 `unsigned=True`，全部改用 `with_variant(...)` 模式；MySQL DDL 仍产生 `BIGINT UNSIGNED`，SQLite 测试库降级 `INTEGER`/`NUMERIC`/`TEXT` |

---

## 阶段 3 任务清单（业务 API 与集成）

| 编号 | 任务 | 输入 | 产出位置 | 验收 | 状态 |
|---|---|---|---|---|---|
| A3-01 | 收藏业务 | `client_id`、`news_id` | `services/user_service.py:add_favorite` + `api/favorites.py:POST` | 重复 POST 仍 200 + `is_favorite=true`；唯一约束不失效 | ✅（2026-09-05：pytest `test_add_favorite_success/idempotent` 全绿） |
| A3-02 | 取消收藏 | `client_id`、`news_id` | `services/user_service.py:remove_favorite` + `api/favorites.py:DELETE` | 无记录时仍 200 + `is_favorite=false` | ✅（2026-09-05：pytest `test_remove_favorite_success/idempotent_when_no_record` 全绿） |
| A3-03 | 收藏列表 | `client_id` | `services/user_service.py:list_favorites` + `api/favorites.py:GET` | 仅返回本客户端的收藏；不含 `content` | ✅（2026-09-05：pytest `test_list_favorites_returns_only_owned` 验证不含 content 字段） |
| A3-04 | 摘要反馈 | `client_id`、`news_id`、`helpful` | `services/user_service.py:upsert_feedback` + `api/feedback.py:POST` | 唯一约束 `(client_id, news_id)`；首次 INSERT 后续 UPDATE；`created_at` 不变 | ✅（2026-09-05：pytest `test_upsert_feedback_insert_then_update_preserves_created_at` + `test_feedback_unique_constraint_violates_on_raw_duplicate` 双验证） |
| A3-05 | 用户状态查询 | `db`、`client_id \| None`、`news_id` | `services/user_service.py:get_news_user_state` | 返回 `{is_favorite, feedback}`；D 详情必须复用 | ✅（2026-09-05：pytest 4 个用例覆盖 None / 无记录 / 仅收藏 / 收藏+反馈 四种语义；签名与 ARCHITECTURE.md §7 + DATABASE.md §10.1 完全一致） |
| A3-06 | 模型指标查询 | `db` | `services/model_service.py:get_latest_metrics` + `api/model.py:GET` | `dataset=CNewSum, dataset_split=test`；无记录 404/1002 | ✅（2026-09-05：pytest `test_get_model_metrics_success/no_record/returns_latest_only`；按 created_at DESC 取最新；无记录抛 BusinessError(1002)） |
| A3-07 | 与 D 新闻详情集成 | `news_articles` 记录 + A3-05 用户状态 | D 的 `api/news.py:GET /news/{news_id}` 内合并 | D 不复制用户查询 | ⏸ 等 D（D3-10） |

**A3-05 冻结内部契约（docs/ARCHITECTURE.md §7）：**

```python
UserService.get_news_user_state(db, client_id, news_id)
-> {"is_favorite": bool, "feedback": bool | None}
```

---

## 阶段 5 任务清单（端到端联调）

| 编号 | 任务 | 输入 | 产出位置 | 验收 |
|---|---|---|---|---|
| A5-01 | 总体端到端集成 | 阶段 2-4 全部产出 | `docs/PHASE5_E2E_LOG.md` | 网站 → MySQL → Worker → AI → API → HarmonyOS 全链路真实跑通 |
| A5-02 | REST 契约一致性 | API.md ↔ 当前实现 | `docs/PHASE5_API_DIFF.md` | 路径/字段/状态码/Header 差异清单 |
| A5-03 | 数据库一致性 | DATABASE.md ↔ ORM ↔ DDL ↔ 业务 | `docs/PHASE5_DB_DIFF.md` | 字段/约束/状态机差异清单 |
| A5-04 | 五模块联调问题协调 | 阶段 5 缺陷 | `docs/PHASE5_DEFECTS.md` | 所有 Mock 删除；缺陷归属清晰 |

---

## 阶段 6 任务清单（测试、优化、提交）

| 编号 | 任务 | 输入 | 产出位置 | 验收 |
|---|---|---|---|---|
| A6-01 | 系统集成测试 | A5-01 联调系统 | `docs/PHASE6_INTEGRATION_REPORT.md` | Windows/MySQL/API 全量验证 |
| A6-02 | README 最终整理 | 阶段 5 真实结果 | `README.md` | 不声明未完成能力；硬指标实际数据回填 |
| A6-03 | 软件实践文档汇总 | B/C/D/E 提供的材料 | `docs/PRACTICE.md` | 训练记录/AI 章节/爬虫测试/客户端截图齐备 |
| A6-04 | 最终提交检查 | 仓库全量 | `docs/PHASE6_SUBMIT_CHECKLIST.md` | 不含数据/权重/缓存/密码/`CHANGE_ME` 残留 |

---

## 角色 A 永久边界（不可越界）

| 可改 | 不可改 |
|---|---|
| `docs/*` | `backend/app/ai/*` |
| `backend/app/{main,config,database,models,schemas,dependencies,exceptions}.py` | `backend/app/crawlers/*` |
| `backend/app/api/{favorites,feedback,model}.py` | `backend/app/api/news.py`（D 独享；A 仅在 D3-10 调用 A3-05 时配合） |
| `backend/app/services/{user_service,model_service}.py` | `backend/app/services/{news_service,summary_service}.py` |
| `sql/*` | `backend/app/worker.py` |
| `scripts/*` | `frontend_harmony/` |
|  | `model_training/` |
|  | `runtime/` 中真实产物 |

**通用禁止**：硬编码密码；API Route 直连 AI 或业务数据库；绕过 Service；不按 ARCHITECTURE.md §9 流程直接改他人公共接口。
