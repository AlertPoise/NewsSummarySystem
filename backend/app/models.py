"""已冻结的 MySQL ORM 模型。

本模块 SQLAlchemy 2.x 的 `BigInteger(unsigned=True)` 旧写法在主类型上已被
移除，统一改用 `with_variant(...)` 模式：
- MySQL 上保留 UNSIGNED 行为以与 sql/create_database.sql 冻结的
  `BIGINT UNSIGNED` 对齐；
- SQLite 测试库走 INTEGER，保证 `INTEGER PRIMARY KEY` 的 ROWID 自动生成；
- 其它 dialect 走 BigInteger 默认值。

DECIMAL/MEDIUMTEXT/CHAR 同理用 dialect 方言变体，仅在 MySQL 上保留方言精度。
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import (
    BIGINT as MYSQL_BIGINT,
    CHAR as MYSQL_CHAR,
    DECIMAL as MYSQL_DECIMAL,
    MEDIUMTEXT as MYSQL_MEDIUMTEXT,
)
from sqlalchemy.dialects.sqlite import INTEGER as SQLITE_INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# ---------- 类型别名：MySQL 方言细节在 SQLite 测试库降级到 INTEGER ----------

# PK 字段必须用 INTEGER 基类型以保证 SQLite ROWID 自增；
# MySQL 上再切回带 unsigned 的 BIGINT，与冻结 DDL 对齐。
BigIntUnsigned = (
    Integer().with_variant(SQLITE_INTEGER(), "sqlite").with_variant(
        MYSQL_BIGINT(unsigned=True), "mysql"
    )
)
Char64 = String(64).with_variant(MYSQL_CHAR(64), "mysql")
MediumText = String().with_variant(MYSQL_MEDIUMTEXT(), "mysql")
Decimal7x6 = Numeric(7, 6).with_variant(MYSQL_DECIMAL(7, 6), "mysql")


class NewsArticle(Base):
    """新闻正文及摘要任务记录。"""

    __tablename__ = "news_articles"
    __table_args__ = (
        Index("ix_news_articles_category", "category"),
        Index("ix_news_articles_publish_time", "publish_time"),
        Index("ix_news_articles_summary_status", "summary_status"),
    )

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(MediumText, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_hash: Mapped[str] = mapped_column(Char64, nullable=False, unique=True)
    publish_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    crawl_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    summary_status: Mapped[str] = mapped_column(String(20), nullable=False)
    summary_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Favorite(Base):
    """客户端收藏记录。"""

    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("client_id", "news_id", name="uq_favorites_client_news"),)

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    news_id: Mapped[int] = mapped_column(BigIntUnsigned, ForeignKey("news_articles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Feedback(Base):
    """客户端对新闻摘要的当前评价。"""

    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("client_id", "news_id", name="uq_feedback_client_news"),)

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    news_id: Mapped[int] = mapped_column(BigIntUnsigned, ForeignKey("news_articles.id"), nullable=False)
    helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ModelEvaluation(Base):
    """正式摘要模型在 CNewSum 上的评价结果。"""

    __tablename__ = "model_evaluations"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_split: Mapped[str] = mapped_column(String(32), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rouge1: Mapped[float] = mapped_column(Decimal7x6, nullable=False)
    rouge2: Mapped[float] = mapped_column(Decimal7x6, nullable=False)
    rougeL: Mapped[float] = mapped_column(Decimal7x6, nullable=False)
    avg_generation_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    p95_generation_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)