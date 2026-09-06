# MySQL 数据库冻结规范

数据库固定为 `news_summary`，MySQL 8.x，地址 `127.0.0.1:3306`，应用用户 `news_app`，字符集 `utf8mb4`。应用程序不得使用 root；密码仅在本机 `.env`，不得提交 Git。A 维护 Schema、公共连接约定和一致性；本文件是字段语义的最终规范。

> **本文档可执行性**：§1-§4 描述静态字段表（schema 层），§6-§10 描述**运行时行为**（写入路径、状态机、协议契约），开发 A3 / B / C / D 的代码时必须把 §6-§10 当作硬性依据。

---

## 1. news_articles

| 字段 | 类型/可空 | 含义与默认语义 | 写入角色 | 读取角色/API |
|---|---|---|---|---|
| id | BIGINT UNSIGNED，非空，PK AI | 新闻唯一标识 | MySQL | A/D/E；新闻、收藏、反馈 API |
| title | VARCHAR(255)，非空 | 真实新闻标题 | D | D/E；列表、详情 |
| content | MEDIUMTEXT，非空 | D 网页级去噪后的真实正文 | D | D/C/E；仅详情和 AI，列表禁止返回 |
| summary | TEXT，可空 | C Pipeline 返回、由 D Worker 持久化的最终摘要 | D Worker | D/E；列表、详情、摘要任务 |
| category | VARCHAR(32)，非空 | 系统分类，只能为科技、财经、社会、体育、国内、国际 | D | D/E；分类、列表、详情 |
| source | VARCHAR(64)，非空 | 真实来源名称 | D | D/E；列表、详情 |
| source_url | VARCHAR(1024)，非空 | 新闻原始 URL | D | D/E；详情 |
| content_hash | CHAR(64)，非空，唯一 | content 的 SHA-256 十六进制值 | D | D；入库去重 |
| publish_time | DATETIME，可空 | 来源声明的发布时间；无法可靠获取时为空 | D | D/E；列表、详情 |
| crawl_time | DATETIME，非空 | Crawler 实际成功采集内容的时间 | D | D/A；审计 |
| summary_status | VARCHAR(20)，非空 | pending/processing/completed/failed 任务状态 | D Worker | D/E；列表、详情、摘要任务 |
| summary_time_ms | INT，可空 | `SummaryPipeline.generate` 的完整生成耗时毫秒 | D Worker | D/E；详情、摘要任务 |
| summary_error | TEXT，可空 | 最近一次失败的可诊断原因 | D Worker | D/A；内部诊断，不对客户端暴露 |
| model_version | VARCHAR(64)，可空 | 生成该 summary 的正式模型版本 | D Worker | D/A；审计 |
| created_at | DATETIME，非空 | 数据库 news_articles 记录实际创建时间 | D | A/D；审计 |
| updated_at | DATETIME，非空 | 数据库记录最后修改时间 | D Worker/D | A/D；审计 |

索引固定为 category、publish_time、summary_status；content_hash 为唯一约束。`crawl_time` 不等同 `created_at`：前者表示采集成功，后者表示记录创建。API 时间输出均转换为 ISO 8601。

**写入路径**：D 的 NewsService 通过 `INSERT INTO news_articles (..., summary_status='pending', summary=NULL, summary_time_ms=NULL, summary_error=NULL, model_version=NULL, created_at=NOW(), updated_at=NOW())` 完成入库；入库前用 `content_hash` 做幂等去重（已存在则跳过或刷新 `updated_at`，由 D 在 A5-04 中明确）。

**字段更新责任矩阵**：

| 字段 | 谁可写 | 何时写 |
|---|---|---|
| summary / summary_time_ms / model_version | D Worker | 摘要任务由 failed/pending → completed 时 |
| summary_error | D Worker | 摘要任务由 processing → failed 时 |
| summary_status | D Worker / SummaryService | 状态机任意迁移（见 §8） |
| 其余字段 | D NewsService | 入库与外部数据刷新 |

---

## 2. favorites

