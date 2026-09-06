"""新闻后台任务：阶段A 采集入库 + 阶段B 摘要处理循环（D 维护）。

数据流（docs/ARCHITECTURE.md §3）：
  阶段A：Crawler 从真实来源采集 RawArticle -> NewsService 校验/去重/入库为 pending；
  阶段B：SummaryService 原子领取 pending 置为 processing -> Worker 调用
         SummaryPipeline.generate(article) -> 成功经 SummaryService.complete 持久化，
         单篇异常经 SummaryService.fail 置为 failed（可经 API 重试回 pending）；
         InputTooLongError（正文超 max_input_tokens，确定性不可处理）例外：
         经 SummaryService.delete_unprocessable 删除该新闻，不进入可重试循环。
  启动自检：把滞留 processing 超过阈值的僵尸记录恢复为 failed，防止异常退出
  导致文章永久卡死（processing 不在 API 可重试范围内）。

接口约束：本模块只调用已冻结的 NewsService/SummaryService/SummaryPipeline 接口，
不改变任何既有签名；Worker 是唯一允许持有并调用 SummaryPipeline 的业务组件。
正式流水线未交付（C2-11）时阶段B 整体跳过：pending 保持原状，不伪造摘要、
不误标失败；阶段A 不依赖 C，始终可独立运行。
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from datetime import datetime, timedelta

from sqlalchemy import select

from app.crawlers.source_a import SourceA
from app.crawlers.source_b import SourceB
from app.database import SessionLocal
from app.exceptions import BusinessError, InputTooLongError
from app.models import NewsArticle
from app.services.news_service import NewsService
from app.services.summary_service import PROCESSING, SummaryService

try:  # Windows 控制台中文输出保障
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass


def _load_summary_pipeline():
    """加载 C 的正式摘要流水线；未交付或加载失败时返回 None（AI 未就绪）。

    load() 抛 NotImplementedError 说明 C2-10/11 尚未完成，属预期环境状态；
    其他异常同样按 AI 未就绪处理并打印定位信息，不让 Worker 崩溃。
    """
    try:
        from app.ai.pipeline import SummaryPipeline

        pipeline = SummaryPipeline()
        pipeline.load()
        return pipeline
    except NotImplementedError:
        print("[worker] 正式摘要流水线尚未交付（C2-11 未完成），摘要阶段跳过。", flush=True)
        return None
    except Exception:
        print("[worker] SummaryPipeline 加载失败，摘要阶段跳过：", flush=True)
        traceback.print_exc()
        return None


def run_crawl_phase(
    db, limit: int = 20, request_interval: float = 1.0
) -> dict[str, dict[str, int]]:
    """阶段A：采集两真实来源并逐条入库，返回各来源统计。

    去重与六类校验由 NewsService.save_article 负责：created=True 表示新入库，
    False 表示内容已存在被 SHA-256 去重；单条非法文章仅跳过并计数，不中断批次；
    单个来源整体失败（网络/站点异常）不影响另一来源。
    """
    stats: dict[str, dict[str, int]] = {}
    for source_class in (SourceA, SourceB):
        name = source_class.__name__
        stats[name] = {"fetched": 0, "created": 0, "deduped": 0, "rejected": 0}
        try:
            source = source_class(limit=limit, request_interval=request_interval)
            articles = source.fetch_articles()
        except Exception:
            print(f"[worker] {name} 采集失败，跳过该来源：", flush=True)
            traceback.print_exc()
            continue

        stats[name]["fetched"] = len(articles)
        for raw in articles:
            try:
                _article, created = NewsService.save_article(db, raw)
            except BusinessError as exc:
                stats[name]["rejected"] += 1
                print(f"[worker] 跳过非法文章 {raw.source_url}：{exc.message}", flush=True)
                continue
            if created:
                stats[name]["created"] += 1
            else:
                stats[name]["deduped"] += 1
        print(
            f"[worker] {name} 采集完成：获取 {stats[name]['fetched']} 篇，"
            f"新入库 {stats[name]['created']} 篇，去重 {stats[name]['deduped']} 篇，"
            f"非法跳过 {stats[name]['rejected']} 篇。",
            flush=True,
        )
    return stats


def run_summary_phase(db, pipeline, batch_limit: int = 50) -> dict[str, int]:
    """阶段B：摘要处理循环（状态机骨架，依赖 C2-11 交付后真正生效）。

    每轮经 SummaryService.claim_pending 原子领取一条 pending 置为 processing，
    调用冻结接口 generate(article) 生成 SummaryResult，成功交 complete、单篇
    异常交 fail（failed 可经 API 重试回 pending，不会卡死在 processing）。
    generate 抛 NotImplementedError 视为流水线未交付：该篇记为失败后停止本轮，
    不把剩余 pending 批量误标失败。
    generate 抛 InputTooLongError 视为确定性永久不可处理（正文超过
    max_input_tokens，重试必然复现）：删除该新闻及外键依赖行并计入 deleted，
    绝不标 failed，避免 failed -> pending 的永久重试循环。
    """
    stats = {"completed": 0, "failed": 0, "deleted": 0}
    while stats["completed"] + stats["failed"] + stats["deleted"] < batch_limit:
        article = SummaryService.claim_pending(db)
        if article is None:
            break
        try:
            result = pipeline.generate(article.content)
        except NotImplementedError as exc:
            SummaryService.fail(db, article.id, f"摘要流水线未交付：{exc}")
            stats["failed"] += 1
            print(f"[worker] 流水线未实现，本篇已记为 failed（id={article.id}），本轮摘要终止。", flush=True)
            break
        except InputTooLongError as exc:
            dependents = SummaryService.delete_unprocessable(db, article.id)
            stats["deleted"] += 1
            print(
                f"[worker] 文章 id={article.id} 正文超过 max_input_tokens（{exc}），"
                f"确定性不可摘要，已删除该新闻及 {dependents} 条关联收藏/反馈。",
                flush=True,
            )
            continue
        except Exception as exc:
            SummaryService.fail(db, article.id, str(exc)[:500])
            stats["failed"] += 1
            print(f"[worker] 摘要失败 id={article.id}：{str(exc)[:200]}", flush=True)
            continue
        SummaryService.complete(
            db,
            article.id,
            summary=result.summary,
            generation_time_ms=result.generation_time_ms,
            model_version=result.model_version,
        )
        stats["completed"] += 1
        print(
            f"[worker] 摘要完成 id={article.id} 耗时 {result.generation_time_ms}ms "
            f"模型 {result.model_version}",
            flush=True,
        )
    print(
        f"[worker] 阶段B统计：成功 {stats['completed']}，失败 {stats['failed']}，"
        f"超长删除 {stats['deleted']}。",
        flush=True,
    )
    return stats


def recover_stale_processing(db, stale_minutes: float = 10.0) -> int:
    """启动自检：把长时间滞留 processing 的僵尸记录恢复为 failed。

    正常单篇生成耗时远小于阈值（性能目标 p95 < 1.5 秒），超时即说明上次
    Worker 在生成中途异常退出；processing 不在 API 可重试范围内
    （request_summary 只重置 failed），不恢复将永久卡死。使用时间阈值而非
    无条件清扫，避免误杀并发 Worker 正在处理的篇目（SKIP LOCKED 允许多
    Worker 并发）。failed 记录可经 API 重试回到 pending。返回恢复条数。
    """
    deadline = datetime.now() - timedelta(minutes=stale_minutes)
    stale_ids = db.scalars(
        select(NewsArticle.id)
        .where(NewsArticle.summary_status == PROCESSING)
        .where(NewsArticle.updated_at < deadline)
        .order_by(NewsArticle.id)
    ).all()
    for news_id in stale_ids:
        SummaryService.fail(
            db, news_id, f"Worker 异常中断恢复：processing 滞留超过 {stale_minutes:g} 分钟"
        )
    return len(stale_ids)


def run_worker(
    limit: int = 20,
    request_interval: float = 1.0,
    summary_batch: int = 50,
    skip_crawl: bool = False,
    skip_summary: bool = False,
    stale_minutes: float = 10.0,
) -> None:
    """后台任务入口：单次执行「启动自检 -> 采集入库 -> 摘要处理」一轮。

    周期性运行由外部调度重复调用本入口（如 scripts/run_worker.ps1 或计划任务）。
    正式流水线未交付时本轮只完成采集入库，pending 由后续轮次处理。
    """
    started = time.perf_counter()
    db = SessionLocal()
    try:
        recovered = recover_stale_processing(db, stale_minutes=stale_minutes)
        if recovered:
            print(f"[worker] 启动自检：恢复 {recovered} 条僵尸 processing 记录为 failed。", flush=True)

        if not skip_crawl:
            print(f"[worker] === 阶段A：采集入库开始（limit={limit}）===", flush=True)
            run_crawl_phase(db, limit=limit, request_interval=request_interval)
        else:
            print("[worker] 阶段A按要求跳过（--skip-crawl）。", flush=True)

        if not skip_summary:
            print("[worker] === 阶段B：摘要处理开始 ===", flush=True)
            pipeline = _load_summary_pipeline()
            if pipeline is not None:
                run_summary_phase(db, pipeline, batch_limit=summary_batch)
        else:
            print("[worker] 阶段B按要求跳过（--skip-summary）。", flush=True)
    finally:
        db.close()
    print(f"[worker] 本轮完成，耗时 {time.perf_counter() - started:.1f} 秒。", flush=True)


def main() -> None:
    """命令行入口：python -m app.worker [--limit N] [--skip-crawl] [--skip-summary]。"""
    parser = argparse.ArgumentParser(description="新闻后台任务：采集入库 + 摘要处理")
    parser.add_argument("--limit", type=int, default=20, help="每个来源单轮最多采集条数（默认 20）")
    parser.add_argument("--interval", type=float, default=1.0, help="详情页请求间隔秒数（默认 1.0）")
    parser.add_argument("--summary-batch", type=int, default=50, help="单轮最多处理摘要条数（默认 50）")
    parser.add_argument("--skip-crawl", action="store_true", help="跳过采集入库阶段")
    parser.add_argument("--skip-summary", action="store_true", help="跳过摘要处理阶段")
    parser.add_argument(
        "--stale-minutes", type=float, default=10.0,
        help="processing 滞留超过该分钟数判定为上次异常中断并恢复为 failed（默认 10）",
    )
    args = parser.parse_args()
    run_worker(
        limit=args.limit,
        request_interval=args.interval,
        summary_batch=args.summary_batch,
        skip_crawl=args.skip_crawl,
        skip_summary=args.skip_summary,
        stale_minutes=args.stale_minutes,
    )


if __name__ == "__main__":
    main()
