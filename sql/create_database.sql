CREATE DATABASE IF NOT EXISTS news_summary DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'news_app'@'localhost' IDENTIFIED BY 'CHANGE_ME';
CREATE USER IF NOT EXISTS 'news_app'@'127.0.0.1' IDENTIFIED BY 'CHANGE_ME';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES ON news_summary.* TO 'news_app'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES ON news_summary.* TO 'news_app'@'127.0.0.1';
FLUSH PRIVILEGES;
USE news_summary;

CREATE TABLE IF NOT EXISTS news_articles (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT, title VARCHAR(255) NOT NULL, content MEDIUMTEXT NOT NULL,
  summary TEXT NULL, category VARCHAR(32) NOT NULL, source VARCHAR(64) NOT NULL, source_url VARCHAR(1024) NOT NULL,
  content_hash CHAR(64) NOT NULL UNIQUE, publish_time DATETIME NULL, crawl_time DATETIME NOT NULL,
  summary_status VARCHAR(20) NOT NULL, summary_time_ms INT NULL, summary_error TEXT NULL, model_version VARCHAR(64) NULL,
  created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
  CONSTRAINT chk_news_summary_status CHECK (summary_status IN ('pending', 'processing', 'completed', 'failed')),
  INDEX ix_news_articles_category (category), INDEX ix_news_articles_publish_time (publish_time), INDEX ix_news_articles_summary_status (summary_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS favorites (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT, client_id VARCHAR(64) NOT NULL, news_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME NOT NULL, CONSTRAINT uq_favorites_client_news UNIQUE (client_id, news_id),
  CONSTRAINT fk_favorites_news FOREIGN KEY (news_id) REFERENCES news_articles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS feedback (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT, client_id VARCHAR(64) NOT NULL, news_id BIGINT UNSIGNED NOT NULL,
  helpful BOOLEAN NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
  CONSTRAINT uq_feedback_client_news UNIQUE (client_id, news_id),
  CONSTRAINT fk_feedback_news FOREIGN KEY (news_id) REFERENCES news_articles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS model_evaluations (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT, model_version VARCHAR(64) NOT NULL, model_name VARCHAR(255) NOT NULL,
  dataset VARCHAR(64) NOT NULL, dataset_split VARCHAR(32) NOT NULL, sample_count INT NOT NULL,
  rouge1 DECIMAL(7,6) NOT NULL, rouge2 DECIMAL(7,6) NOT NULL, rougeL DECIMAL(7,6) NOT NULL,
  avg_generation_time_ms INT NOT NULL, p95_generation_time_ms INT NOT NULL, created_at DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- TODO(A-阶段1)：执行前将两个 CHANGE_ME 替换为本机强密码；输入为仅本机使用的数据库密码，输出为 news_app 应用账户，必须遵守 backend/.env.example，禁止提交真实密码。
