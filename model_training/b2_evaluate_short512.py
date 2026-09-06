"""B2-SHORT512：在完全相同 dev_lt512 上只读评价一个模型。"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import torch
import yaml
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from model_training.b2_data import ROOT
from model_training.b2_rouge import EVALUATOR_VERSION, score
from model_training.b2_short512_common import (EXPECTED_COUNTS, RUNS_DIR, TOKENIZER_REPOSITORY, TOKENIZER_REVISION,
    iter_manifest_rows, load_manifest, manifest_fingerprint, utc_now, verify_manifest_domain)


def main() -> None:
    """在固定生成参数下覆盖全部 5734 条 dev_lt512。"""
    parser = argparse.ArgumentParser(description="short512 dev 评价")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--parent-run-id", required=True)
    parser.add_argument("--label", choices=("new", "old"), required=True)
    args = parser.parse_args()
    config = yaml.safe_load(Path(__file__).with_name("config_short512.yaml").read_text(encoding="utf-8"))
    manifest_path = ROOT / config["dataset"]["validation_manifest"]
    entries = load_manifest(manifest_path); stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"b2-short512-{stamp}-{args.label}-dev-validation"; run_dir = RUNS_DIR / run_id; run_dir.mkdir(parents=True, exist_ok=False)
    source = Path(args.model_dir).resolve()
    record = {"run_id": run_id, "parent_run_id": args.parent_run_id, "timestamp_start": utc_now(), "task": "B2-SHORT512-VALIDATION", "experiment_type": "validation_short_domain", "formal_result": True, "domain": "token_count_lt_512", "dataset": "CNewSum", "validation_split": "dev_lt512", "sample_count": EXPECTED_COUNTS["dev"], "model_role": args.label, "model_source": str(source.relative_to(ROOT)), "tokenizer_source": TOKENIZER_REPOSITORY, "tokenizer_revision": TOKENIZER_REVISION, "evaluator": EVALUATOR_VERSION, "generation_parameters": config["evaluation"], "dev_manifest": manifest_fingerprint(manifest_path), "test_model_evaluation": False, "status": "running"}
    (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        if not torch.cuda.is_available(): raise RuntimeError("cuda_environment")
        tokenizer = AutoTokenizer.from_pretrained(source, local_files_only=True, trust_remote_code=False)
        verify_manifest_domain("dev", entries, tokenizer)
        model = AutoModelForSeq2SeqLM.from_pretrained(source, local_files_only=True, trust_remote_code=False).cuda().eval()
        scores = []; lengths = []; empty = 0; processed = 0; pending = []
        def flush(output):
            nonlocal empty, processed
            inputs = tokenizer([item["article"] for item in pending], max_length=512, truncation=True, padding=True, return_tensors="pt").to("cuda")
            generated = model.generate(**inputs, max_new_tokens=80, num_beams=2, length_penalty=1.0, early_stopping=True)
            for item, prediction in zip(pending, tokenizer.batch_decode(generated, skip_special_tokens=True), strict=True):
                metric = score(prediction, item["summary"]); scores.append(metric); lengths.append(len(prediction)); empty += int(not prediction.strip()); processed += 1
                output.write(json.dumps({"id": item["id"], **metric, "prediction_char_length": len(prediction)}, ensure_ascii=False) + "\n")
            pending.clear()
        with (run_dir / "metrics.jsonl").open("w", encoding="utf-8") as output, torch.inference_mode():
            for row in iter_manifest_rows("dev", entries):
                pending.append(row)
                if len(pending) == 8: flush(output)
            if pending: flush(output)
        if processed != EXPECTED_COUNTS["dev"]: raise RuntimeError(f"validation_coverage_mismatch:{processed}")
        summary = {"sample_count": processed, "validation_rouge1": statistics.fmean(item["rouge1"] for item in scores), "validation_rouge2": statistics.fmean(item["rouge2"] for item in scores), "validation_rougeL": statistics.fmean(item["rougeL"] for item in scores), "validation_quality_pass_rate": sum(item["rougeL"] >= .40 for item in scores) / processed, "validation_rougeL_median": statistics.median(item["rougeL"] for item in scores), "generated_length_mean": statistics.fmean(lengths), "generated_length_median": statistics.median(lengths), "empty_generation_count": empty}
        (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        record.update({"status": "completed", "timestamp_end": utc_now(), **summary, "artifacts": ["metrics.jsonl", "summary.json"]})
    except Exception as exc:
        record.update({"status": "failed", "timestamp_end": utc_now(), "error_type": type(exc).__name__, "error_message": str(exc)})
        raise
    finally:
        (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run_id)


if __name__ == "__main__": main()
