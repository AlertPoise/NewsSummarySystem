"""测试夹具：根据 ``DATABASE_URL`` 环境变量在 SQLite 内存库与真实 MySQL 之间切换。

为什么保留 SQLite 默认：CI 与本地日常开发不需要起 MySQL，SQLite 内存 + PRAGMA
FK=ON 已经能覆盖 FK / 唯一约束契约。

如何切 MySQL：在 ``pytest`` 启动前设置 ``DATABASE_URL=mysql+pymysql://...``，
另外再用 ``TEST_MYSQL_RESET=1`` 让每个测试用一套独立前缀清理（默认 ``e2e_``），
避免污染 ``news_summary`` 真实业务表。

使用举例（脚本里）：

    $env:DATABASE_URL = 'mysql+pymysql://news_app:pwd@127.0.0.1:3306/news_summary?charset=utf8mb4'
    $env:TEST_MYSQL_RESET = '1'
    pytest tests/ -v
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import NewsArticle


def _is_mysql_url(url: str) -> bool:
    return url.startswith("mysql") or url.startswith("mariadb")


_TEST_MYSQL_PREFIX = "e2e_"
# 与 sql/create_database.sql + backend/app/models.py + 真实库保持一致：
# 表名无 user_ 前缀（不是 user_favorites / user_feedback）
_TABLES_TO_RESET = (
    "feedback",
    "favorites",
    "model_evaluations",
    "news_articles",
)


@pytest.fixture
def engine() -> Generator[Engine, None, None]:
    """数据库引擎：默认 SQLite 内存；环境变量 DATABASE_URL 指向 MySQL 时切真库。

    MySQL 模式下，本 fixture 启动时清理 ``e2e_`` 前缀的测试数据（不影响真实业务数据），
    测试结束后再次清理，确保测试可重复。
    """

    db_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")

    if _is_mysql_url(db_url):
        eng = create_engine(db_url, pool_pre_ping=True, pool_recycle=1800)
        if os.environ.get("TEST_MYSQL_RESET") == "1":
            with eng.begin() as conn:
                for tbl in _TABLES_TO_RESET:
                    conn.execute(text(f"DELETE FROM {tbl} WHERE 1=1"))
        try:
            yield eng
        finally:
            if os.environ.get("TEST_MYSQL_RESET") == "1":
                with eng.begin() as conn:
                    for tbl in _TABLES_TO_RESET:
                        conn.execute(text(f"DELETE FROM {tbl} WHERE 1=1"))
            eng.dispose()
        return

    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _enable_fk(dbapi_conn, _conn_record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def db_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """共享单连接的 Session，让 FastAPI 依赖与 ORM 测试看到同一份数据。"""

    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient；通过 dependency_overrides 把 get_db 重写到测试 session。"""

    def _override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_news(db_session: Session) -> NewsArticle:
    """塞一条新闻用于收藏/反馈关联；固定 news_id 由 AUTO_INCREMENT 返回。"""

    fixed_time = datetime(2026, 9, 5, 10, 0, 0)
    article = NewsArticle(
        title="测试新闻标题",
        content="测试正文" * 100,
        summary=None,
        category="科技",
        source="测试来源",
        source_url="https://example.invalid/news/1",
        content_hash="a" * 64,
        publish_time=fixed_time,
        crawl_time=fixed_time,
        summary_status="pending",
        summary_time_ms=None,
        summary_error=None,
        model_version=None,
        created_at=fixed_time,
        updated_at=fixed_time,
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)
    return article


@pytest.fixture
def valid_uuid() -> str:
    """合法的 UUID v4 字符串，用于 X-Client-ID Header。"""

    return "550e8400-e29b-41d4-a716-446655440000"