| 字段 | 类型/可空 | 含义与默认语义 | 写入角色 | 读取角色/API |
|---|---|---|---|---|
| id | BIGINT UNSIGNED，非空，PK AI | 收藏记录标识 | MySQL | A；内部 |
| client_id | VARCHAR(64)，非空 | HarmonyOS 生成的 UUID v4 | A | A；按客户端隔离 |
| news_id | BIGINT UNSIGNED，非空，FK | 被收藏的 news_articles.id | A | A/D；收藏/详情 |
| created_at | DATETIME，非空 | 首次成功收藏时间 | A | A；审计 |

唯一约束 `(client_id, news_id)`；news_id 外键指向 `news_articles.id`（**外键策略详见 §6**）。A 实现插入和删除；D 只能经 `UserService.get_news_user_state` 读取详情状态；E 仅经 REST 访问。

**幂等语义**：

| API | 已存在记录 | 不存在记录 |
|---|---|---|
| `POST /favorites/{news_id}` | 不报错；返回 200 + `is_favorite=true` | INSERT 新记录；返回 200 + `is_favorite=true` |
| `DELETE /favorites/{news_id}` | DELETE 行；返回 200 + `is_favorite=false` | 不报错；返回 200 + `is_favorite=false` |

实现层用 `INSERT ... ON DUPLICATE KEY UPDATE id=id`（无副作用，避免触发 updated_at）或先 SELECT 再 INSERT；DELETE 用 `DELETE ... WHERE client_id=? AND news_id=?` 受影响行数为 0/1 都视为成功。

---

## 3. feedback

| 字段 | 类型/可空 | 含义与默认语义 | 写入角色 | 读取角色/API |
|---|---|---|---|---|
| id | BIGINT UNSIGNED，非空，PK AI | 反馈记录标识 | MySQL | A；内部 |
| client_id | VARCHAR(64)，非空 | UUID v4 客户端标识（**格式与 §7 一致**） | A | A；按客户端隔离 |
| news_id | BIGINT UNSIGNED，非空，FK | 被评价新闻 | A | A/D；详情/反馈 |
| helpful | BOOLEAN，非空 | true 为有帮助，false 为不准确 | A | A/D/E；详情/反馈 |
| created_at | DATETIME，非空 | 首次评价时间 | A | A；审计 |
| updated_at | DATETIME，非空 | 最后一次评价更新时间 | A | A；审计 |

唯一约束 `(client_id, news_id)`；首次反馈 INSERT，后续 UPDATE。该表收集离线分析、重新训练和优化的输入，**不触发在线训练**。

**写入时序（硬性要求）**：

1. `A3-04` 必须先 SELECT 检查是否存在；存在则 UPDATE `helpful`、`updated_at=NOW()`，**`created_at` 不变**；不存在则 INSERT 并填 `created_at=NOW()`、`updated_at=NOW()`。
2. 不得使用 `INSERT ... ON DUPLICATE KEY UPDATE`，因为 MySQL 在 `ON DUPLICATE KEY UPDATE` 路径下 `created_at` 会被 UPDATE 语句覆盖，违反"首次评价时间"语义。
3. 若用 `INSERT ... ON DUPLICATE KEY UPDATE` 实现，必须显式 `created_at = created_at`；或者改用"先 SELECT 后 INSERT/UPDATE"的两步事务。

---

## 4. model_evaluations

| 字段 | 类型/可空 | 含义与默认语义 | 写入角色 | 读取角色/API |
|---|---|---|---|---|
| id | BIGINT UNSIGNED，非空，PK AI | 评价记录标识 | MySQL | A；内部 |
| model_version | VARCHAR(64)，非空 | 与 `SummaryResult.model_version` 同一版本体系 | A（按B/C交付） | A/E；metrics |
| model_name | VARCHAR(255)，非空 | 正式摘要模型名称 | A（按B/C交付） | A/E；metrics |
| dataset | VARCHAR(64)，非空 | 固定 CNewSum | A（按B/C交付） | A/E；metrics |
| dataset_split | VARCHAR(32)，非空 | 固定 test | A（按B/C交付） | A/E；metrics |
| sample_count | INT，非空 | 本次评价样本数 | A（按B/C交付） | A/E；metrics |
| rouge1 | DECIMAL(7,6)，非空 | 完整 Pipeline ROUGE-1 | A（按B/C交付） | A/E；metrics |
| rouge2 | DECIMAL(7,6)，非空 | 完整 Pipeline ROUGE-2 | A（按B/C交付） | A/E；metrics |
| rougeL | DECIMAL(7,6)，非空 | 完整 Pipeline ROUGE-L | A（按B/C交付） | A/E；metrics |
| avg_generation_time_ms | INT，非空 | 预热后 batch_size=1 平均耗时 | A（按B/C交付） | A/E；metrics |
| p95_generation_time_ms | INT，非空 | 相同规则的 P95 耗时 | A（按B/C交付） | A/E；metrics |
| created_at | DATETIME，非空 | 评价记录创建时间 | A | A；审计 |

