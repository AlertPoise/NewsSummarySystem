"""进程内按需摘要队列（按用户演示需求新增：点击单篇即时生成）。

行为：news API 对 pending 文章调用 request() 入队；后台守护线程懒加载一次
正式流水线（模型常驻本进程，首次约 10~30 秒，之后每篇仅推理耗时），
逐篇领取并生成；只处理被点击的 id，不批量扫描 pending，因此不会
“后台一次性生成所有摘要”。与外部批量 Worker 可并存：领取沿用
SummaryService 的 CAS/SKIP LOCKED 语义，同一篇不会重复生成。

僵尸恢复：摘要生成中若 API 进程退出（如重启），该篇会滞留 processing。
守护线程处理同一 id 前先把“processing 且超过阈值”的记录复位回 pending
再领取，避免重启后该篇永久卡死；正常生成远快于此阈值，不会误伤并发任务。

守护线程随 uvicorn 进程生命周期运行；进程退出时未完成任务保持
pending/processing，可再次点击重试或由批量 Worker 的 stale 自检兜底。
"""

from __future__ import annotations

import logging
import queue
import threading
from datetime import datetime, timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.models import NewsArticle
from app.services.summary_service import PENDING, PROCESSING

_logger = logging.getLogger(__name__)
_requests: queue.Queue[int] = queue.Queue()
_lock = threading.Lock()
_thread: threading.Thread | None = None
_pipeline = None

# 处理中超过该秒数视为上次进程中断的僵尸记录（正常推理远快于此）
_ZOMBIE_AFTER_SECONDS = 60


def request(news_id: int) -> None:
    """登记一篇按需生成请求（幂等；重复请求由领取语义去重）。"""
    _requests.put(news_id)
    _ensure_thread()


def _ensure_thread() -> None:
    global _thread
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_loop, name="on-demand-summary", daemon=True)
            _thread.start()


def _reset_zombie(db, news_id: int) -> None:
    """API 进程重启中断的僵尸 processing 复位回 pending（仅限本 id 超阈值者）。"""
    article = db.scalar(
        select(NewsArticle)
        .where(NewsArticle.id == news_id, NewsArticle.summary_status == PROCESSING)
        .with_for_update(skip_locked=True)
    )
    if article is None:
        return
    if article.updated_at is None or article.updated_at < datetime.now() - timedelta(seconds=_ZOMBIE_AFTER_SECONDS):
        article.summary_status = PENDING
        db.commit()
        print(
            f"[on-demand] 文章 id={news_id} 上次生成被中断（processing 滞留超 {_ZOMBIE_AFTER_SECONDS} 秒），"
            "已复位为 pending 重新生成。",
            flush=True,
        )
    else:
        db.rollback()


def _process_one(news_id: int) -> None:
    db = SessionLocal()
    try:
        _reset_zombie(db, news_id)
        from app.worker import run_on_demand_summary
        run_on_demand_summary(db, _pipeline, news_id=news_id)
    finally:
        db.close()


def _loop() -> None:
    global _pipeline
    while True:
        news_id = _requests.get()
        try:
            if _pipeline is None:
                # 复用 Worker 的流水线装配（含正式模型元信息/权重校验与 AI 未就绪判断）
                from app.worker import _load_summary_pipeline
                _pipeline = _load_summary_pipeline()
            if _pipeline is None:
                print(f"[on-demand] 正式摘要流水线未就绪，id={news_id} 保持 pending。", flush=True)
                continue
            _process_one(news_id)
        except Exception:
            _logger.exception("按需摘要处理失败 news_id=%s", news_id)
