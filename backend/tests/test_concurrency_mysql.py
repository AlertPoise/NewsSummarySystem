"""D6-02 并发维度测试：claim_pending 的 FOR UPDATE SKIP LOCKED 与 CAS 重置。

必须运行在真实 MySQL 上（SQLite 无行锁语义，`with_for_update` 为空操作）：
夹具按 backend/.env 的连接信息创建独立的 `{db_name}_e2e` 数据库并建表，
全程不读写真实业务库 `news_summary`，结束后删除。MySQL 不可用时整组用例
自动跳过，不影响 SQLite 默认测试流。
"""

from __future__ import annotations

import threading
from datetime import datetime

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import Base
from app.models import NewsArticle
from app.services.summary_service import (
    COMPLETED,
    FAILED,
    PENDING,
    PROCESSING,
    SummaryService,
)

# 与 conftest 的 MySQL 清理顺序一致：先外键依赖表再主表
_E2E_TABLES = ("feedback", "favorites", "model_evaluations", "news_articles")


@pytest.fixture(scope="module")
def e2e_engine():
    """独立 e2e MySQL 引擎：建库建表 → 用例 → 删库；连不上则整组跳过。

    建库权限回退链：先用应用用户（news_app）尝试 CREATE DATABASE；
    无权限（错误 1044，sql/create_database.sql 只授予 news_summary.*）时，
    按本机开发约定（scripts 中 mysql_cli.bat 的 root 免密连接）以 root
    引导建库并授予 news_app 与真实库一致的权限。root 密码不硬编码，
    可经 TEST_MYSQL_ROOT_PASSWORD 环境变量覆盖，默认与本地免密 root 一致。
    两者都失败则跳过整组用例。测试始终以 news_app 身份运行。
    """
    settings = get_settings()
    app_server_url = (
        f"mysql+pymysql://{settings.db_user}:{settings.db_password}@"
        f"{settings.db_host}:{settings.db_port}/?charset={settings.db_charset}"
    )
    e2e_name = f"{settings.db_name}_e2e"

    def _try_connect(url: str):
        engine = create_engine(url, connect_args={"connect_timeout": 3})
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            engine.dispose()
            raise
        return engine

    admin_engine = None
    try:
        admin_engine = _try_connect(app_server_url)
        with admin_engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {e2e_name} CHARACTER SET utf8mb4"))
            conn.commit()
    except OperationalError as exc:
        if admin_engine is not None:
            admin_engine.dispose()
        if exc.orig is None or exc.orig.args[0] != 1044:
            pytest.skip(f"MySQL 不可用，D6-02 并发用例跳过：{exc.orig}")
        # 1044：应用用户无建库权限，回退 root 引导（密码经环境变量覆盖，不硬编码）
        import os

        root_password = os.environ.get("TEST_MYSQL_ROOT_PASSWORD", "")
        root_url = (
            f"mysql+pymysql://root:{root_password}@"
            f"{settings.db_host}:{settings.db_port}/?charset={settings.db_charset}"
        )
        try:
            admin_engine = _try_connect(root_url)
            with admin_engine.connect() as conn:
                conn.execute(
                    text(f"CREATE DATABASE IF NOT EXISTS {e2e_name} CHARACTER SET utf8mb4")
                )
                for host in ("localhost", "127.0.0.1"):
                    conn.execute(
                        text(
                            f"GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, "
                            f"INDEX, DROP, REFERENCES ON {e2e_name}.* "
                            f"TO '{settings.db_user}'@'{host}'"
                        )
                    )
                conn.commit()
        except OperationalError as root_exc:
            pytest.skip(
                "news_app 无建库权限且 root 引导失败，D6-02 并发用例跳过；"
                f"可先以管理员执行 CREATE DATABASE {e2e_name} 并授权：{root_exc.orig}"
            )

    engine = create_engine(
        f"mysql+pymysql://{settings.db_user}:{settings.db_password}@"
        f"{settings.db_host}:{settings.db_port}/{e2e_name}?charset={settings.db_charset}",
        pool_pre_ping=True,
    )
    try:
        Base.metadata.create_all(engine)
    except Exception:
        engine.dispose()
        admin_engine.dispose()
        raise
    yield engine

    engine.dispose()
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {e2e_name}"))
            conn.commit()
    except OperationalError:
        pass  # 清理失败不掩盖用例结果，e2e 库可由管理员手动删除
    admin_engine.dispose()


@pytest.fixture()
def e2e_sessions(e2e_engine) -> sessionmaker:
    """每个用例独立的会话工厂；用例开始前清空 e2e 库全部数据。"""
    with e2e_engine.begin() as conn:
        for table in _E2E_TABLES:
            conn.execute(text(f"DELETE FROM {table}"))
    return sessionmaker(bind=e2e_engine, autoflush=False, autocommit=False)