> **历史扩展字段（不入当前表）**：ARCHITECTURE.md §4 要求每个训练运行记录还包含 `quality_pass_rate` 与 `latency_pass_rate`。这两个字段**只写在 `runtime/training_runs/<run_id>/` 的 JSON 运行记录**，不写入 `model_evaluations`；它们是 B 离线记录的硬门槛，A3-06 的 metrics API 不对外暴露。

B 负责训练和评价主流程，C 提供完整在线 Pipeline 配合，A 按固定字段持久化并提供最新正式评价查询。不得把裸 Seq2Seq 结果作为本表最终 ROUGE；ROUGE-L 必须不低于 0.40。

**写入协议详见 §9**。

---

## 5. 状态机、字段映射与职责边界（摘要）

`summary_status` 只允许 `pending → processing → completed`、`processing → failed`、`failed → pending`。D 的 Worker 成功更新 summary、summary_time_ms、model_version、updated_at；失败更新 summary_error、summary_status、updated_at。C 不直接更新业务表，B 不修改新闻业务表，E 不读 MySQL。

API 映射：列表映射 `id/title/summary/category/source/publish_time/summary_status`；详情额外映射 `content/source_url/summary_time_ms` 与 A 的 `is_favorite/feedback`；模型指标映射 model_evaluations 除 id/created_at 外全部字段。完整 JSON 以 API.md 为准。

> **以下 §6-§10 是上述职责边界的运行时硬性细节**，本阶段结束后所有阶段 3+ 业务代码必须严格遵守。

---

## 6. 外键策略与级联规则

`favorites` 与 `feedback` 均通过 `news_id BIGINT UNSIGNED` 外键引用 `news_articles.id`。**本项目禁止直接 DELETE 新闻记录**（业务上无此场景：摘要失败可改 `summary_status='failed'` 不删新闻，爬虫重复通过 `content_hash` 唯一约束兜底），因此外键策略如下：

| 外键关系 | ON DELETE | ON UPDATE | 理由 |
|---|---|---|---|
| `favorites.news_id → news_articles.id` | `RESTRICT`（默认） | `RESTRICT`（默认） | 禁止物理删除新闻；新闻存在性是收藏/反馈成立的前提 |
| `feedback.news_id → news_articles.id` | `RESTRICT`（默认） | `RESTRICT`（默认） | 同上 |

**写入顺序硬性要求**：

| 操作 | 必须顺序 |
|---|---|
| `POST /favorites/{news_id}` | 先 `SELECT 1 FROM news_articles WHERE id=?` 验证存在，再 INSERT favorites；FK 兜底，违反返回 1452 SQLSTATE 时 Service 层捕获并抛 `BusinessError(1002, "新闻不存在")` |
| `POST /news/{news_id}/feedback` | 同上 |
| `POST /news/{news_id}/summary` | 同上 |
| `DELETE /favorites/{news_id}` | 无需先 SELECT 验证 news 存在；FK 不参与 DELETE |

**ORM 层处理**（阶段 3 由 A 实现）：`backend/app/services/user_service.py` 中对 INSERT favorites/feedback 的代码路径必须包 `try/except IntegrityError`，捕获 `pymysql.err.IntegrityError` 错误码 1452 后映射到 `BusinessError(1002)`；**不得让 SQLAlchemy 把 FK 错误冒泡为 500**。

**索引说明**：MySQL InnoDB 自动为外键列建索引（`fk_favorites_news_idx`、`fk_feedback_news_idx`），无需手动创建；`news_articles.id` 已是 PK，自动被引用。

---

## 7. client_id 与 X-Client-ID 映射

### 7.1 格式规范

