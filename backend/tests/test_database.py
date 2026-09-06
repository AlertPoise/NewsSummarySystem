"""数据库模型 / Service 层测试（角色 A 部分：A3-01~05 行为测试）。

不依赖外部 MySQL：使用 SQLite 内存 + PRAGMA foreign_keys=ON（conftest.py），
让 FK / 唯一约束触发 IntegrityError 的路径可在 CI 离线跑通。
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import BusinessError, ERR_NOT_FOUND
from app.models import Favorite, Feedback, ModelEvaluation, NewsArticle
from app.services.user_service import UserService


# ---------- 既有：模型可导入 ----------


def test_database_models_are_available() -> None:
    """验证已冻结 ORM 模型可被导入。"""

    assert NewsArticle.__tablename__ == "news_articles"
    assert Favorite.__tablename__ == "favorites"
    assert Feedback.__tablename__ == "feedback"
    assert ModelEvaluation.__tablename__ == "model_evaluations"


# ---------- A3-01 add_favorite：Service 层行为 ----------


def test_add_favorite_inserts_row(db_session: Session, sample_news: NewsArticle, valid_uuid: str) -> None:  # noqa: ANN001
    """首次收藏 → favorites 表新增 1 行，created_at 已填。"""

    result = UserService.add_favorite(db_session, client_id=valid_uuid, news_id=sample_news.id)
    assert result == {"news_id": sample_news.id, "is_favorite": True}

    count = db_session.scalar(select(func.count()).select_from(Favorite))
    assert count == 1
    row = db_session.scalar(select(Favorite))
    assert row.client_id == valid_uuid
    assert row.news_id == sample_news.id
    assert isinstance(row.created_at, datetime)


def test_add_favorite_idempotent_at_service_layer(
    db_session: Session, sample_news: NewsArticle, valid_uuid: str
) -> None:  # noqa: ANN001
    """Service 层幂等：连续两次 add_favorite 仍 1 行。"""

    UserService.add_favorite(db_session, client_id=valid_uuid, news_id=sample_news.id)
    UserService.add_favorite(db_session, client_id=valid_uuid, news_id=sample_news.id)
    count = db_session.scalar(select(func.count()).select_from(Favorite))
    assert count == 1


def test_add_favorite_news_not_found_raises_1002(db_session: Session, valid_uuid: str) -> None:
    """news_id 不存在 → BusinessError(1002)。"""

    with pytest.raises(BusinessError) as exc_info:
        UserService.add_favorite(db_session, client_id=valid_uuid, news_id=9999)
    assert exc_info.value.code == ERR_NOT_FOUND
    assert exc_info.value.http_status == 404


# ---------- A3-02 remove_favorite ----------


def test_remove_favorite_deletes_row(
    db_session: Session, sample_news: NewsArticle, valid_uuid: str
) -> None:  # noqa: ANN001
    """先 add 再 remove → favorites 表清空。"""

    UserService.add_favorite(db_session, client_id=valid_uuid, news_id=sample_news.id)
    result = UserService.remove_favorite(db_session, client_id=valid_uuid, news_id=sample_news.id)
    assert result == {"news_id": sample_news.id, "is_favorite": False}
    assert db_session.scalar(select(func.count()).select_from(Favorite)) == 0


def test_remove_favorite_no_record_is_noop(
    db_session: Session, sample_news: NewsArticle, valid_uuid: str
) -> None:  # noqa: ANN001
    """无记录时仍返回 is_favorite=false，不抛错。"""

    result = UserService.remove_favorite(db_session, client_id=valid_uuid, news_id=sample_news.id)
    assert result["is_favorite"] is False


# ---------- A3-03 list_favorites ----------


def test_list_favorites_excludes_other_clients(
    db_session: Session, sample_news: NewsArticle, valid_uuid: str
) -> None:  # noqa: ANN001
    """仅返回当前 client_id 的收藏；另一个 client 的记录被过滤。"""

    UserService.add_favorite(db_session, client_id=valid_uuid, news_id=sample_news.id)
    db_session.add(
        Favorite(
            client_id="another-client",
            news_id=sample_news.id,
            created_at=datetime(2026, 9, 5, 10, 0, 0),
        )
    )
    db_session.commit()

    items = UserService.list_favorites(db_session, client_id=valid_uuid)
    assert len(items) == 1
    assert items[0]["id"] == sample_news.id
    # 绝不返回 content
    assert "content" not in items[0]


def test_list_favorites_empty(db_session: Session, valid_uuid: str) -> None:
    """无任何收藏 → 空列表。"""

    items = UserService.list_favorites(db_session, client_id=valid_uuid)
    assert items == []


# ---------- A3-04 upsert_feedback ----------


def test_upsert_feedback_insert_then_update_preserves_created_at(
    db_session: Session, sample_news: NewsArticle, valid_uuid: str
) -> None:  # noqa: ANN001
    """先 INSERT 再 UPDATE → created_at 不变（DATABASE.md §3 硬性要求）。"""

    UserService.upsert_feedback(db_session, client_id=valid_uuid, news_id=sample_news.id, helpful=True)
    row = db_session.scalar(
        select(Feedback).where(
            Feedback.client_id == valid_uuid, Feedback.news_id == sample_news.id
        )
    )
    first_created_at = row.created_at
    first_updated_at = row.updated_at

    UserService.upsert_feedback(
        db_session, client_id=valid_uuid, news_id=sample_news.id, helpful=False
    )
    db_session.expire_all()
    row = db_session.scalar(
        select(Feedback).where(
            Feedback.client_id == valid_uuid, Feedback.news_id == sample_news.id
        )
    )
    assert row.helpful is False
    assert row.created_at == first_created_at
    assert row.updated_at >= first_updated_at


def test_upsert_feedback_news_not_found_raises_1002(db_session: Session, valid_uuid: str) -> None:
    """news_id 不存在 → 404/1002。"""

    with pytest.raises(BusinessError) as exc_info:
        UserService.upsert_feedback(
            db_session, client_id=valid_uuid, news_id=9999, helpful=True
        )
    assert exc_info.value.code == ERR_NOT_FOUND


def test_feedback_unique_constraint_violates_on_raw_duplicate(
    db_session: Session, sample_news: NewsArticle, valid_uuid: str
) -> None:  # noqa: ANN001
    """绕过 Service 直接写：第二次 INSERT 触发 IntegrityError 验证唯一约束生效。"""

    fixed_time = datetime(2026, 9, 5, 10, 0, 0)
    db_session.add(
        Feedback(
            client_id=valid_uuid,
            news_id=sample_news.id,
            helpful=True,
            created_at=fixed_time,
            updated_at=fixed_time,
        )
    )
    db_session.commit()

    db_session.add(
        Feedback(
            client_id=valid_uuid,
            news_id=sample_news.id,
            helpful=False,
            created_at=fixed_time,
            updated_at=fixed_time,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ---------- A3-05 get_news_user_state ----------


def test_get_news_user_state_none_client(db_session: Session, sample_news: NewsArticle) -> None:
    """client_id=None → is_favorite=False, feedback=None（API.md §6）。"""

    state = UserService.get_news_user_state(db_session, None, sample_news.id)
    assert state == {"is_favorite": False, "feedback": None}


def test_get_news_user_state_no_records(
    db_session: Session, sample_news: NewsArticle, valid_uuid: str
) -> None:  # noqa: ANN001
    """client_id 合法但无任何记录 → is_favorite=False, feedback=None。"""

    state = UserService.get_news_user_state(db_session, valid_uuid, sample_news.id)
    assert state == {"is_favorite": False, "feedback": None}


def test_get_news_user_state_only_favorite(
    db_session: Session, sample_news: NewsArticle, valid_uuid: str
) -> None:  # noqa: ANN001
    """有收藏无反馈 → is_favorite=True, feedback=None。"""

    UserService.add_favorite(db_session, client_id=valid_uuid, news_id=sample_news.id)
    state = UserService.get_news_user_state(db_session, valid_uuid, sample_news.id)
    assert state == {"is_favorite": True, "feedback": None}


def test_get_news_user_state_favorite_and_feedback(
    db_session: Session, sample_news: NewsArticle, valid_uuid: str
) -> None:  # noqa: ANN001
    """有收藏有反馈 → is_favorite=True, feedback=helpful 值。"""

    UserService.add_favorite(db_session, client_id=valid_uuid, news_id=sample_news.id)
    UserService.upsert_feedback(db_session, client_id=valid_uuid, news_id=sample_news.id, helpful=True)
    state = UserService.get_news_user_state(db_session, valid_uuid, sample_news.id)
    assert state == {"is_favorite": True, "feedback": True}