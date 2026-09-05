"""新闻摘要任务协调业务（D 维护）。

SummaryService 只负责摘要任务的状态机、事务、并发控制与持久化：
查询当前状态、处理 API 摘要请求、协助 Worker 原子领取 pending、接收 Worker
成功结果或失败信息并写库。本模块不得持有或调用 SummaryPipeline/BERT/TextRank，
摘要文本等由 Worker 调用 C 的 Pipeline 后以字段形式交回。

状态机：pending -> processing -> completed；processing -> failed -> pending。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.models import NewsArticle

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# 摘要任务状态常量
PENDING = "pending"
PROCESSING = "processing"
COMPLETED = "completed"
FAILED = "failed"


class SummaryService:
    """协调新闻记录状态与摘要生成结果。"""

    @staticmethod
    def _get(db: "Session", news_id: int) -> NewsArticle | None:
        return db.get(NewsArticle, news_id)

    @staticmethod
    def request_summary(db: "Session", news_id: int) -> dict | None:
        """处理 API 的摘要请求，返回统一结果，找不到新闻返回 None。

        语义：completed 原样返回缓存；processing 保持处理中；pending 仅确认；
        failed 原子重置为 pending 后返回。调用方据此决定 200/202 与返回体。
        """
        article = SummaryService._get(db, news_id)
        if article is None:
            return None
        if article.summary_status == FAILED:
            # 失败态允许重试：原子置回 pending
            article.summary_status = PENDING
            article.updated_at = datetime.now()
            db.commit()
        return {
            "news_id": article.id,
            "summary_status": article.summary_status,
            "summary": article.summary,
            "generation_time_ms": article.summary_time_ms,
        }

    @staticmethod
    def claim_pending(db: "Session") -> NewsArticle | None:
        """原子领取一条 pending 新闻并置为 processing；无待处理时返回 None。

        使用 SELECT ... FOR UPDATE SKIP LOCKED 保证并发下只有单个 Worker 领取到。
        """
        article = db.scalar(
            select(NewsArticle)
            .where(NewsArticle.summary_status == PENDING)
            .order_by(NewsArticle.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if article is None:
            return None
        article.summary_status = PROCESSING
        article.updated_at = datetime.now()
        db.commit()
        return article

    @staticmethod
    def complete(
        db: "Session",
        news_id: int,
        summary: str,
        generation_time_ms: int,
        model_version: str,
    ) -> None:
        """持久化成功摘要结果：summary、耗时、模型版本并置为 completed。"""
        article = SummaryService._get(db, news_id)
        if article is None:
            return
        article.summary = summary
        article.summary_time_ms = generation_time_ms
        article.model_version = model_version
        article.summary_status = COMPLETED
        article.summary_error = None
        article.updated_at = datetime.now()
        db.commit()

    @staticmethod
    def fail(db: "Session", news_id: int, error: str) -> None:
        """持久化失败原因并置为 failed，供后续重试重置为 pending。"""
        article = SummaryService._get(db, news_id)
        if article is None:
            return
        article.summary_error = error
        article.summary_status = FAILED
        article.updated_at = datetime.now()
        db.commit()
