# AI 使用记录（个人副本）

> 个人归档副本，原始共享文件位于 [docs/AI_PROMPTS.md](AI_PROMPTS.md)。本文件按模板沿用，记录本次会话中 AI 实际辅助产出的所有阶段3 / E2E 工作，便于后续审计与本组互查。
> 正式共享记录仍以 `docs/AI_PROMPTS.md` 为权威源。

## 统一记录模板（沿用）

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

---

## 阶段3 业务实现

日期：2026-09-05

人员：A

角色：项目架构与文档维护（业务 API 与后端集成）

阶段：阶段3

任务编号：A3-01 / A3-02 / A3-03 / A3-04 / A3-05 / A3-06

使用工具：WorkBuddy（CC 编程助手）

任务目的：实现 A 职责范围内的收藏、反馈、模型指标后端业务：含 Service 静态方法、5 个 API 路由去 NotImplementedError、SQLAlchemy 2.x 双 dialect 让 SQLite 测试与 MySQL 生产共用、conftest 双引擎 fixture、配套 pytest 用例、幂等种子 SQL，以及阶段签字清单更新。

完整Prompt：

```
A（推荐）实现 A3-01~06 + 配套单测
```

后续多轮短指令补完：SQLAlchemy 双 dialect 写法、conftest 双引擎 fixture 设计、test_api/test_database 重写、seed SQL 幂等与字段、API 契约逐字段对齐。

涉及文件：

- `backend/app/services/user_service.py`
- `backend/app/services/model_service.py`
- `backend/app/api/favorites.py`
- `backend/app/api/feedback.py`
- `backend/app/api/model.py`
- `backend/app/models.py`
- `backend/app/dependencies.py`
- `backend/app/exceptions.py`
- `backend/app/schemas.py`
- `backend/tests/conftest.py`
- `backend/tests/test_api.py`
- `backend/tests/test_database.py`
- `sql/seed_test_data.sql`
- `docs/ROLE_A_CHECKLIST.md`

AI生成内容：

- `UserService`：add/remove/list_favorite 三个静态方法 + `upsert_feedback` + `get_news_user_state` 五个方法全部实现，对接 SQLAlchemy Session 与 `X-Client-ID` UUID v4 维度
- `ModelService.get_latest_metrics`：从 `model_evaluations` 取最新一行并以 `ApiResponse` 包装输出
- 5 个 API 路由：去掉骨架期的 `NotImplementedError`，按 `docs/API.md` 返回 `{code, message, data}` 包装
- `models.py`：`with_variant(MYSQL_BIGINT(unsigned=True), "mysql").with_variant(SQLITE_INTEGER(), "sqlite")` 让 `rouge1/rouge2/rougeL` 在 SQLite 测试与 MySQL 生产下都正确
- `tests/conftest.py`：SQLite 内存引擎与 `TEST_MYSQL_URL` 切真 MySQL 双 fixture；启用 `PRAGMA foreign_keys=ON`；表名对齐实际为 `favorites` / `feedback`（无 `user_` 前缀）
- `tests/test_api.py` 15 用例 + `tests/test_database.py` 12 用例，覆盖 API 契约、错误码、FK 约束、模型指标空表兜底
- `sql/seed_test_data.sql`：75 行，幂等灌 1 条新闻 + 1 条 `model_evaluations`，FK 顺序安全（子表 → 父表 DELETE）
- `ROLE_A_CHECKLIST.md`：阶段3 现状表 + A3-01~06 签字栏

人工检查：

- `cd backend && .venv/Scripts/python -m pytest tests -v` 32/32 全绿（SQLite 内存模式）
- 每个 API 路由返回的 `code/data` 字段逐一与 `docs/API.md` §1 对照
- 字段类型（DECIMAL 精度、BIGINT UNSIGNED、TEXT 容量）与 `docs/DATABASE.md` 一致
- 公共契约（路径、字段、状态码）未做私自改动
- 五个 TODO（`A3-07` 等）按 `TODO(角色)：输入/输出/依赖` 格式落实

人工修改：

- AI 初次给的 `user_favorites` / `user_feedback` 表名为 AI 幻觉，回归实际表名 `favorites` / `feedback`（conftest.py + 后续 ps1 同步）
- `rouge1 DECIMAL(7,6)` 在 MySQL 取出后强制转 `float`，避免 Python 精度显示怪值
- conftest fixture 顺序：MySQL fixture 在会话级 scope 启用 `TEST_MYSQL_RESET=1`，SQLite fixture 隔离每次 setup
- `upsert_feedback` 内部事务边界由 AI 提出的两次写法改成显式 commit + 异常回滚

