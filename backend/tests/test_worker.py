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


class TestC_DContract:
    """P1-5：真实 C Pipeline（假组件但走真实代码路径）与 D Worker 的集成契约。

    C 的 SummaryPipeline.generate 预检超长时抛出的必须是 D Worker 捕获的
    同一个 InputTooLongError（共享 app.exceptions 实例），Worker 据此走
    delete 而非 failed，防止 failed → pending 永久重试循环。
    """

    def test_shared_InputTooLongError_is_same_class(self) -> None:
        """pipeline 再导出的异常与 app.exceptions 的必须是同一个类对象。

        P0-2 修复的回归锁：若 C 侧自造一个独立异常类，D 的
        `except InputTooLongError` 就捕获不到，超长文章会落到通用
        Exception 分支被标 failed，进入可重试死循环。
        """
        from app.ai import pipeline as ai_pipeline
        from app import exceptions as exc_mod

        assert ai_pipeline.InputTooLongError is exc_mod.InputTooLongError

    def test_real_pipeline_overlong_deleted_not_failed(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """真实 C Pipeline 抛超长异常时，Worker 删除文章而非标 failed。

        用假 BERT/Transformer 仅隔离模型权重下载；超长预检、抛异常、
        Worker 捕获、delete_unprocessable 全部走真实代码路径。
        """
        import numpy as np

        class FakeBert:
            def __init__(self, **kwargs: object) -> None:
                self.is_loaded = True

            def load(self) -> None:
                self.is_loaded = True

            def encode_batch(self, sentences: list[str]) -> list[object]:
                return [np.zeros(4) for _ in sentences]

        class FakeSummarizer:
            model_version = "test-v0"
            metadata = {
                "model_name": "dummy",
                "model_version": "test-v0",
                "dataset": "CNewSum",
                "max_input_tokens": 512,
                "max_new_tokens": 60,
            }

            def __init__(self, model_dir: object) -> None:
                pass

            def load(self) -> None:
                pass

            def count_tokens(self, text: str) -> int:
                return 600  # 触发真实预检：> 512 → 抛共享 InputTooLongError

            def generate(self, text: str) -> str:
                raise AssertionError("超长输入不应到达生成阶段")

        monkeypatch.setattr("app.ai.pipeline.BertEncoder", FakeBert)
        monkeypatch.setattr("app.ai.pipeline.TransformerSummarizer", FakeSummarizer)

        from app.ai.pipeline import SummaryPipeline

        pipeline = SummaryPipeline(max_input_tokens=512)
        pipeline.load()

        overlong = _add_article(db_session, title="C-D集成超长", content="超长" * 600)
        stats = run_summary_phase(db_session, pipeline, batch_limit=10)

        assert stats["deleted"] == 1
        assert stats["failed"] == 0
        assert db_session.get(NewsArticle, overlong.id) is None



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
    assert SummaryService.delete_unprocessable(db_session, pending_row.id) == -1
    assert db_session.get(NewsArticle, pending_row.id) is not None


def test_delete_unprocessable_cas_failure_preserves_dependents(
    db_session: Session,
) -> None:
    """CAS 失败必须整事务回滚：新闻与收藏/反馈全部原样保留。

    回归 DATABASE.md §6 硬性要求——禁止"子表已删、新闻仍在"的半删除状态。
    """
    row = _add_article(db_session, title="非processing带依赖", content="正文")
    now = datetime(2026, 9, 6, 11, 0, 0)
    db_session.add(Favorite(client_id="c2", news_id=row.id, created_at=now))
    db_session.add(
        Feedback(client_id="c2", news_id=row.id, helpful=False, created_at=now, updated_at=now)
    )
    db_session.commit()

    result = SummaryService.delete_unprocessable(db_session, row.id)

    assert result == -1
    assert db_session.get(NewsArticle, row.id) is not None
    assert db_session.scalars(select(Favorite).where(Favorite.news_id == row.id)).all() != []
    assert db_session.scalars(select(Feedback).where(Feedback.news_id == row.id)).all() != []


@pytest.mark.parametrize("status", ["processing"])
def test_delete_unprocessable_processing_row(db_session: Session, status: str) -> None:
    """processing 行可被删除（Worker 持有领取权后的正常路径）。"""
    row = _add_article(db_session, title="processing中", content="正文", status=status)
    dependents = SummaryService.delete_unprocessable(db_session, row.id)
    assert dependents == 0
    assert db_session.get(NewsArticle, row.id) is None
