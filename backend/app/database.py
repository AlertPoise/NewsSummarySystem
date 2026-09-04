"""SQLAlchemy 数据库连接与会话骨架。"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类。"""


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """为单个 HTTP 请求提供并关闭数据库会话。"""
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()
