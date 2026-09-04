# MySQL 数据库设计冻结

数据库为 `news_summary`，地址 `127.0.0.1:3306`，应用用户 `news_app`，字符集 `utf8mb4`；程序不用 root，密码只保存在 `backend/.env`。

| 表 | 字段与约束 |
|---|---|
| `news_articles` | `id` BIGINT UNSIGNED PK AI；`title` VARCHAR(255)、`content` MEDIUMTEXT、`category` VARCHAR(32)、`source` VARCHAR(64)、`source_url` VARCHAR(1024)、`content_hash` CHAR(64) 均非空，hash 唯一；`summary`、`publish_time`、`summary_time_ms`、`summary_error`、`model_version` 可空；`crawl_time`、`summary_status`、`created_at`、`updated_at` 非空。状态只能为 pending、processing、completed、failed；索引为 category、publish_time、summary_status。 |
| `favorites` | `id` BIGINT UNSIGNED PK AI；`client_id` VARCHAR(64)、`news_id` BIGINT UNSIGNED、`created_at` 非空；`(client_id,news_id)` 唯一，news_id 外键到 news_articles.id。 |
| `feedback` | `id` BIGINT UNSIGNED PK AI；`client_id`、`news_id`、`helpful` BOOLEAN、`created_at`、`updated_at` 非空；`(client_id,news_id)` 唯一，news_id 外键到 news_articles.id。 |
| `model_evaluations` | `id` BIGINT UNSIGNED PK AI；`model_version`、`model_name`、`dataset`、`dataset_split`、`sample_count`、`rouge1`、`rouge2`、`rougeL`、`avg_generation_time_ms`、`p95_generation_time_ms`、`created_at` 均非空；ROUGE 为 DECIMAL(7,6)，dataset 固定为 CNewSum。 |

DDL 位于 `sql/create_database.sql`，ORM 位于 `backend/app/models.py`，两者字段及约束必须同步修改且本阶段已一致。
