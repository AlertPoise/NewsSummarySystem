-- ============================================================================
-- 新闻文章自动摘要系统 —— MySQL 一键初始化脚本
--
-- 文件     : sql/init_news_summary.sql
-- 规范来源 : docs/DATABASE.md（冻结规范；字段/约束语义以该文件为准）
-- 适用版本 : MySQL 8.0.16+（CHECK 约束需 8.0.16 起强制执行）
-- 字符集   : utf8mb4 / utf8mb4_unicode_ci
--
-- 用法（在本机执行，需要 root 权限）:
--   mysql -u root -p < sql/init_news_summary.sql
--
-- 说明:
--   1. 本脚本可重复执行（所有对象均为 IF NOT EXISTS），不会破坏已有数据。
--   2. 应用账户初始密码为 CHANGE_ME，执行后必须按文末"第二部分"改为强密码。
--   3. 业务代码一律通过 news_app 账户连接，禁止使用 root（DATABASE.md 头部约定）。
--   4. 若 news_app 已存在，CREATE USER IF NOT EXISTS 不会重置密码，
--      改密请直接使用文末 ALTER USER 语句。
-- ============================================================================

SET NAMES utf8mb4;

-- ----------------------------------------------------------------------------
-- 第一部分：建库 + 应用账户 + 授权
-- ----------------------------------------------------------------------------

CREATE DATABASE IF NOT EXISTS news_summary
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

-- news_app 仅允许本机连接；localhost 与 127.0.0.1 在 MySQL 中是两个账户，各建一份
CREATE USER IF NOT EXISTS 'news_app'@'localhost' IDENTIFIED BY 'CHANGE_ME';
CREATE USER IF NOT EXISTS 'news_app'@'127.0.0.1' IDENTIFIED BY 'CHANGE_ME';

-- 授权范围与 sql/create_database.sql 冻结版保持一致
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
  ON news_summary.* TO 'news_app'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
  ON news_summary.* TO 'news_app'@'127.0.0.1';

FLUSH PRIVILEGES;

USE news_summary;

