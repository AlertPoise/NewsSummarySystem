"""B2-08：仅在完整 CNewSum dev 上评价正式 checkpoint。"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from model_training.b2_data import PROCESSED_DIR, RUNS_DIR, stream_jsonl, utc_now
from model_training.b2_rouge import EVALUATOR_VERSION, score

SOURCE_RUN = "b2-07-20260905T091244Z-r0-full-train"
BATCH_SIZE = 8


def main() -> None:
    source = RUNS_DIR / SOURCE_RUN / "checkpoint"
    if not source.is_dir(): raise FileNotFoundError(f"正式训练 checkpoint 尚未完成：{source}")
    run_id = "b2-08-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-full-dev-validation"
    run_dir = RUNS_DIR / run_id; run_dir.mkdir(parents=True)
    record = {"run_id": run_id, "parent_run_id": SOURCE_RUN, "timestamp_start": utc_now(), "task": "B2-08", "experiment_type": "full_validation", "formal_result": True, "dataset": "CNewSum", "dataset_split": ["dev"], "sample_count": 14356, "evaluator": EVALUATOR_VERSION, "test_model_evaluation": False, "corpus_rougeL": None, "quality_pass_rate": None, "avg_generation_time_ms": None, "p95_generation_time_ms": None, "latency_pass_rate": None, "status": "running"}
    (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        if not torch.cuda.is_available(): raise RuntimeError("cuda_environment")
        tokenizer = AutoTokenizer.from_pretrained(source, local_files_only=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(source, local_files_only=True).cuda().eval()
        scores = []; lengths = []; empty = 0
        with (run_dir / "metrics.jsonl").open("w", encoding="utf-8") as output, torch.inference_mode():
            pending = []
            for index, (_, row, error) in enumerate(stream_jsonl(PROCESSED_DIR / "dev.jsonl"), 1):
                if error or row is None: raise ValueError(f"dev:{index}: {error}")
                pending.append(row)
                if len(pending) < BATCH_SIZE:
                    continue
                input_data = tokenizer([item["article"] for item in pending], max_length=512, truncation=True, padding=True, return_tensors="pt").to("cuda")
                generated = model.generate(**input_data, max_new_tokens=80, num_beams=2, length_penalty=1.0, early_stopping=True)
                for item, prediction in zip(pending, tokenizer.batch_decode(generated, skip_special_tokens=True)):
                    metric = score(prediction, item["summary"]); scores.append(metric); lengths.append(len(prediction)); empty += int(not prediction.strip())
                    output.write(json.dumps({"id": item["id"], **metric, "prediction_char_length": len(prediction)}, ensure_ascii=False) + "\n")
                pending = []
            if pending:
                input_data = tokenizer([item["article"] for item in pending], max_length=512, truncation=True, padding=True, return_tensors="pt").to("cuda")
                generated = model.generate(**input_data, max_new_tokens=80, num_beams=2, length_penalty=1.0, early_stopping=True)
                for item, prediction in zip(pending, tokenizer.batch_decode(generated, skip_special_tokens=True)):
                    metric = score(prediction, item["summary"]); scores.append(metric); lengths.append(len(prediction)); empty += int(not prediction.strip())
                    output.write(json.dumps({"id": item["id"], **metric, "prediction_char_length": len(prediction)}, ensure_ascii=False) + "\n")
        record.update({"status": "completed", "timestamp_end": utc_now(), "validation_rouge1": statistics.fmean(item["rouge1"] for item in scores), "validation_rouge2": statistics.fmean(item["rouge2"] for item in scores), "validation_rougeL": statistics.fmean(item["rougeL"] for item in scores), "validation_quality_pass_rate": sum(item["rougeL"] >= .40 for item in scores) / len(scores), "validation_rougeL_median": statistics.median(item["rougeL"] for item in scores), "generated_length_mean": statistics.fmean(lengths), "generated_length_median": statistics.median(lengths), "empty_generation_count": empty, "artifacts": ["metrics.jsonl"], "notes": "完整 dev 的裸模型 validation；不构成 B2-10 的 test/Pipeline 正式评价。"})
    except Exception as exc:
        record.update({"status": "failed", "timestamp_end": utc_now(), "error_type": type(exc).__name__, "error_message": str(exc)})
        raise
    finally:
        (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run_dir)


if __name__ == "__main__":
    main()
