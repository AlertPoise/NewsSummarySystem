"""B2-11/B2-14/B6-02：完整正式 SummaryPipeline 单篇性能测试。"""

from __future__ import annotations

import argparse
import json
import itertools
import time
from typing import Any, Callable, Iterable

from model_training.b2_data import ROOT, utc_now
from model_training.b2_metadata import load_json
from model_training.b2_pipeline_eval_common import (LATENCY_THRESHOLD_MS, MODEL_DIR, deterministic_sample, eligibility_counts, hardware_environment, latency_target_met,
    iter_eligible_rows, iter_raw_test_rows, json_dump, latency_summary, make_run_dir, pipeline_imports, sample_manifest)


def cuda_synchronize() -> None:
    """仅在 CUDA 可用时同步，保证 GPU 异步工作被准确计入 latency。"""
    import torch

    if torch.cuda.is_available():
        torch.cuda.synchronize()


def measure_pipeline(pipeline: Any, rows: Iterable[dict[str, Any]], *, warmup_runs: int, synchronize: Callable[[], None] = cuda_synchronize) -> tuple[list[dict[str, Any]], int]:
    """预热后逐条测量 generate；warmup 绝不进入返回的原始记录。"""
    iterator = iter(rows)
    warmup_rows: list[dict[str, Any]] = []
    for _ in range(warmup_runs):
        try:
            row = next(iterator)
        except StopIteration:
            break
        warmup_rows.append(row)
        pipeline.generate(row["article"])
    measurements: list[dict[str, Any]] = []
    failures = 0
    for row in itertools.chain(warmup_rows, iterator):
        try:
            synchronize()
            start_ns = time.perf_counter_ns()
            result = pipeline.generate(row["article"])
            synchronize()
            elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            summary = result.summary if hasattr(result, "summary") else str(result)
            measurements.append({"id": row["id"], "article_token_count": row["article_token_count"], "generation_time_ms": elapsed_ms, "summary_length": len(summary), "model_version": getattr(result, "model_version", None), "status": "measured"})
        except Exception as exc:
            failures += 1
            measurements.append({"id": row["id"], "article_token_count": row["article_token_count"], "generation_time_ms": None, "summary_length": None, "model_version": None, "status": "failed", "error": f"{type(exc).__name__}: {exc}"})
    return measurements, failures