- HTTP Header：`X-Client-ID: <UUID v4 标准字符串>`
- UUID v4 标准格式：`xxxxxxxx-xxxx-4xxx-yxxx-zzzzzzzzzzzz`（共 36 字符：32 位十六进制 + 4 个连字符；版本位固定为 `4`，变体位固定为 `8|9|a|b` 之一）
- DB 字段：`favorites.client_id`、`feedback.client_id` 均为 `VARCHAR(64) NOT NULL`，预留 28 字符冗余以兼容未来客户端 ID 扩展

### 7.2 规范化规则（强制）

**所有路径**（HTTP 入口 FastAPI dependency、Service 层、Repository 层）在使用 `client_id` 前必须经过 `normalize_client_id(raw: str) -> str` 一次规范化：

| 步骤 | 输入 → 输出 | 例 |
|---|---|---|
| 1. 两端去空白 | `"  abc  "` → `"abc"` | 客户端误带入空格 |
| 2. 统一小写 | `"ABC"` → `"abc"` | 防止 UUID 大小写误判 |
| 3. 长度校验 | 长度 ≠ 36 抛 `BusinessError(1001)` | 防 Header 截断或拼接 |
| 4. UUID v4 格式校验 | 不匹配正则抛 `BusinessError(1001)` | 防伪造 |

```python
# backend/app/dependencies.py（已实现，签名固定）
def parse_client_id(x_client_id: str | None = Header(None, alias="X-Client-ID")) -> str | None:
    """可选解析；非 None 时自动 normalize + 校验，失败抛 BusinessError(1001)。"""

def require_client_id(x_client_id: str = Header(..., alias="X-Client-ID")) -> str:
    """必填解析；缺失或非法均抛 BusinessError(1001)。"""
```

### 7.3 唯一性边界

| 字段 | 唯一性 | 含义 |
|---|---|---|
| `favorites (client_id, news_id)` | DB 唯一约束 | 同一客户端对同一新闻只能有一条收藏 |
| `feedback (client_id, news_id)` | DB 唯一约束 | 同一客户端对同一新闻只能有一条当前评价 |
| `client_id` 单独 | 不唯一 | 客户端 ID 由 HarmonyOS 自行生成；服务器不约束跨客户端/跨设备去重 |
| `client_id` 与用户实名 | 无关联 | 本项目无登录系统，`client_id` 即临时身份标识；不与真实账号绑定 |

### 7.4 缺失语义

| 端点 | 是否必填 | 缺失时 |
|---|---|---|
| `GET /api/news/{news_id}` | 可选 | `is_favorite=false`，`feedback=null`（API.md §6） |
| `POST /api/favorites/{news_id}` | **必填** | 400/1001 |
| `DELETE /api/favorites/{news_id}` | **必填** | 400/1001 |
| `POST /api/news/{news_id}/feedback` | **必填** | 400/1001 |
| `GET /api/favorites` | **必填** | 400/1001 |

由 `backend/app/dependencies.py:require_client_id` 在路由层统一拦截，Service 层拿到的已是规范化后的字符串。

---

## 8. summary_status 状态机

### 8.1 状态集合

`summary_status VARCHAR(20) NOT NULL`，取值固定为以下四个：

| 状态 | 含义 | 终态？ |
|---|---|---|
| `pending` | 已入库待摘要；可被 Worker 领取 | 否 |
| `processing` | 已被 Worker 领取；摘要生成中 | 否（30s 保护见 §8.4） |
| `completed` | 摘要生成成功并已持久化 | 是（除失败外不再迁移） |
| `failed` | 摘要生成失败，可重试 | 否 |

### 8.2 状态迁移图

```text
                ┌─────────────┐
   入库 INSERT  │   pending   │ ←─────────────┐
                └──────┬──────┘               │
                       │ Worker 原子领取        │
                       │ SummaryService        │
                       │ claim_pending()       │ Worker 原子重置
                       ▼                       │
                ┌─────────────┐               │
                │ processing  │               │
                └──┬──────┬───┘               │
       成功 ───────┘      └─────── 失败 ──────┐ │
              ▼                            ▼   │
       ┌─────────────┐               ┌─────────┴───┐
       │  completed  │               │   failed   │
       └─────────────┘               └──────┬─────┘
                                            │ 失败 → pending
                                            │ 由 E POST 或 Worker
                                            ▼
                                       (回到 pending)
```

