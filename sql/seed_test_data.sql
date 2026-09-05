-- 端到端验证灌料脚本：插入 1 条新闻 + 1 条模型评价，供 scripts/run_e2e.ps1 校验使用。
-- 与 backend/app/services/model_service.py:SampleNewsPayload 的字段保持一致（纯字段灌入）。
-- 来源表：DATABASE.md 1-5 节；写入角色：D / A。

USE news_summary;

-- 1) 先清子表（feedback / favorites），再清父表（news_articles / model_evaluations）。
--   否则上一轮 run_e2e.ps1 残留的 favorites/feedback 行引用着 seed 新闻，
--   DELETE news_articles 会触发 FK 约束 → mysql 退出非零 → seed FAIL。
DELETE FROM feedback
  WHERE news_id IN (
    SELECT id FROM news_articles
     WHERE content_hash = SHA2('seed_test_article_content', 256)
  );
DELETE FROM favorites
  WHERE news_id IN (
    SELECT id FROM news_articles
     WHERE content_hash = SHA2('seed_test_article_content', 256)
  );
DELETE FROM model_evaluations WHERE sample_count = 1000 AND dataset = 'CNewSum';
DELETE FROM news_articles WHERE content_hash = SHA2('seed_test_article_content', 256);

-- 2) 灌一条新闻（id 走 AUTO_INCREMENT）
INSERT INTO news_articles
  (title, content, summary, category, source, source_url, content_hash,
   publish_time, crawl_time, summary_status, summary_time_ms, summary_error,
   model_version, created_at, updated_at)
VALUES
  ('Seed 验证新闻',
   REPEAT('x', 200),
   '这是一条供 scripts/run_e2e.ps1 用的种子新闻，用于校验 GET /api/news 与 5 路由端到端',
   '科技',
   'seed-source',
   'https://example.invalid/seed/news/1',
   SHA2('seed_test_article_content', 256),
   '2026-09-05 10:00:00', '2026-09-05 10:00:00',
   'completed', 860, NULL, 'v1.0.0-seed',
   '2026-09-05 10:00:00', '2026-09-05 10:00:00');

-- 3) 灌一条模型评价
INSERT INTO model_evaluations
  (model_version, model_name, dataset, dataset_split, sample_count,
   rouge1, rouge2, rougeL, avg_generation_time_ms, p95_generation_time_ms, created_at)
VALUES
  ('v1.0.0-seed', 'news_summarizer_seed', 'CNewSum', 'test', 1000,
   0.500000, 0.300000, 0.450000, 900, 1400, '2026-09-05 12:00:00');

-- 4) 顺手验证两条记录确实在
SELECT COUNT(*) AS news_seeded FROM news_articles WHERE content_hash = SHA2('seed_test_article_content', 256);
SELECT COUNT(*) AS metrics_seeded FROM model_evaluations WHERE sample_count = 1000 AND dataset = 'CNewSum';