最终结果：阶段3 业务实现完整，pytest 32 项 SQLite 全绿，等待真 MySQL 端到端验证。

---

## E2E 端到端验证脚本与 7 轮踩坑

日期：2026-09-05

人员：A

角色：项目架构与文档维护（真 MySQL 集成验收）

阶段：阶段3 收尾（衔接阶段5）

任务编号：A3-08（自拟：集成验收）

使用工具：WorkBuddy（CC 编程助手）

任务目的：在本机 MySQL 8.0.45 上跑端到端验证——一条命令覆盖：DB 连接探测、库创建、幂等灌种子、起 uvicorn、9 项 REST 路由契约、pytest 32 项切真 MySQL、收尾 verdict 汇总，期望所有阶段 ALL GREEN。

完整Prompt：

```
真 MySQL 端到端验证
```

后续 7 轮贴 Clipboard_Screenshot.png 让 AI 逐轮定位 PS 5.1 / pytest / API 契约三方面踩坑。

涉及文件：

- `scripts/run_e2e.ps1`（约 502 行，最终 0 解析错）
- `backend/conftest.py`（新建 12 行注释，作为 pytest rootdir 锚点）
- `sql/seed_test_data.sql`（头部 DELETE 顺序倒过来，子表 → 父表）
- `docs/ROLE_A_CHECKLIST.md`（登记阶段3 真库端到端通过）

AI生成内容：

- 7 阶段 ps1 骨架：`mysql.conn` → `mysql.create_db` → `mysql.seed` → `uvicorn.boot` → `route.contracts`（9 项）→ `pytest.mysql` → `summary`
- `Hit` 函数：包成 hash 返回 `{Ok, StatusCode, Content}`，不外抛错，避免触发 `$ErrorActionPreference='Stop'` 中断 ps1 流
- `Add-Verdict` 命名空间：失败 detail 强制带 `'HTTP=' + StatusCode + ' body=' + Content`，不让 verdict 丢失诊断上下文
- 阶段 3 mysql.seed 改用变量接收 stdout/stderr，失败 detail 携带 mysql 退出码与原始错误而非空话
- 阶段 6 pytest：文件重定向 + array splatting 调外部命令，UTF-8 输出在脚本顶部三连设置

人工检查：

- 本机 `cd C:\Users\18356\Desktop\NewsSummarySystem-main && powershell -ExecutionPolicy Bypass -File scripts\run_e2e.ps1` 多轮重跑
- 7 轮每次贴报错截图给 AI 定位、修复、重跑，最后一轮 14/14 ALL GREEN
- 所有踩坑逐条落 `F:\workbudddy\2026-09-05-13-00-21\.workbuddy\memory\2026-09-05.md`，可追溯

人工修改（按时间顺序，7 轮 12 修）：