def main() -> None:
    parser = argparse.ArgumentParser(description="完整 SummaryPipeline 性能 Benchmark")
    parser.add_argument("--stage", choices=("initial", "final", "recheck", "sampled"), default="initial")
    parser.add_argument("--warmup-runs", type=int, default=5)
    parser.add_argument("--limit", type=int, help="仅 smoke；有限样本不构成正式验收")
    parser.add_argument("--c2-14-complete", action="store_true", help="仅 final：确认 C2-14 已正式交付")
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", default="20260907")
    args = parser.parse_args()
    if args.warmup_runs < 0 or args.limit is not None and args.limit <= 0 or args.sample_size <= 0:
        parser.error("warmup 必须非负，limit 必须为正数")
    if args.stage == "sampled" and args.limit is not None:
        parser.error("sampled stage 不接受 --limit；请使用固定 --sample-size")
    stage_map = {"initial": ("b2-11", "B2-11", "initial-benchmark"), "final": ("b2-14", "B2-14", "final-benchmark"), "recheck": ("b6-02", "B6-02", "benchmark-recheck"), "sampled": ("b2-11", "B2-11", "course-sampled-benchmark")}
    prefix, task, suffix = stage_map[args.stage]
    run_id, run_dir = make_run_dir(prefix, suffix)
    sampled = args.stage == "sampled"
    record: dict[str, Any] = {"run_id": run_id, "parent_run_id": None, "timestamp_start": utc_now(), "timestamp_end": None, "task": task, "experiment_type": "full_pipeline_benchmark", "formal_result": not sampled and args.limit is None and (args.stage != "final" or args.c2_14_complete), "evaluation_profile": "course_sampled" if sampled else "full", "evaluation_scope": "eligible_test_sample" if sampled else "eligible_test_full", "full_evaluation": not sampled and args.limit is None, "dataset": "CNewSum", "dataset_split": "test", "model_name": None, "model_version": None, "batch_size": 1, "warmup_runs": args.warmup_runs, "full_test_count": None, "eligible_count": None, "excluded_count": None, "eligible_ratio": None, "sample_count": 0, "avg_generation_time_ms": None, "median_generation_time_ms": None, "p95_generation_time_ms": None, "min_generation_time_ms": None, "max_generation_time_ms": None, "latency_pass_count": 0, "latency_pass_rate": None, "latency_threshold_ms": LATENCY_THRESHOLD_MS, "status": "running", "error": None, "blocked_by": None}
    json_dump(run_dir / "run.json", record)
    try:
        if args.stage == "final" and not args.c2_14_complete:
            record.update({"status": "blocked", "formal_result": False, "blocked_by": "C2-14", "error": "C2-14 completion was not confirmed; B2-14 must not be fabricated."})
            return
        metadata = load_json(MODEL_DIR / "model_metadata.json")
        record.update({"model_name": metadata["model_name"], "model_version": metadata["model_version"], "max_input_tokens": metadata["max_input_tokens"], "generation_parameters": {"max_new_tokens": metadata["max_new_tokens"], **metadata["generation_config"]}})
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=False)
        record.update(eligibility_counts(iter_raw_test_rows(), tokenizer, int(metadata["max_input_tokens"])))
        SummaryPipeline, _ = pipeline_imports()
        pipeline = SummaryPipeline()
        pipeline.load()
        record["hardware"] = {**hardware_environment(), "pipeline_loaded": True}
        rows = iter_eligible_rows(tokenizer, int(metadata["max_input_tokens"]), limit=args.limit)
        if sampled:
            sampled_rows = deterministic_sample(rows, args.sample_size, args.seed)
            manifest = sample_manifest(sampled_rows, sample_size_requested=args.sample_size, seed=args.seed, counts=record)
            json_dump(run_dir / "sample_manifest.json", manifest)
            record.update({"sample_size_requested": args.sample_size, "sample_size_actual": len(sampled_rows), "sampling_seed": args.seed, "sampling_method": manifest["selection_method"]})
            rows = sampled_rows
        values, failures = measure_pipeline(pipeline, rows, warmup_runs=args.warmup_runs)
        with (run_dir / "latencies.jsonl").open("w", encoding="utf-8", newline="\n") as output:
            for item in values:
                output.write(json.dumps(item, ensure_ascii=False) + "\n")
        successful = [item["generation_time_ms"] for item in values if item["status"] == "measured"]
        record.update(latency_summary(successful))
        record["failed_count"] = failures
        if sampled:
            latency_met = latency_target_met(record)
            course_pass = not failures and latency_met
            record.update({"status": "completed" if course_pass else "acceptance_failed", "acceptance_profile": "course_sampled", "course_sampled_acceptance": course_pass, "full_acceptance": False, "latency_target_met": latency_met, "c2_14_required": not latency_met, "b2_14_required": not latency_met, "decision_reason": "initial sampled benchmark already meets latency target" if latency_met else "sampled benchmark does not meet latency target"})
        elif args.limit is not None:
            record.update({"status": "smoke_completed" if not failures else "failed", "acceptance_status": "not_applicable_limited_run"})
        elif failures:
            record.update({"status": "failed", "acceptance_status": "failed", "error": "pipeline_generation_failures"})
        elif record["latency_pass_rate"] >= 0.95 and record["p95_generation_time_ms"] < LATENCY_THRESHOLD_MS:
            record.update({"status": "completed", "acceptance_status": "passed"})
        else:
            record.update({"status": "acceptance_failed", "acceptance_status": "failed"})
        json_dump(run_dir / "metrics.json", {key: record[key] for key in ("sample_count", "avg_generation_time_ms", "median_generation_time_ms", "p95_generation_time_ms", "min_generation_time_ms", "max_generation_time_ms", "latency_pass_count", "latency_pass_rate", "latency_threshold_ms")})
    except Exception as exc:
        record.update({"status": "failed", "acceptance_status": "failed", "error": f"{type(exc).__name__}: {exc}"})
        raise
    finally:
        record["timestamp_end"] = utc_now()
        json_dump(run_dir / "run.json", record)
        print(run_dir)


if __name__ == "__main__":
    main()