### 8.3 迁移规则

| 迁移 | 触发方 | 原子性 | 伴随字段更新 |
|---|---|---|---|
| `pending → processing` | D Worker（`SummaryService.claim_pending`） | 必须是 `UPDATE ... WHERE id=? AND summary_status='pending'` 的 CAS；受影响行数=1 才视为成功，=0 则其他 Worker 已领取，本轮放弃 | `summary_status='processing'`、`updated_at=NOW()` |
| `processing → completed` | D Worker（`SummaryService.complete_summary`） | 必须在原 `processing` 行 UPDATE；CAS 失败（说明已被重置为 pending）记录警告 | `summary`、`summary_time_ms`、`model_version`、`summary_status='completed'`、`updated_at=NOW()` |
| `processing → failed` | D Worker 异常路径 | 同上 CAS | `summary_error`、`summary_status='failed'`、`updated_at=NOW()`；`summary`、`summary_time_ms`、`model_version` **保持原值或显式清空（由 D 决定，但写入协议必须固定）** |
| `failed → pending` | E POST `/news/{news_id}/summary` 或 Worker 失败重试 | CAS：`UPDATE ... WHERE id=? AND summary_status='failed'` | `summary_error=NULL`、可选清空 `summary`、`summary_time_ms`、`model_version`、`summary_status='pending'`、`updated_at=NOW()` |
| 任何 → `processing`（除 pending 外） | **禁止** | — | — |
| `completed → *` | **禁止**（除非人工干预；本项目不提供此接口） | — | — |
| `pending → failed` | **禁止**（Worker 领取失败才允许 writing failed） | — | — |

### 8.4 保护机制

- **Worker 并发保护**：`claim_pending` 使用 `SELECT ... FOR UPDATE SKIP LOCKED` 或单条 CAS UPDATE；同一新闻不会被两个 Worker 同时进入 processing。
- **processing 长时间未完成**：本项目不强制超时重置；如果 Worker 进程崩溃导致 processing 永久挂起，由运维或阶段 5 联调时人工修复。API.md §7 明确 E POST 在 processing 状态下不重复创建工作。
- **API 不允许直接修改 status**：所有状态迁移必须经 SummaryService 公共方法，**禁止** API Route 直接 `UPDATE news_articles SET summary_status=...`。
- **确定性永久不可处理**：正文超过冻结的 `max_input_tokens` 时 Pipeline 抛 `InputTooLongError`，该类文章重试必然复现。状态机无"永久跳过"终态（§8.1 固定四态），故 Worker 经 `SummaryService.delete_unprocessable` 删除该新闻及外键依赖行（favorites/feedback），**不得**标 failed——否则 `failed → pending` 重试形成死循环。

### 8.5 SQL CHECK 约束

`sql/create_database.sql` 已定义：

```sql
CONSTRAINT chk_news_summary_status CHECK (summary_status IN ('pending', 'processing', 'completed', 'failed'))
```

任何 Service 层 bug 写入非法值都会被 MySQL 拒绝（SQLSTATE 3819），由 `IntegrityError` 处理映射到 500/1005。

---

## 9. model_evaluations 写入协议

### 9.1 写入责任

| 项 | 责任方 |
|---|---|
| 主评价脚本产出真实指标 | B（`model_training/evaluate.py`） |
| Pipeline 配合（生成摘要用于 ROUGE） | C（`backend/app/ai/pipeline.py` 暴露给 B 的 evaluate 入口） |
| 字段填充与 INSERT | **A**（`backend/scripts/import_model_evaluation.py` 或 `model_training/scripts/persist_evaluation.py`，由 A 在阶段 5 实现） |
| 最新正式评价查询 | A（`backend/app/services/model_service.py:get_latest_metrics`） |

> **A 不参与训练也不参与评价主流程；A 仅承担"评价记录持久化"和"对外 metrics 查询"。**

### 9.2 触发时机

仅在 B 阶段 2 的某次正式 run **通过所有硬门槛**（见 9.3）时执行一次 INSERT。**不通过硬门槛的运行不写入数据库**——失败的运行只保留在 `runtime/training_runs/<run_id>/*.json` 离线记录中。

