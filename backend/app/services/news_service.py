"""新闻查询与入库业务（D 维护）。

职责：RawArticle 入库前的六类校验与 SHA-256 去重、新闻入库、固定六类分类查询、
分页查询、详情查询。详情所需的用户状态（收藏/反馈）一律经 A 的
UserService.get_news_user_state 获取，不在此重写收藏/反馈查询。
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.crawlers.base import RawArticle
from app.models import NewsArticle
from app.news_categories import SIX_CATEGORIES, is_valid_category

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# 默认分页参数（与 API.md 一致）
_DEFAULT_PAGE = 1
_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 50


class NewsService:
    """封装新闻分类、查询、分页、去重与入库业务。"""

    @staticmethod
    def list_categories() -> list[str]:
        """返回固定六类分类，不随数据库内容变化。"""
        return list(SIX_CATEGORIES)

    @staticmethod
    def content_sha256(content: str) -> str:
        """对正文计算 SHA-256 十六进制值，用于去重。"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def save_article(db: "Session", raw: RawArticle) -> tuple[NewsArticle, bool]:
        """把一个真实新闻写入 news_articles。

        入库前完成六类校验与按 content_hash 去重：
        已存在则直接返回已有记录且 created=False，不产生重复行；
        首次写入返回新记录且 created=True。依赖数据库唯一约束兜底并发重复。
        """
        if not is_valid_category(raw.category):
            raise ValueError(f"分类不在系统六类内：{raw.category}")
        if not raw.title.strip() or not raw.content.strip():
            raise ValueError("新闻标题或正文不能为空")
        if not raw.source_url.strip():
            raise ValueError("新闻来源 URL 不能为空")

        content_hash = NewsService.content_sha256(raw.content)
        existing = db.scalar(
            select(NewsArticle).where(NewsArticle.content_hash == content_hash)
        )
        if existing is not None:
            return existing, False

        now = datetime.now()
        article = NewsArticle(
            title=raw.title,
            content=raw.content,
            category=raw.category,
            source=raw.source,
            source_url=raw.source_url,
            content_hash=content_hash,
            publish_time=raw.publish_time,
            crawl_time=now,
            summary_status="pending",
            summary=None,
            summary_time_ms=None,
            summary_error=None,
            model_version=None,
            created_at=now,
            updated_at=now,
        )
        db.add(article)
        try:
            db.commit()
            return article, True
        except IntegrityError:
            # 并发下同内容同时写入，唯一约束兜底：回滚后返回已存在记录
            db.rollback()
            existing = db.scalar(
                select(NewsArticle).where(NewsArticle.content_hash == content_hash)
            )
            if existing is None:
                raise
            return existing, False

    @staticmethod
    def list_news(
        db: "Session",
        page: int = _DEFAULT_PAGE,
        page_size: int = _DEFAULT_PAGE_SIZE,
        category: str | None = None,
    ) -> tuple[int, list[dict]]:
        """分页查询新闻列表。

        排序固定为 publish_time DESC，发布时间为空的记录排在后，空值内及同时间按 id DESC，
        保证稳定分页。category 非法时抛 ValueError（由 API 层映射为业务错误）。
        返回 (total, items)；items 为不含 content 的字典列表。
        """
        if page < 1:
            raise ValueError("page 必须大于等于 1")
        if page_size < 1 or page_size > _MAX_PAGE_SIZE:
            raise ValueError("page_size 必须在 1~50 之间")
        if category is not None and not is_valid_category(category):
            raise ValueError(f"分类不在系统六类内：{category}")

        filters = [NewsArticle.category == category] if category else []
        total = db.scalar(select(func.count()).select_from(NewsArticle).where(*filters)) or 0

        columns = (
            NewsArticle.id,
            NewsArticle.title,
            NewsArticle.summary,
            NewsArticle.category,
            NewsArticle.source,
            NewsArticle.publish_time,
            NewsArticle.summary_status,
        )
        rows = (
            db.execute(
                select(*columns)
                .where(*filters)
                .order_by(
                    NewsArticle.publish_time.is_(None),
                    NewsArticle.publish_time.desc(),
                    NewsArticle.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .all()
        )
        items = [
            {
                "id": row.id,
                "title": row.title,
                "summary": row.summary,
                "category": row.category,
                "source": row.source,
                "publish_time": row.publish_time,
                "summary_status": row.summary_status,
            }
            for row in rows
        ]
        return total, items

    @staticmethod
    def get_news_detail(
        db: "Session", news_id: int, client_id: str | None = None
    ) -> dict | None:
        """查询单篇新闻详情；不存在返回 None。

        client_id 为空时用户状态固定 is_favorite=False、feedback=None；
        提供 client_id 时经 A 的 UserService.get_news_user_state 获取用户状态。
        """
        article = db.get(NewsArticle, news_id)
        if article is None:
            return None

        is_favorite = False
        feedback: bool | None = None
        if client_id:
            # 复用 A 冻结的唯一内部契约，不重写收藏/反馈查询
            from app.services.user_service import UserService

            state = UserService.get_news_user_state(db, client_id, news_id)
            is_favorite = bool(state.get("is_favorite", False))
            feedback = state.get("feedback")

        return {
            "id": article.id,
            "title": article.title,
            "content": article.content,
            "summary": article.summary,
            "category": article.category,
            "source": article.source,
            "source_url": article.source_url,
            "publish_time": article.publish_time,
            "summary_status": article.summary_status,
            "summary_time_ms": article.summary_time_ms,
            "is_favorite": is_favorite,
            "feedback": feedback,
        }
