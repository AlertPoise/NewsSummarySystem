"""客户端收藏与反馈业务（阶段 3 A3-01~05 实现）。

本模块在阶段 1 公共层冻结基础上实现角色 A 的全部用户业务。遵循：
- docs/DATABASE.md §2 favorites：唯一约束 (client_id, news_id)，POST 幂等，
  DELETE 受影响行数 0/1 均视为成功；含 §6 FK 兜底（news 不存在 → 1002）。
- docs/DATABASE.md §3 feedback：先 SELECT 再 INSERT/UPDATE，created_at 不变，
  禁止 INSERT ... ON DUPLICATE KEY UPDATE。
- docs/DATABASE.md §6 ORM 层处理：INSERT 路径必须 try/except IntegrityError
  并把 1452 SQLSTATE 映射到 BusinessError(1002)。
- docs/DATABASE.md §7 client_id：dependencies 层已规范化（小写/36字符/UUID v4）。
- docs/DATABASE.md §10.1 + docs/ARCHITECTURE.md §7：A3-05 get_news_user_state
  冻结内部契约，D 必须复用，禁止复制查询逻辑。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import not_found
from app.models import Favorite, Feedback, NewsArticle


def _utcnow_naive() -> datetime:
    """朴素 UTC 时间（无 tzinfo），用于 DATETIME 列写入。

    显式去掉 tzinfo，避免 MySQL DATETIME 列（无时区）在接收 aware datetime 时
    因 SQLAlchemy/PyMySQL 版本不同出现存值偏移；同时规避 Python 3.12+
    对 datetime.utcnow() 的 DeprecationWarning。
    """

    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserService:
    """封装基于客户端标识的收藏与摘要反馈业务。"""

    @staticmethod
    def add_favorite(db: Session, *, client_id: str, news_id: int) -> dict[str, Any]:
        """A3-01 幂等收藏：重复 POST 仍返回 is_favorite=True，记录不增加。

        实现策略（DATABASE.md §2 允许）：
        1. 先 SELECT 1 FROM news_articles WHERE id=? 兜底 FK；
        2. INSERT IGNORE 等价物（依赖 IntegrityError 捕获）保证唯一约束幂等；
        3. favorites 表无 updated_at 字段，不存在"created_at 被覆盖"风险。
        """

        # 1. 新闻存在性预检（DATABASE.md §6）
        if not db.scalar(select(exists().where(NewsArticle.id == news_id))):
            raise not_found("新闻不存在")

        # 2. INSERT；唯一约束命中走 except 分支
        db.add(
            Favorite(
                client_id=client_id,
                news_id=news_id,
                created_at=_utcnow_naive(),
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # 唯一约束命中视为幂等成功（DBA §2）；FK 1452 在前置 SELECT 下不应触发
        return {"news_id": news_id, "is_favorite": True}

    @staticmethod
    def remove_favorite(db: Session, *, client_id: str, news_id: int) -> dict[str, Any]:
        """A3-02 幂等取消：无记录时仍返回 is_favorite=False。

        DELETE 不需要前置 SELECT news_articles（DATABASE.md §6）。
        受影响行数 0/1 均视为成功。
        """

        db.execute(
            delete(Favorite).where(
                Favorite.client_id == client_id,
                Favorite.news_id == news_id,
            )
        )
        db.commit()
        return {"news_id": news_id, "is_favorite": False}

    @staticmethod
    def list_favorites(db: Session, *, client_id: str) -> list[dict[str, Any]]:
        """A3-03 收藏列表：仅返回该客户端的收藏，不含 content（API.md §8）。

        排序：favorites.created_at DESC, favorites.id DESC，确保稳定分页。
        """

        rows = (
            db.execute(
                select(NewsArticle)
                .join(Favorite, Favorite.news_id == NewsArticle.id)
                .where(Favorite.client_id == client_id)
                .order_by(Favorite.created_at.desc(), Favorite.id.desc())
            )
            .scalars()
            .all()
        )
        items: list[dict[str, Any]] = []
        for n in rows:
            items.append(
                {
                    "id": n.id,
                    "title": n.title,
                    "summary": n.summary,
                    "category": n.category,
                    "source": n.source,
                    "publish_time": n.publish_time,
                    "summary_status": n.summary_status,
                }
            )
        return items

    @staticmethod
    def upsert_feedback(
        db: Session,
        *,
        client_id: str,
        news_id: int,
        helpful: bool,
    ) -> dict[str, Any]:
        """A3-04 摘要反馈：首次 INSERT，后续 UPDATE（created_at 不变）。

        写入时序硬性要求（DATABASE.md §3）：
        1. 先 SELECT 验证 news 存在（FK 兜底）；
        2. 再 SELECT 1 检查 (client_id, news_id) 是否存在；
        3. 存在 → UPDATE helpful/updated_at（created_at 保留）；不存在 → INSERT。
        4. 禁止使用 INSERT ... ON DUPLICATE KEY UPDATE（会覆盖 created_at）。
        """

        # 1. 新闻存在性预检
        if not db.scalar(select(exists().where(NewsArticle.id == news_id))):
            raise not_found("新闻不存在")

        # 2. 先 SELECT 检查是否已有反馈（DATABASE.md §3 硬性要求）
        existing = db.scalar(
            select(Feedback).where(
                Feedback.client_id == client_id,
                Feedback.news_id == news_id,
            )
        )
        now = _utcnow_naive()

        if existing is None:
            db.add(
                Feedback(
                    client_id=client_id,
                    news_id=news_id,
                    helpful=helpful,
                    created_at=now,
                    updated_at=now,
                )
            )
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                # 并发 INSERT 触发唯一约束 / FK 错误均落到此处；
                # FK 1452 视为新闻不存在（前置 SELECT 与并发 INSERT 之间的 race）
                raise not_found("新闻不存在")
        else:
            existing.helpful = helpful
            existing.updated_at = now
            db.commit()

        return {"news_id": news_id, "helpful": helpful}

    @staticmethod
    def get_news_user_state(
        db: Session,
        client_id: str | None,
        news_id: int,
    ) -> dict[str, Any]:
        """A3-05 冻结内部契约（ARCHITECTURE.md §7 + DATABASE.md §10.1）。

        返回 ``{"is_favorite": bool, "feedback": bool | None}``，供 D 在
        GET /api/news/{news_id} 合并用户状态使用，禁止 D 复制 favorites/feedback
        查询逻辑。

        client_id=None（无 Header）时：is_favorite=False, feedback=None（API.md §6）。
        数据库一次往返：两条独立 SELECT（DATABASE.md §10.6 允许）。
        """

        if client_id is None:
            return {"is_favorite": False, "feedback": None}

        is_fav = bool(
            db.scalar(
                select(
                    exists().where(
                        Favorite.client_id == client_id,
                        Favorite.news_id == news_id,
                    )
                )
            )
        )
        fb_value = db.scalar(
            select(Feedback.helpful).where(
                Feedback.client_id == client_id,
                Feedback.news_id == news_id,
            )
        )
        return {"is_favorite": is_fav, "feedback": fb_value}