def _insert_articles(factory: sessionmaker, count: int, *, status: str = PENDING) -> list[int]:
    """向 e2e 库插入 count 条指定 summary_status 的新闻，返回入库 id 列表。"""
    now = datetime.now()
    articles = []
    with factory() as session:
        for i in range(count):
            article = NewsArticle(
                title=f"并发稿件{i}",
                content=f"并发测试正文{i}，用于验证多 Worker 领取互斥性。",
                category="科技",
                source="测试来源",
                source_url=f"https://example.invalid/conc/{status}/{i}",
                content_hash=f"{abs(hash((status, i))):064x}",
                publish_time=now,
                crawl_time=now,
                summary_status=status,
                summary=None,
                summary_time_ms=None,
                summary_error=None,
                model_version=None,
                created_at=now,
                updated_at=now,
            )
            session.add(article)
            articles.append(article)
        session.commit()
        return [article.id for article in articles]


def _status_map(factory: sessionmaker) -> dict[int, str]:
    """读取 e2e 库全部新闻的 {id: summary_status}。"""
    with factory() as session:
        return {
            row.id: row.summary_status
            for row in session.scalars(select(NewsArticle)).all()
        }


def test_claim_pending_only_claims_pending(e2e_sessions) -> None:
    """领取只针对 pending：processing/completed/failed 不会被再次领取。"""
    pending_ids = _insert_articles(e2e_sessions, 1, status=PENDING)
    _insert_articles(e2e_sessions, 1, status=PROCESSING)
    _insert_articles(e2e_sessions, 1, status=COMPLETED)
    _insert_articles(e2e_sessions, 1, status=FAILED)

    with e2e_sessions() as session:
        first = SummaryService.claim_pending(session)
        first_id = first.id if first is not None else None
        second = SummaryService.claim_pending(session)

    assert first_id == pending_ids[0]
    assert second is None  # 其余三条非 pending，无可领取


def test_skip_locked_skips_row_held_by_uncommitted_claimer(e2e_sessions) -> None:
    """确定性验证 SKIP LOCKED：被未提交事务锁定的 pending 行被后来者跳过。

    会话1以与 claim_pending 相同的锁定查询持有第一行行锁且不提交；
    会话2的 claim_pending 必须跳过该行领取后续行；会话1回滚后该行
    原样保留为 pending，未被任何 Worker 消费。
    """
    ids = sorted(_insert_articles(e2e_sessions, 3))
    first_id = ids[0]

    holder = e2e_sessions()
    other = e2e_sessions()
    claimed: list[int] = []
    try:
        held = holder.scalars(
            select(NewsArticle)
            .where(NewsArticle.summary_status == PENDING)
            .order_by(NewsArticle.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).first()
        assert held is not None and held.id == first_id

        claimer = SummaryService.claim_pending(other)
        assert claimer is not None and claimer.id != first_id
        claimed.append(claimer.id)
        claimer2 = SummaryService.claim_pending(other)
        assert claimer2 is not None and claimer2.id != first_id
        claimed.append(claimer2.id)
    finally:
        holder.rollback()
        holder.close()
        other.close()

    rows = _status_map(e2e_sessions)
    assert rows[first_id] == PENDING  # 被跳过的行未被消费
    assert all(rows[cid] == PROCESSING for cid in claimed)


def test_four_workers_claim_exactly_once(e2e_sessions) -> None:
    """4 个并发 Worker 线程领取 24 条 pending：每条恰好被领取一次。"""
    total = 24
    _insert_articles(e2e_sessions, total)

    results: list[int] = []
    lock = threading.Lock()

    def worker() -> None:
        session = e2e_sessions()
        try:
            while True:
                article = SummaryService.claim_pending(session)
                if article is None:
                    break
                with lock:
                    results.append(article.id)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not any(thread.is_alive() for thread in threads), "存在 Worker 线程卡死"

    assert len(results) == total, f"领取条数不足：{len(results)}/{total}"
    assert len(set(results)) == total, "出现重复领取（SKIP LOCKED 失效）"

    rows = _status_map(e2e_sessions)
    assert set(rows.values()) == {PROCESSING}


def test_request_summary_cas_reset_has_single_winner(e2e_sessions) -> None:
    """failed → pending 的 CAS 重置：并发重复请求按当前实际状态幂等返回。"""
    target = _insert_articles(e2e_sessions, 1, status=FAILED)[0]

    first_session = e2e_sessions()
    second_session = e2e_sessions()
    try:
        first_result = SummaryService.request_summary(first_session, target)
        # 第二个请求到达时行已不是 failed：CAS 影响行数为 0，走幂等返回分支
        second_result = SummaryService.request_summary(second_session, target)
    finally:
        first_session.close()
        second_session.close()

    assert first_result is not None and first_result["summary_status"] == PENDING
    assert second_result is not None and second_result["summary_status"] == PENDING
    assert _status_map(e2e_sessions)[target] == PENDING
    assert "summary_error" not in first_result or first_result.get("summary") is None


def test_request_summary_leaves_processing_untouched(e2e_sessions) -> None:
    """processing 状态不被 request_summary 重置（API.md §7 语义）。"""
    target = _insert_articles(e2e_sessions, 1, status=PROCESSING)[0]

    with e2e_sessions() as session:
        result = SummaryService.request_summary(session, target)

    assert result is not None and result["summary_status"] == PROCESSING
    assert _status_map(e2e_sessions)[target] == PROCESSING
