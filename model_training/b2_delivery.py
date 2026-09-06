"""B2-13：从真实 B2-10 与 B2-14 运行记录生成给 A 的固定字段交付 JSON。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from model_training.b2_data import RUNS_DIR, utc_now
from model_training.b2_pipeline_eval_common import json_dump, make_run_dir

DELIVERY_FIELDS = ("model_name", "model_version", "dataset", "dataset_split", "sample_count", "rouge1", "rouge2", "rougeL", "avg_generation_time_ms", "p95_generation_time_ms")


def read_run(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "run.json").read_text(encoding="utf-8"))


def is_accepted_quality(run: dict[str, Any]) -> bool:
    return run.get("task") in ("B2-10", "B6-01") and run.get("formal_result") is True and run.get("acceptance_status") == "passed"


def is_accepted_final_benchmark(run: dict[str, Any]) -> bool:
    return run.get("task") == "B2-14" and run.get("formal_result") is True and run.get("acceptance_status") == "passed"


def is_course_sampled_quality(run: dict[str, Any]) -> bool:
    return run.get("task") == "B2-10" and run.get("evaluation_profile") == "course_sampled" and run.get("status") in ("completed", "acceptance_failed") and run.get("status") != "aborted"


def is_course_sampled_benchmark(run: dict[str, Any]) -> bool:
    return run.get("task") == "B2-11" and run.get("evaluation_profile") == "course_sampled" and run.get("status") in ("completed", "acceptance_failed") and run.get("status") != "aborted"


def build_payload(quality: dict[str, Any], benchmark: dict[str, Any]) -> dict[str, Any]:
    """组合两个通过硬门槛的正式结果，拒绝版本或数据范围不一致。"""
    if not is_accepted_quality(quality) or not is_accepted_final_benchmark(benchmark):
        raise ValueError("delivery_requires_accepted_B2_10_and_B2_14")
    if quality.get("model_version") != benchmark.get("model_version"):
        raise ValueError("model_version_mismatch")
    payload = {"model_name": quality["model_name"], "model_version": quality["model_version"], "dataset": "CNewSum", "dataset_split": "test", "sample_count": quality["evaluated_count"], "rouge1": quality["rouge1"], "rouge2": quality["rouge2"], "rougeL": quality["corpus_rougeL"], "avg_generation_time_ms": benchmark["avg_generation_time_ms"], "p95_generation_time_ms": benchmark["p95_generation_time_ms"]}
    missing = [field for field in DELIVERY_FIELDS if payload.get(field) is None]
    if missing:
        raise ValueError("delivery_missing:" + ",".join(missing))
    return payload


def build_course_sampled_payload(quality: dict[str, Any], benchmark: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """组合真实 sampled 评价，并生成不能被固定 API 字段承载的 provenance。"""
    if not is_course_sampled_quality(quality) or not is_course_sampled_benchmark(benchmark):
        raise ValueError("delivery_requires_course_sampled_runs")
    if quality.get("model_version") != benchmark.get("model_version"):
        raise ValueError("model_version_mismatch")
    payload = {"model_name": quality["model_name"], "model_version": quality["model_version"], "dataset": "CNewSum", "dataset_split": "test", "sample_count": quality["evaluated_count"], "rouge1": quality["rouge1"], "rouge2": quality["rouge2"], "rougeL": quality["corpus_rougeL"], "avg_generation_time_ms": benchmark["avg_generation_time_ms"], "p95_generation_time_ms": benchmark["p95_generation_time_ms"]}
    missing = [field for field in DELIVERY_FIELDS if payload.get(field) is None]
    if missing:
        raise ValueError("delivery_missing:" + ",".join(missing))
    provenance = {"evaluation_profile": "course_sampled", "quality_sample_size": quality["evaluated_count"], "performance_sample_size": benchmark["sample_count"], "seed": quality.get("sampling_seed"), "sampling_method": quality.get("sampling_method"), "full_test_count": quality["full_test_count"], "eligible_count": quality["eligible_count"], "excluded_count": quality["excluded_count"], "quality_run_id": quality["run_id"], "performance_run_id": benchmark["run_id"], "full_evaluation": False, "time_constraint_reason": "user_time_constraint", "course_sampled_acceptance": bool(quality.get("course_sampled_acceptance")) and bool(benchmark.get("course_sampled_acceptance")), "c2_14_required": benchmark.get("c2_14_required"), "b2_14_required": benchmark.get("b2_14_required")}
    return payload, provenance


def latest_run(predicate: Any) -> Path | None:
    candidates = sorted((item for item in RUNS_DIR.iterdir() if item.is_dir() and (item / "run.json").is_file()), key=lambda item: item.name, reverse=True)
    for path in candidates:
        try:
            if predicate(read_run(path)):
                return path
        except (OSError, json.JSONDecodeError):
            continue
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="B2-13 生成交给 A 的模型评价 JSON")
    parser.add_argument("--profile", choices=("full", "course-sampled"), default="full")
    parser.add_argument("--quality-run", type=Path, help="通过的 B2-10 运行目录")
    parser.add_argument("--benchmark-run", type=Path, help="通过的 B2-14 运行目录")
    args = parser.parse_args()
    run_id, run_dir = make_run_dir("b2-13", "course-sampled-delivery" if args.profile == "course-sampled" else "evaluation-delivery")
    record: dict[str, Any] = {"run_id": run_id, "timestamp_start": utc_now(), "task": "B2-13", "experiment_type": "evaluation_delivery", "formal_result": False, "status": "running", "blocked_by": None, "error": None}
    json_dump(run_dir / "run.json", record)
    try:
        quality_predicate = is_course_sampled_quality if args.profile == "course-sampled" else is_accepted_quality
        benchmark_predicate = is_course_sampled_benchmark if args.profile == "course-sampled" else is_accepted_final_benchmark
        quality_dir = args.quality_run or latest_run(quality_predicate)
        benchmark_dir = args.benchmark_run or latest_run(benchmark_predicate)
        if quality_dir is None or benchmark_dir is None:
            missing = []
            if quality_dir is None: missing.append("B2-10")
            if benchmark_dir is None: missing.append("B2-14")
            record.update({"status": "blocked", "blocked_by": missing, "error": "missing_accepted_dependency"})
            return
        quality, benchmark = read_run(quality_dir), read_run(benchmark_dir)
        if args.profile == "course-sampled":
            payload, provenance = build_course_sampled_payload(quality, benchmark)
            json_dump(run_dir / "evaluation_provenance.json", provenance)
            decision_id, decision_dir = make_run_dir("b2-performance-decision", "course-sampled")
            decision = {"run_id": decision_id, "timestamp_start": utc_now(), "timestamp_end": utc_now(), "task": "B2-PERFORMANCE-DECISION", "decision": "optimization_not_required" if not provenance["c2_14_required"] else "optimization_required", "based_on": benchmark["run_id"], "c2_14_required": provenance["c2_14_required"], "b2_14_required": provenance["b2_14_required"], "reason": benchmark.get("decision_reason"), "formal_result": False, "evaluation_profile": "course_sampled", "status": "completed"}
            json_dump(decision_dir / "run.json", decision)
            record["performance_decision_run"] = decision_id
            course_accepted = provenance["course_sampled_acceptance"]
            record.update({"status": "completed" if course_accepted else "acceptance_failed", "course_sampled_acceptance": course_accepted, "evaluation_profile": "course_sampled", "full_evaluation": False})
        else:
            payload = build_payload(quality, benchmark)
        json_dump(run_dir / "model_evaluation.json", payload)
        record.update({"status": "completed" if args.profile == "full" else record["status"], "formal_result": args.profile == "full", "quality_run": quality_dir.name, "benchmark_run": benchmark_dir.name, "delivery_path": "model_evaluation.json", "fields": list(DELIVERY_FIELDS)})
    except Exception as exc:
        record.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}"})
        raise
    finally:
        record["timestamp_end"] = utc_now()
        json_dump(run_dir / "run.json", record)
        print(run_dir)


if __name__ == "__main__":
    main()