-- ----------------------------------------------------------------------------
-- 表 1/4：news_articles —— 新闻文章主表
-- 写入角色：D 的 NewsService 入库；D Worker 更新摘要字段（DATABASE.md §1）
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS news_articles (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '新闻唯一标识',
  title           VARCHAR(255)    NOT NULL                COMMENT '真实新闻标题',
  content         MEDIUMTEXT      NOT NULL                COMMENT '去噪后的真实正文；列表接口禁止返回',
  summary         TEXT            NULL                    COMMENT 'Worker 持久化的最终摘要；入库时必须为 NULL',
  category        VARCHAR(32)     NOT NULL                COMMENT '固定六类：科技/财经/社会/体育/国内/国际（Service 层校验）',
  source          VARCHAR(64)     NOT NULL                COMMENT '真实来源名称',
  source_url      VARCHAR(1024)   NOT NULL                COMMENT '新闻原始 URL',
  content_hash    CHAR(64)        NOT NULL                COMMENT 'content 的 SHA-256 十六进制值；入库幂等去重依据',
  publish_time    DATETIME        NULL                    COMMENT '来源声明的发布时间；无法可靠获取时为 NULL',
  crawl_time      DATETIME        NOT NULL                COMMENT 'Crawler 实际采集成功时间（不等于 created_at）',
  summary_status  VARCHAR(20)     NOT NULL                COMMENT '摘要任务状态机，见 DATABASE.md §8',
  summary_time_ms INT             NULL                    COMMENT '完整 Pipeline 生成耗时（毫秒）',
  summary_error   TEXT            NULL                    COMMENT '最近一次失败原因；仅内部诊断，不对客户端暴露',
  model_version   VARCHAR(64)     NULL                    COMMENT '生成该摘要的正式模型版本',
  created_at      DATETIME        NOT NULL                COMMENT '记录创建时间',
  updated_at      DATETIME        NOT NULL                COMMENT '记录最后修改时间',
  PRIMARY KEY (id),
  UNIQUE KEY uq_news_articles_content_hash (content_hash),
  KEY ix_news_articles_category (category),
  KEY ix_news_articles_publish_time (publish_time),
  KEY ix_news_articles_summary_status (summary_status),
  CONSTRAINT chk_news_summary_status
    CHECK (summary_status IN ('pending', 'processing', 'completed', 'failed'))
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
  COMMENT = '新闻文章主表（D 写入，Worker 更新摘要字段，状态机见 DATABASE.md §8）';

-- ----------------------------------------------------------------------------
-- 表 2/4：favorites —— 用户收藏表
-- 写入角色：A 独占读写（DATABASE.md §2）；幂等语义：
--   POST   已存在 -> 不报错，返回 is_favorite=true
--   DELETE 不存在 -> 不报错，返回 is_favorite=false
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS favorites (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '收藏记录标识',
  client_id  VARCHAR(64)     NOT NULL                COMMENT '客户端标识（UUID v4，统一小写，见 DATABASE.md §7）',
  news_id    BIGINT UNSIGNED NOT NULL                COMMENT '被收藏新闻 id，指向 news_articles.id',
  created_at DATETIME        NOT NULL                COMMENT '首次成功收藏时间',
  PRIMARY KEY (id),
  UNIQUE KEY uq_favorites_client_news (client_id, news_id),
  CONSTRAINT fk_favorites_news
    FOREIGN KEY (news_id) REFERENCES news_articles (id)
    ON DELETE RESTRICT
    ON UPDATE RESTRICT
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
  COMMENT = '用户收藏表（A 独占读写；唯一约束 client_id+news_id 保证幂等）';

-- ----------------------------------------------------------------------------
-- 表 3/4：feedback —— 用户摘要反馈表
-- 写入角色：A 独占读写（DATABASE.md §3）；写入时序硬性要求：
--   先 SELECT 判断是否存在 -> 存在则 UPDATE helpful/updated_at（created_at 不变）
--                         -> 不存在则 INSERT
--   禁止 INSERT ... ON DUPLICATE KEY UPDATE（会覆盖 created_at）
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS feedback (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '反馈记录标识',
  client_id  VARCHAR(64)     NOT NULL                COMMENT '客户端标识（UUID v4，统一小写）',
  news_id    BIGINT UNSIGNED NOT NULL                COMMENT '被评价新闻 id，指向 news_articles.id',
  helpful    BOOLEAN         NOT NULL                COMMENT 'true=有帮助；false=不准确',
  created_at DATETIME        NOT NULL                COMMENT '首次评价时间（UPDATE 路径不可覆盖）',
  updated_at DATETIME        NOT NULL                COMMENT '最后一次评价更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uq_feedback_client_news (client_id, news_id),
  CONSTRAINT fk_feedback_news
    FOREIGN KEY (news_id) REFERENCES news_articles (id)
    ON DELETE RESTRICT
    ON UPDATE RESTRICT
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
  COMMENT = '用户摘要反馈表（A 独占读写；先 SELECT 后 INSERT/UPDATE）';

-- ----------------------------------------------------------------------------
-- 表 4/4：model_evaluations —— 模型评价记录表
-- 写入角色：A 按 B/C 交付的评价结果持久化（DATABASE.md §9）
--   仅在训练 run 通过全部硬门槛后 INSERT 一条：
--     corpus_rougeL >= 0.40, quality_pass_rate >= 0.95,
--     latency_pass_rate >= 0.95, p95_generation_time_ms < 1500
--   quality_pass_rate / latency_pass_rate 只写离线 JSON，不入本表。
--   metrics API 取数规则：ORDER BY created_at DESC LIMIT 1（表数据量小，无需额外索引）
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS model_evaluations (
  id                     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '评价记录标识',
  model_version          VARCHAR(64)     NOT NULL                COMMENT '与 SummaryResult.model_version 同一版本体系',
  model_name             VARCHAR(255)    NOT NULL                COMMENT '正式摘要模型名称',
  dataset                VARCHAR(64)     NOT NULL                COMMENT '固定 CNewSum',
  dataset_split          VARCHAR(32)     NOT NULL                COMMENT '固定 test',
  sample_count           INT             NOT NULL                COMMENT '本次评价样本数',
  rouge1                 DECIMAL(7,6)    NOT NULL                COMMENT '完整 Pipeline ROUGE-1',
  rouge2                 DECIMAL(7,6)    NOT NULL                COMMENT '完整 Pipeline ROUGE-2',
  rougeL                 DECIMAL(7,6)    NOT NULL                COMMENT '完整 Pipeline ROUGE-L（硬门槛 >= 0.40）',
  avg_generation_time_ms INT             NOT NULL                COMMENT '预热后 batch_size=1 平均耗时（毫秒）',
  p95_generation_time_ms INT             NOT NULL                COMMENT '相同规则 P95 耗时（硬门槛 < 1500）',
  created_at             DATETIME        NOT NULL                COMMENT '评价记录创建时间（按真实时间排序）',
  PRIMARY KEY (id)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
  COMMENT = '模型评价记录表（A 持久化 B/C 交付的正式评价结果）';

-- ----------------------------------------------------------------------------
-- 第二部分：修改应用账户密码（建库后必做，手动执行）
--
-- 把 <强密码> 替换为本机自定义密码，取消注释后单独执行；
-- 该密码同步写入 backend/.env 的 DB_PASSWORD（.env 不入 Git）。
-- ----------------------------------------------------------------------------

-- ALTER USER 'news_app'@'localhost' IDENTIFIED BY '<强密码>';
-- ALTER USER 'news_app'@'127.0.0.1' IDENTIFIED BY '<强密码>';
-- FLUSH PRIVILEGES;

-- ----------------------------------------------------------------------------
-- 第三部分：自检验证（执行后人工核对输出）
-- ----------------------------------------------------------------------------

-- 3.1 MySQL 版本：需 >= 8.0.16，否则 CHECK 约束不生效
SELECT VERSION() AS mysql_version;

-- 3.2 表数量：应等于 4
SELECT COUNT(*) AS table_count
  FROM information_schema.tables
 WHERE table_schema = 'news_summary';

-- 3.3 约束清单：应包含 2 个外键 + 3 个唯一键 + 1 个 CHECK
--     fk_favorites_news / fk_feedback_news
--     uq_news_articles_content_hash / uq_favorites_client_news / uq_feedback_client_news
--     chk_news_summary_status
SELECT table_name, constraint_name, constraint_type
  FROM information_schema.table_constraints
 WHERE table_schema = 'news_summary'
 ORDER BY table_name, constraint_type;

-- 3.4 应用账户连通性（另开终端执行，密码用第二部分改后的值）：
--     mysql -h 127.0.0.1 -P 3306 -u news_app -p news_summary -e "SHOW TABLES;"
--
-- 连接参数（给队友的连接卡）：
--   Host = 127.0.0.1   Port = 3306   Database = news_summary   User = news_app