| # | 踩坑 | 修法 |
|---|---|---|
| 1 | `$Host` `$Pwd` 是 PS 5.1 内置只读变量，`Convert-DbEnvToUrl` 参数同名 → `VariableNotWritable` | 参数加 `P_` 前缀：`$P_Host` `$P_Port` `$P_Pwd` |
| 2 | 数组字面量里 `'=' + $dbCharset` 被 PowerShell 拆成两个元素 → `--default-character-set=` 编译时报字符集名为空 | 先赋给 `$charsetArg = '--default-character-set=' + $dbCharset` 再放进数组 |
| 3 | 表名 AI 幻觉加了 `user_` 前缀（`user_favorites` / `user_feedback`），实际是 `favorites` / `feedback` | conftest.py + ps1 都改回无前缀 |
| 4 | `$ErrorActionPreference='Stop'` + `Hit` 函数 catch 块二次抛错 → 整个 ps1 流中断 | Hit 函数**内消化** hash 返回，完全不要依赖外层 catch |
| 5 | `missing_header` 断言 HTTP 422，但 `app.exceptions.invalid_request()` 实际返 **400** | 期望从 422 改 400（pytest 是契约权威源） |
| 6 | IWR `GetResponseStream()` 拿空字符串（4xx 时 chunked 流被 IWR 内部消费） | 优先读 `$_.ErrorDetails.Message` + stream 兜底 |
| 7 | `seedNewsId` 段反引号续行 + `'A' + "B" + 'C'` 三段拼接 → PS 5.1 parser 算后传入 native exe 时 news_id 变怪值 | 单变量双引号 here-string：`$seedNewsIdSql = "SELECT ..."` 直接传给 mysql |
| 8 | 顶部 `'Stop'` 让 pytest 的 stderr 触发 `NativeCommandError` 中断 ps1 | 改 `'SilentlyContinue'` |
| 9 | pytest `2>&1` 流只在 catch 里拿一行概要，完整 traceback 被吞 | 文件重定向 `1> $pytestStdout 2> $pytestStderr` + ReadAllText 拼接 |
| 10 | pytest `ModuleNotFoundError: No module named 'app'`（从项目根启动，cwd ≠ backend/，pytest rootdir 解析错） | 新建 `backend/conftest.py`（仅注释）作 rootdir 锚点 + 显式 `--rootdir=$backendDir` 双保险 |
| 11 | `route.favorite_list` 断言 `$b.data.items.Count`，实际 `data` 是直接数组（`test_api.py:156` 权威） | 改 `$b.data.Count`，加 array / object 双形态判断 |
| 12 | seed 重跑 → 上一轮 POST favorites/feedback 留下子行，`DELETE FROM news_articles` 触发 FK 1451 | `seed_test_data.sql` 头部加 `DELETE FROM feedback / favorites` 子表先，父表后 |
| 13 | **PS 5.1 `>` 重定向默认 UTF-16 LE with BOM** → Read 工具看到 BOM 当 binary 拒绝解析，ps1 -match 命中不了 banner | 顶部 param() 后三连 encoding：`$OutputEncoding` / `[Console]::OutputEncoding]` / `$PSDefaultParameterValues['Out-File:Encoding']` 都设 utf8 |
| 14 | 调试阶段 ps1 跑 pytest 与 bash 直接跑同一命令结果天差地别 | stage 6 入口 dump `cmd: ...` + `DATABASE_URL=...`，下次失败 30 秒定位 |
| 15 | `Select-Object -Last 1` 拿字符串数组的「最后一行」脆弱 | 改整个组合输出做正则 + 3 级 fallback（`= N passed` / `(?m)^N passed in` / `\d+ passed`） |
| 16 | `'1>'` `'2>'` 单引号包住 → PS 5.1 当**字符串参数**传给 pytest，pytest 不识别，stdout/stderr 文件根本没生成 | 裸 token `1>` `2>` |
| 17 | `runtime/` 目录上次清理后缺失，`Join-Path` 不自动建 | `New-Item -ItemType Directory -Force` 兜底 |
| 18 | **call operator + 字符串拼接 + Windows 路径 → collected 0 items**（同字节命令 bash 32 passed，ps1 0 items）| pytest 调用改 array splatting：`@pytestArgs` 独立 token，绕开 call operator 对反斜杠路径的二次拆分 |

最终结果：

- `mysql.conn` / `mysql.create_db` / `mysql.seed` / `uvicorn.boot` / 9 项 REST 契约（含 `missing_header` / `favorite_insert` / `favorite_idempotent` / `feedback_insert` / `feedback_update` / `favorite_list` / `favorite_delete` / `fk_missing_news` / `metrics`）/ `pytest.mysql`（32 passed，MySQL 引擎）/ `summary` 合计 **14/14 ALL GREEN**
- `scripts/run_e2e.ps1` 最终 0 解析错、约 502 行，单条命令覆盖 7 阶段
- 18 条 PS 5.1 / pytest / API 契约踩坑已落 `memory/2026-09-05.md`，下次维护时直接复用

---

## 待人工补充

- 本次会话中 A 的真实短指令（如「真 MySQL 端到端验证」「这样不行」等）未单独保存原文，仅以概括形式入档。下次维护时如能溯源首次 Codex 初始化原文（已有 TODO(A-阶段1)），建议同步到本文件。
- 若后续 `A3-07`（`UserService.get_news_user_state` 被 D 调用）/ `A5`（评价数据）/ `A6`（最终交付）有新的 AI 调用，请按模板继续追加。

---

_本文件由 AI 按 `docs/AI_PROMPTS.md` 模板起草，使用人 A 复核后纳入个人归档；正式共享仍以 `docs/AI_PROMPTS.md` 为权威源。_
