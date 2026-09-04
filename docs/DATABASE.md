# MySQL 数据库冻结规范

数据库固定为 `news_summary`，MySQL 8.x，地址 `127.0.0.1:3306`，应用用户 `news_app`，字符集 `utf8mb4`。应用程序不得使用 root；密码仅在本机 `.env`，不得提交 Git。A 维护 Schema、公共连接约定和一致性；本文件是字段语义的最终规范。

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

## 2. favorites

| 字段 | 类型/可空 | 含义与默认语义 | 写入角色 | 读取角色/API |
|---|---|---|---|---|
| id | BIGINT UNSIGNED，非空，PK AI | 收藏记录标识 | MySQL | A；内部 |
| client_id | VARCHAR(64)，非空 | HarmonyOS 生成的 UUID v4 | A | A；按客户端隔离 |
| news_id | BIGINT UNSIGNED，非空，FK | 被收藏的 news_articles.id | A | A/D；收藏/详情 |
| created_at | DATETIME，非空 | 首次成功收藏时间 | A | A；审计 |

唯一约束 `(client_id, news_id)`；news_id 外键指向 news_articles.id。A 实现插入和删除；D 只能经 `UserService.get_news_user_state` 读取详情状态；E 仅经 REST 访问。

## 3. feedback

| 字段 | 类型/可空 | 含义与默认语义 | 写入角色 | 读取角色/API |
|---|---|---|---|---|
| id | BIGINT UNSIGNED，非空，PK AI | 反馈记录标识 | MySQL | A；内部 |
| client_id | VARCHAR(64)，非空 | UUID v4 客户端标识 | A | A；按客户端隔离 |
| news_id | BIGINT UNSIGNED，非空，FK | 被评价新闻 | A | A/D；详情/反馈 |
| helpful | BOOLEAN，非空 | true 为有帮助，false 为不准确 | A | A/D/E；详情/反馈 |
| created_at | DATETIME，非空 | 首次评价时间 | A | A；审计 |
| updated_at | DATETIME，非空 | 最后一次评价更新时间 | A | A；审计 |

唯一约束 `(client_id, news_id)`；首次反馈 INSERT，后续 UPDATE。该表收集离线分析、重新训练和优化的输入，不触发在线训练。

## 4. model_evaluations

| 字段 | 类型/可空 | 含义与默认语义 | 写入角色 | 读取角色/API |
|---|---|---|---|---|
| id | BIGINT UNSIGNED，非空，PK AI | 评价记录标识 | MySQL | A；内部 |
| model_version | VARCHAR(64)，非空 | 与 SummaryResult.model_version 同一版本体系 | A（按B/C交付） | A/E；metrics |
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

B 负责训练和评价主流程，C 提供完整在线 Pipeline 配合，A 按固定字段持久化并提供最新正式评价查询。不得把裸 Seq2Seq 结果作为本表最终 ROUGE；ROUGE-L 必须不低于 0.40。

## 5. 状态机、字段映射与职责边界

`summary_status` 只允许 `pending → processing → completed`、`processing → failed`、`failed → pending`。D 的 Worker 成功更新 summary、summary_time_ms、model_version、updated_at；失败更新 summary_error、summary_status、updated_at。C 不直接更新业务表，B 不修改新闻业务表，E 不读 MySQL。

API 映射：列表映射 `id/title/summary/category/source/publish_time/summary_status`；详情额外映射 `content/source_url/summary_time_ms` 与 A 的 `is_favorite/feedback`；模型指标映射 model_evaluations 除 id/created_at 外全部字段。完整 JSON 以 API.md 为准。
