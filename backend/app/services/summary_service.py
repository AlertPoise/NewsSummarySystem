"""新闻摘要任务协调业务（D 维护）。

SummaryService 只负责摘要任务的状态机、事务、并发控制与持久化：
查询当前状态、处理 API 摘要请求、协助 Worker 原子领取 pending、接收 Worker
成功结果或失败信息并写库。本模块不得持有或调用 SummaryPipeline/BERT/TextRank，
摘要文本等由 Worker 调用 C 的 Pipeline 后以字段形式交回。

状态机：pending -> processing -> completed；processing -> failed -> pending。
所有迁移按 docs/DATABASE.md §8.3 使用 CAS 条件更新：仅当行处于预期来源状态时
才写入，CAS 失败记录警告且不覆盖，禁止产生状态机之外的迁移。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete, select, update

from app.exceptions import state_conflict
from app.models import Favorite, Feedback, NewsArticle

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# CAS 失败按 DATABASE.md §8.3 要求记录警告
logger = logging.getLogger(__name__)

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
        failed 按 §8.3 以 CAS 原子重置为 pending 并清空 summary_error 后返回。
        调用方据此决定 200/202 与返回体。
        """
        article = SummaryService._get(db, news_id)
        if article is None:
            return None
        if article.summary_status == FAILED:
            # 失败态允许重试：CAS UPDATE ... WHERE summary_status='failed'，
            # 伴随字段固定清空 summary_error（DATABASE.md §8.3）
            result = db.execute(
                update(NewsArticle)
                .where(
                    NewsArticle.id == news_id,
                    NewsArticle.summary_status == FAILED,
                )
                .values(
                    summary_status=PENDING,
                    summary_error=None,
                    updated_at=datetime.now(),
                )
            )
            db.commit()
            if result.rowcount == 1:
                db.refresh(article)
            else:
                # CAS 失败：状态已被并发迁移（另一请求已重置或 Worker 已领取），
                # 按当前实际状态幂等返回，不重复创建摘要工作；若读回仍是
                # failed，说明并发竞争未收敛，按 API.md §7 返回 409/1003
                article = SummaryService._get(db, news_id)
                if article is None:
                    return None
                db.refresh(article)
                if article.summary_status == FAILED:
                    raise state_conflict("摘要状态并发变更，请稍后重试")
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
        """持久化成功摘要结果：summary、耗时、模型版本并置为 completed。

        按 DATABASE.md §8.3 使用 CAS：仅当行仍处于 processing 时写入；
        CAS 失败说明行已被并发迁移（如已被重置为 pending），记录警告且
        不覆盖，避免产生 completed -> failed 等状态机禁止的迁移。
        """
        result = db.execute(
            update(NewsArticle)
            .where(
                NewsArticle.id == news_id,
                NewsArticle.summary_status == PROCESSING,
            )
            .values(
                summary=summary,
                summary_time_ms=generation_time_ms,
                model_version=model_version,
                summary_status=COMPLETED,
                summary_error=None,
                updated_at=datetime.now(),
            )
        )
        db.commit()
        if result.rowcount != 1:
            logger.warning(
                "摘要完成 CAS 失败：news_id=%s 已不处于 processing，跳过写入（DATABASE.md §8.3）",
                news_id,
            )

    @staticmethod
    def fail(db: "Session", news_id: int, error: str) -> None:
        """持久化失败原因并置为 failed，供后续重试重置为 pending。

        按 DATABASE.md §8.3 使用 CAS：仅当行仍处于 processing 时写入；
        CAS 失败记录警告且不写入，防止把已 completed 的行非法回退为 failed。
        写入协议固定：summary、summary_time_ms、model_version 保持原值
        （§8.3 允许由 D 固定），仅更新 summary_error、summary_status、updated_at。
        """
        result = db.execute(
            update(NewsArticle)
            .where(
                NewsArticle.id == news_id,
                NewsArticle.summary_status == PROCESSING,
            )
            .values(
                summary_error=error,
                summary_status=FAILED,
                updated_at=datetime.now(),
            )
        )
        db.commit()
        if result.rowcount != 1:
            logger.warning(
                "摘要失败 CAS 失败：news_id=%s 已不处于 processing，跳过写入（DATABASE.md §8.3）",
                news_id,
            )

    @staticmethod
    def delete_unprocessable(db: "Session", news_id: int) -> int:
        """永久删除确定性不可摘要的新闻（如正文超过 max_input_tokens）。

        冻结状态机（DATABASE.md §8.1 固定四态 + CHECK 约束）没有"永久跳过"
        终态：标 failed 会被 request_summary 重置回 pending 形成永久重试循环，
        标 completed 属于伪造摘要，因此唯一不破坏状态机的处理是删除该新闻。
        favorites/feedback 对 news_articles 为 RESTRICT 外键，必须先删依赖行
        再删新闻行。仅当行仍处于 processing（Worker 刚领取）时执行删除，CAS
        失败记录警告且不删（processing 只会由持有它的 Worker 自身迁移，此
        分支仅作并发防御）。返回删除的收藏/反馈条数。
        """
        dependents = db.execute(
            delete(Favorite).where(Favorite.news_id == news_id)
        ).rowcount
        dependents += db.execute(
            delete(Feedback).where(Feedback.news_id == news_id)
        ).rowcount
        result = db.execute(
            delete(NewsArticle).where(
                NewsArticle.id == news_id,
                NewsArticle.summary_status == PROCESSING,
            )
        )
        db.commit()
        if result.rowcount != 1:
            logger.warning(
                "删除不可摘要新闻 CAS 失败：news_id=%s 已不处于 processing，跳过删除",
                news_id,
            )
        return dependents