### 9.3 硬门槛（写入前的强制校验）

| 指标 | 阈值 | 来源 |
|---|---|---|
| `corpus_rougeL` | ≥ 0.40 | ARCHITECTURE.md §4 |
| `quality_pass_rate` | ≥ 0.95 | ARCHITECTURE.md §4 |
| `latency_pass_rate` | ≥ 0.95 | ARCHITECTURE.md §4 |
| `p95_generation_time_ms` | < 1500 | ARCHITECTURE.md §4 |

**任一不通过则拒绝写入并打印失败原因**；脚本非零退出。

### 9.4 字段填写规则

```python
# backend/scripts/import_model_evaluation.py 输入契约（伪代码）
def import_evaluation(run_dir: Path) -> int:
    """从 runtime/training_runs/<run_id>/evaluation.json 读取并写入 model_evaluations；返回新行 id。"""
    payload = json.loads((run_dir / "evaluation.json").read_text(encoding="utf-8"))

    # 字段映射规则
    row = {
        "model_version": payload["model_version"],                  # 与 SummaryResult.model_version 同源
        "model_name": payload["model_name"],
        "dataset": "CNewSum",                                       # 固定
        "dataset_split": "test",                                    # 固定
        "sample_count": int(payload["sample_count"]),
        "rouge1": float(payload["rouge1"]),                         # DECIMAL(7,6) 兼容
        "rouge2": float(payload["rouge2"]),
        "rougeL": float(payload["rougeL"]),
        "avg_generation_time_ms": int(payload["avg_generation_time_ms"]),
        "p95_generation_time_ms": int(payload["p95_generation_time_ms"]),
        "created_at": datetime.utcnow(),
    }

    # 硬门槛校验
    assert row["rougeL"] >= 0.40
    assert payload["quality_pass_rate"] >= 0.95                    # 来自 JSON，不入库
    assert payload["latency_pass_rate"] >= 0.95
    assert row["p95_generation_time_ms"] < 1500

    # INSERT
    with engine.begin() as conn:
        result = conn.execute(model_evaluations.insert().values(**row))
        return result.inserted_primary_key[0]
```

### 9.5 幂等与版本去重

- 同一 `(model_version, dataset, dataset_split)` 可存在多条历史记录（不同 run 的多次通过门槛的评价）。
- `GET /api/model/metrics` 按 `created_at DESC LIMIT 1` 取最新一条。
- 不为去重而删除历史记录。

### 9.6 失败重跑

- 若 INSERT 因 DB 错误失败，不得重试修改 `created_at`（按真实时间排序才有审计意义）；直接报错退出，由人工排查后再次调用脚本。

---

## 10. A/D 用户状态契约字段表

D 的新闻详情（API.md §6）需要输出 `is_favorite` 与 `feedback` 两个用户相关字段，**禁止 D 直接 SQL 查询 favorites/feedback 表**——必须通过 A 的 `UserService.get_news_user_state` 内部契约。下表是该契约的字段级硬性规范：

### 10.1 内部契约签名（冻结）

```python
UserService.get_news_user_state(db, client_id: str | None, news_id: int) -> dict
→ {"is_favorite": bool, "feedback": bool | None}
```

实现位置：`backend/app/services/user_service.py:get_news_user_state`，由 A 在阶段 3 实现。

### 10.2 字段映射表

| 输出字段 | 类型 | 取值规则 | 数据来源 |
|---|---|---|---|
| `is_favorite` | `bool` | `True` 当且仅当 `favorites` 表存在 `(client_id=传入值, news_id=传入值)` 的行 | `SELECT EXISTS (SELECT 1 FROM favorites WHERE client_id=? AND news_id=?)` |
| `feedback` | `bool \| None` | `client_id is None` → `None`；否则 `SELECT helpful FROM feedback WHERE client_id=? AND news_id=?`，无记录 → `None`，有记录 → 该记录的 `helpful` | `feedback` 表 |

### 10.3 三方字段对照

