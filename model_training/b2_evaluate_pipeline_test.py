"""B2-10/B6-01：只经 C 正式 SummaryPipeline 的 CNewSum test ROUGE 评价。"""

from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any

from model_training.b2_data import ROOT, utc_now
from model_training.b2_metadata import load_json
from model_training.b2_pipeline_eval_common import (
    MODEL_DIR, QUALITY_THRESHOLD, aggregate_rouge, deterministic_sample, eligibility_counts, hardware_environment, iter_eligible_rows,
    iter_raw_test_rows, json_dump, make_run_dir, pipeline_imports, quality_summary, sample_manifest,
)
from model_training.b2_rouge import EVALUATOR_VERSION, score


def git_commit() -> str | None:
    """读取当前 commit；异常时留空而不伪造。"""
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def evaluate_pipeline(
    pipeline: Any,
    tokenizer: Any,
    input_too_long_error: type[BaseException],
    *,
    max_input_tokens: int,
    output: Any,
    limit: int | None = None,
    rows: Any = None,
) -> tuple[list[dict[str, float]], int, bool]:
    """流式调用唯一正式 Pipeline，返回成功评分、失败数与契约不一致标志。"""
    scores: list[dict[str, float]] = []
    failures = 0
    contract_mismatch = False
    selected_rows = rows if rows is not None else iter_eligible_rows(tokenizer, max_input_tokens, limit=limit)
    for row in selected_rows:
        base = {"id": row["id"], "article_token_count": row["article_token_count"], "reference": row["reference"]}
        try:
            result = pipeline.generate(row["article"])
            prediction = result.summary
            if not isinstance(prediction, str) or not prediction.strip():
                raise RuntimeError("pipeline_returned_empty_summary")
            item_score = score(prediction, row["reference"])
            scores.append(item_score)
            output.write(json.dumps({**base, "prediction": prediction, **item_score, "model_version": result.model_version, "generation_time_ms": result.generation_time_ms, "status": "evaluated"}, ensure_ascii=False) + "\n")
        except input_too_long_error as exc:
            failures += 1
            contract_mismatch = True
            output.write(json.dumps({**base, "prediction": None, "rouge1": None, "rouge2": None, "rougeL": None, "model_version": None, "status": "pipeline_contract_mismatch", "error": str(exc)}, ensure_ascii=False) + "\n")
        except Exception as exc:
            failures += 1
            output.write(json.dumps({**base, "prediction": None, "rouge1": None, "rouge2": None, "rougeL": None, "model_version": None, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False) + "\n")
        output.flush()
    return scores, failures, contract_mismatch


def main() -> None:
    parser = argparse.ArgumentParser(description="B2-10 完整 SummaryPipeline CNewSum test 评价")
    parser.add_argument("--stage", choices=("b2-10", "b6-recheck"), default="b2-10")
    parser.add_argument("--profile", choices=("full", "sampled"), default="full")
    parser.add_argument("--sample-size", type=int, default=300)
    parser.add_argument("--seed", default="20260907")
    parser.add_argument("--limit", type=int, help="仅 smoke；有限样本永不构成正式验收")
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0 or args.sample_size <= 0:
        parser.error("--limit 必须为正数")
    if args.profile == "sampled" and args.limit is not None:
        parser.error("sampled profile 不接受 --limit；请使用固定 --sample-size")
    prefix = "b2-10" if args.stage == "b2-10" else "b6-01"
    run_id, run_dir = make_run_dir(prefix, "course-sampled" if args.profile == "sampled" else "pipeline-test")
    record: dict[str, Any] = {"run_id": run_id, "parent_run_id": "b2-09-20260905T152641Z-export", "timestamp_start": utc_now(), "timestamp_end": None, "task": "B2-10" if args.stage == "b2-10" else "B6-01", "experiment_type": "pipeline_test_evaluation", "formal_result": args.profile == "full" and args.limit is None, "evaluation_profile": "course_sampled" if args.profile == "sampled" else "full", "evaluation_scope": "eligible_test_sample" if args.profile == "sampled" else "eligible_test_full", "full_evaluation": args.profile == "full" and args.limit is None, "git_commit": git_commit(), "dataset": "CNewSum", "dataset_split": "test", "model_name": None, "model_version": None, "tokenizer": None, "max_input_tokens": None, "generation_parameters": None, "full_test_count": None, "eligible_count": None, "excluded_count": None, "eligible_ratio": None, "evaluated_count": 0, "failed_count": 0, "rouge1": None, "rouge2": None, "rougeL": None, "corpus_rougeL": None, "quality_pass_count": 0, "quality_pass_rate": None, "quality_threshold": QUALITY_THRESHOLD, "evaluator": EVALUATOR_VERSION, "status": "running", "error": None, "hardware": None, "notes": "使用 C 的 SummaryPipeline.generate；范围外原文绝不调用 Pipeline。"}
    json_dump(run_dir / "run.json", record)
    try:
        metadata = load_json(MODEL_DIR / "model_metadata.json")
        record.update({"model_name": metadata["model_name"], "model_version": metadata["model_version"], "tokenizer": metadata["tokenizer"], "max_input_tokens": metadata["max_input_tokens"], "generation_parameters": {"max_new_tokens": metadata["max_new_tokens"], **metadata["generation_config"]}})
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=False)
        counts = eligibility_counts(iter_raw_test_rows(), tokenizer, int(metadata["max_input_tokens"]))
        record.update(counts)
        sampled_rows = None
        if args.profile == "sampled":
            sampled_rows = deterministic_sample(iter_eligible_rows(tokenizer, int(metadata["max_input_tokens"])), args.sample_size, args.seed)
            manifest = sample_manifest(sampled_rows, sample_size_requested=args.sample_size, seed=args.seed, counts=counts)
            json_dump(run_dir / "sample_manifest.json", manifest)
            record.update({"sample_size_requested": args.sample_size, "sample_size_actual": len(sampled_rows), "sampling_seed": args.seed, "sampling_method": manifest["selection_method"]})
        SummaryPipeline, InputTooLongError = pipeline_imports()
        pipeline = SummaryPipeline()
        pipeline.load()
        record["hardware"] = {**hardware_environment(), "pipeline_loaded": True}
        with (run_dir / "predictions.jsonl").open("w", encoding="utf-8", newline="\n") as output:
            values, failed, mismatch = evaluate_pipeline(pipeline, tokenizer, InputTooLongError, max_input_tokens=int(metadata["max_input_tokens"]), output=output, limit=args.limit, rows=sampled_rows)
        aggregate = aggregate_rouge(values)
        quality = quality_summary(values)
        record.update(aggregate)
        record.update(quality)
        record["failed_count"] = failed
        if args.profile == "sampled":
            course_pass = not failed and not mismatch and aggregate["corpus_rougeL"] is not None and aggregate["corpus_rougeL"] >= QUALITY_THRESHOLD and quality["quality_pass_rate"] is not None and quality["quality_pass_rate"] >= 0.95
            record.update({"status": "completed" if course_pass else "acceptance_failed", "acceptance_profile": "course_sampled", "course_sampled_acceptance": course_pass, "full_acceptance": False})
        elif args.limit is not None:
            record.update({"status": "smoke_completed" if not failed else "failed", "acceptance_status": "not_applicable_limited_run", "notes": record["notes"] + " --limit 运行仅为 smoke。"})
        elif mismatch:
            record.update({"status": "failed", "acceptance_status": "failed", "error": "pipeline_contract_mismatch"})
        elif failed:
            record.update({"status": "failed", "acceptance_status": "failed", "error": "pipeline_generation_failures"})
        elif aggregate["corpus_rougeL"] is not None and aggregate["corpus_rougeL"] >= QUALITY_THRESHOLD and quality["quality_pass_rate"] is not None and quality["quality_pass_rate"] >= 0.95:
            record.update({"status": "completed", "acceptance_status": "passed"})
        else:
            record.update({"status": "acceptance_failed", "acceptance_status": "failed"})
        json_dump(run_dir / "metrics.json", {key: record[key] for key in ("rouge1", "rouge2", "rougeL", "corpus_rougeL", "evaluated_count", "failed_count", "quality_pass_count", "quality_pass_rate", "quality_threshold", "evaluator")})
    except Exception as exc:
        record.update({"status": "failed", "acceptance_status": "failed", "error": f"{type(exc).__name__}: {exc}"})
        raise
    finally:
        record["timestamp_end"] = utc_now()
        json_dump(run_dir / "run.json", record)
    print(run_dir)


if __name__ == "__main__":
    main()
