"""Worker 阶段B 异常分类测试：确定性永久不可处理 vs 临时生成失败。

回归场景：C 的 SummaryPipeline.generate 对超过 512 token 的正文抛
InputTooLongError，若按通用 Exception 标 failed，request_summary 会把
failed 重置回 pending，形成永久重试循环。修复后超长文章必须被删除，
不出现在任何可重试状态里。
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.ai.pipeline import SummaryResult
from app.exceptions import InputTooLongError
from app.models import Favorite, Feedback, NewsArticle
from app.services.summary_service import SummaryService
from app.worker import run_summary_phase


def _add_article(db: Session, *, title: str, content: str, status: str = "pending") -> NewsArticle:
    """插入一条指定 summary_status 的新闻，返回带 id 的记录。"""
    fixed_time = datetime(2026, 9, 6, 10, 0, 0)
    article = NewsArticle(
        title=title,
        content=content,
        summary=None,
        category="科技",
        source="测试来源",
        source_url=f"https://example.invalid/news/{title}",
        content_hash=title.rjust(64, "0"),
        publish_time=fixed_time,
        crawl_time=fixed_time,
        summary_status=status,
        summary_time_ms=None,
        summary_error=None,
        model_version=None,
        created_at=fixed_time,
        updated_at=fixed_time,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


class _FakePipeline:
    """按标题关键词分流：超长 -> InputTooLongError；临时故障 -> RuntimeError。"""

    def __init__(self) -> None:
        self.load_calls = 0

    def generate(self, article: str) -> SummaryResult:
        if "超长" in article[:32]:
            raise InputTooLongError("正文 1234 token 超过 max_input_tokens 512")
        if "临时故障" in article[:32]:
            raise RuntimeError("模型推理超时")
        return SummaryResult(summary="摘要", generation_time_ms=10, model_version="test-v1")


def test_overlong_article_deleted_not_failed(db_session: Session) -> None:
    """超长文章被删除：不存在于任何状态，尤其不能是 failed（防重试循环）。"""
    overlong = _add_article(db_session, title="超长文章", content="超长" * 600)
    stats = run_summary_phase(db_session, _FakePipeline(), batch_limit=10)
    assert stats["deleted"] == 1
    assert db_session.get(NewsArticle, overlong.id) is None
    assert db_session.scalar(
        select(NewsArticle).where(NewsArticle.title == "超长文章")
    ) is None


def test_overlong_article_with_dependents_deleted_together(db_session: Session) -> None:
    """删除超长新闻时连带清理 RESTRICT 外键依赖行（favorites/feedback）。"""
    overlong = _add_article(db_session, title="超长带依赖", content="超长" * 600)
    now = datetime(2026, 9, 6, 10, 30, 0)
    db_session.add(Favorite(client_id="c1", news_id=overlong.id, created_at=now))
    db_session.add(
        Feedback(
            client_id="c1", news_id=overlong.id, helpful=True,
            created_at=now, updated_at=now,
        )
    )
    db_session.commit()

    stats = run_summary_phase(db_session, _FakePipeline(), batch_limit=10)

    assert stats["deleted"] == 1
    assert db_session.get(NewsArticle, overlong.id) is None
    assert db_session.scalars(select(Favorite).where(Favorite.news_id == overlong.id)).all() == []
    assert db_session.scalars(select(Feedback).where(Feedback.news_id == overlong.id)).all() == []


def test_transient_failure_still_failed_and_retryable(db_session: Session) -> None:
    """临时失败保持既有协议：标 failed 且可经 request_summary 重置回 pending。"""
    broken = _add_article(db_session, title="临时故障文章", content="临时故障" + "正常" * 100)
    stats = run_summary_phase(db_session, _FakePipeline(), batch_limit=10)
    assert stats["failed"] == 1
    row = db_session.get(NewsArticle, broken.id)
    assert row is not None and row.summary_status == "failed"
    assert "模型推理超时" in (row.summary_error or "")

    reset = SummaryService.request_summary(db_session, broken.id)
    assert reset is not None and reset["summary_status"] == "pending"


def test_mixed_batch_classification(db_session: Session) -> None:
    """同一批次内三类文章各走各的路径：删除 / failed 可重试 / completed。"""
    _add_article(db_session, title="超长甲", content="超长" * 600)
    _add_article(db_session, title="临时故障乙", content="临时故障" + "正常" * 100)
    _add_article(db_session, title="正常丙", content="正常" * 100)

    stats = run_summary_phase(db_session, _FakePipeline(), batch_limit=10)

    assert stats == {"completed": 1, "failed": 1, "deleted": 1}
    statuses = {
        row.title: row.summary_status
        for row in db_session.scalars(select(NewsArticle)).all()
    }
    assert "超长甲" not in statuses  # 已删除
    assert statuses["临时故障乙"] == "failed"
    assert statuses["正常丙"] == "completed"


def test_delete_unprocessable_cas_guard(db_session: Session) -> None:
    """delete_unprocessable 仅对 processing 行生效，其他状态不删除。"""
    pending_row = _add_article(db_session, title="还在pending", content="正文")
    assert SummaryService.delete_unprocessable(db_session, pending_row.id) == 0
    assert db_session.get(NewsArticle, pending_row.id) is not None


@pytest.mark.parametrize("status", ["processing"])
def test_delete_unprocessable_processing_row(db_session: Session, status: str) -> None:
    """processing 行可被删除（Worker 持有领取权后的正常路径）。"""
    row = _add_article(db_session, title="processing中", content="正文", status=status)
    dependents = SummaryService.delete_unprocessable(db_session, row.id)
    assert dependents == 0
    assert db_session.get(NewsArticle, row.id) is None