| 契约字段 | API.md §6 字段 | 来源层 | ORM 模型 | 数据库列 |
|---|---|---|---|---|
| `is_favorite`（bool） | `data.is_favorite`（bool） | `favorites` 表存在性 | `Favorite` 类 | `favorites.client_id`、`favorites.news_id` |
| `feedback`（bool \| None） | `data.feedback`（bool \| null） | `feedback` 表 `.helpful` | `Feedback` 类 | `feedback.client_id`、`feedback.news_id`、`feedback.helpful` |

### 10.4 调用顺序（D 集成时）

D 的 `/api/news/{news_id}` 实现必须按以下顺序执行：

1. D 自己的 `NewsService.get_by_id(news_id)`：取新闻记录（404/1002 在此处理）
2. **A 的 `UserService.get_news_user_state(db, client_id, news_id)`**：取用户状态
3. D 的 `NewsDetail` 构造：合并 1 和 2 的字段，输出 API.md §6 规定的 JSON

**禁止 D 直接构造 SQL 查询 favorites/feedback；禁止 D 在 NewsService 内复制 A 的查询逻辑**。

### 10.5 client_id 为 None 的语义

| 场景 | `is_favorite` | `feedback` |
|---|---|---|
| 无 X-Client-ID（用户未传） | `False` | `null` |
| X-Client-ID 合法但无对应收藏 | `False` | `null`（feedback 表也无记录时） |
| X-Client-ID 合法、有收藏无反馈 | `True` | `null` |
| X-Client-ID 合法、有反馈 | 取决于收藏是否存在 | 反馈记录中的 `helpful` 值 |

### 10.6 性能要求

`UserService.get_news_user_state` 应在 **一次数据库往返** 内完成（两条 SELECT，或一条 JOIN）。禁止在循环内 N+1 查询；禁止每详情请求都开新事务。

---

## 11. 与其他文档的引用关系

| 主题 | 主文档 | 本文档引用章节 |
|---|---|---|
| 字段语义、表结构、约束 | 本文件 §1-§4 | — |
| 角色 A 总任务 | `docs/ROLE_A_CHECKLIST.md` | 引用 A1-02 / A3-04 / A3-05 / A3-06 / A5-03 |
| 阶段 1 审计结论 | `docs/ROLE_A_AUDIT.md` | 本文档 §1-§4 审计对齐结论 |
| REST 契约 | `docs/API.md` | §10 引用 §6、§8 引用 §7 |
| 跨模块接口 | `docs/ARCHITECTURE.md` §7 | §10 引用 §7 的 `UserService.get_news_user_state` 签名 |
| 训练硬指标 | `docs/ARCHITECTURE.md` §4 + `docs/DEVELOPMENT_PLAN.md` | §9 引用 §4 的硬门槛 |
| 分类枚举 | `docs/API.md` §4 | §1 字段表引用六个固定分类 |

---

## 12. 变更控制

§1-§5 字段表如需变更，按 ARCHITECTURE.md §9 流程：先在本文件修订，再同步 `sql/create_database.sql` 与 `backend/app/models.py`；不得跳文档直接改代码。§6-§10 行为规则的修订同样需要全员确认。

违反本章冻结规则的代码改动视为架构越权；阶段 5 的 `PHASE5_DB_DIFF.md` 会逐条扫描并要求修复。

---

## 13. 可执行初始化脚本

| 文件 | 用途 |
|---|---|
| `sql/create_database.sql` | 冻结的最小 DDL（文档引用基准） |
| `sql/init_news_summary.sql` | **一键初始化完整脚本**：建库 + 建用户 + 授权 + 4 表 DDL（含全部约束/索引/COMMENT）+ 自检验证；可重复执行 |
| `scripts/init_database.ps1` | 上述 SQL 的**交互式封装**：自动定位 mysql.exe → 执行 DDL → 交互改密 → 生成 `backend/.env`（UTF-8 BOM，PS 5.1 兼容） |

队友接入流程（每人本地一份独立库）：

```bash
mysql -u root -p < sql/init_news_summary.sql
# 然后按脚本"第二部分"修改 news_app 密码，并同步到 backend/.env 的 DB_PASSWORD
```

连接参数：`Host=127.0.0.1`、`Port=3306`、`Database=news_summary`、`User=news_app`。

两份 DDL 的字段/约束语义必须保持一致；任何 Schema 变更先改本文件 §1-§4，再同步两个 SQL 与 `backend/app/models.py`。
