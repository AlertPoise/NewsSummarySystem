"""B2-07 的完整 CNewSum CUDA 微调。"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
import yaml
from torch.optim import AdamW
from torch.utils.data import DataLoader, IterableDataset
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from model_training.b2_data import PROCESSED_DIR, RUNS_DIR, stream_jsonl, utc_now


class TrainRows(IterableDataset):
    """流式提供完整 train split，避免将 690MB 原始数据装入 RAM。"""
    def __iter__(self):
        for line_no, row, error in stream_jsonl(PROCESSED_DIR / "train.jsonl"):
            if error or row is None: raise ValueError(f"train:{line_no}: {error}")
            yield row


def main() -> None:
    config = yaml.safe_load((Path(__file__).with_name("config.yaml")).read_text(encoding="utf-8"))
    training, model_config, evaluation = config["training"], config["model"], config["evaluation"]
    run_id = "b2-07-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-r0-full-train"
    run_dir = RUNS_DIR / run_id; run_dir.mkdir(parents=True)
    record = {"run_id": run_id, "parent_run_id": "b2-06-20260905T091100Z-training-parameters", "timestamp_start": utc_now(), "task": "B2-07", "experiment_type": "formal_training", "formal_result": True, "tuning_round": 0, "candidate_model": model_config["checkpoint"], "model_source": model_config["checkpoint"], "model_revision": model_config["revision"], "tokenizer_source": model_config["checkpoint"], "tokenizer_revision": model_config["revision"], "license": "apache-2.0", "contamination_risk": "model card does not document CNewSum-trained fine-tuning", "dataset": "CNewSum", "train_file": "processed/train.jsonl", "validation_file": "processed/dev.jsonl", "dataset_split": ["train"], "sample_count": 275596, "seed": training["seed"], "training_parameters": training, "generation_parameters": {"num_beams": evaluation["num_beams"], "max_new_tokens": training["max_target_length"], "length_penalty": evaluation["length_penalty"]}, "test_model_evaluation": False, "corpus_rougeL": None, "quality_pass_rate": None, "avg_generation_time_ms": None, "p95_generation_time_ms": None, "latency_pass_rate": None, "status": "running", "artifacts": ["metrics.jsonl", "checkpoint"]}
    (run_dir / "config_snapshot.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics_path = run_dir / "metrics.jsonl"
    try:
        if not torch.cuda.is_available(): raise RuntimeError("cuda_environment")
        torch.manual_seed(training["seed"]); torch.cuda.manual_seed_all(training["seed"])
        tokenizer = AutoTokenizer.from_pretrained(model_config["checkpoint"], revision=model_config["revision"], trust_remote_code=False)
        net = AutoModelForSeq2SeqLM.from_pretrained(model_config["checkpoint"], revision=model_config["revision"], trust_remote_code=False).cuda().train()
        optimizer = AdamW(net.parameters(), lr=float(training["learning_rate"]))
        def collate(rows):
            inputs = tokenizer([row["article"] for row in rows], max_length=training["max_source_length"], truncation=True, padding=True, return_tensors="pt")
            labels = tokenizer(text_target=[row["summary"] for row in rows], max_length=training["max_target_length"], truncation=True, padding=True, return_tensors="pt").input_ids
            labels[labels == tokenizer.pad_token_id] = -100; inputs["labels"] = labels
            return inputs
        loader = DataLoader(TrainRows(), batch_size=training["per_device_train_batch_size"], collate_fn=collate)
        accumulation = training["gradient_accumulation_steps"]; losses = []; start = time.perf_counter(); optimizer.zero_grad(set_to_none=True)
        with metrics_path.open("w", encoding="utf-8") as metric_log:
            for step, batch in enumerate(loader, 1):
                batch = {key: value.cuda(non_blocking=True) for key, value in batch.items()}
                result = net(**batch); loss = result.loss / accumulation; loss.backward(); losses.append(float(result.loss.detach().cpu()))
                if step % accumulation == 0: optimizer.step(); optimizer.zero_grad(set_to_none=True)
                if step % 100 == 0: metric_log.write(json.dumps({"step": step, "train_loss_window": sum(losses[-100:]) / min(len(losses), 100), "elapsed_seconds": time.perf_counter() - start}, ensure_ascii=False) + "\n"); metric_log.flush()
            if step % accumulation: optimizer.step(); optimizer.zero_grad(set_to_none=True)
        torch.cuda.synchronize(); duration = time.perf_counter() - start
        net.save_pretrained(run_dir / "checkpoint", safe_serialization=True); tokenizer.save_pretrained(run_dir / "checkpoint")
        record.update({"status": "completed", "timestamp_end": utc_now(), "duration_seconds": duration, "train_loss": sum(losses) / len(losses), "peak_gpu_memory": torch.cuda.max_memory_allocated(), "best_checkpoint": "checkpoint", "notes": "完整 train 单 epoch CUDA 微调完成；B2-08 将独立在完整 dev 上评价。"})
    except Exception as exc:
        record.update({"status": "failed", "timestamp_end": utc_now(), "error_type": type(exc).__name__, "error_message": str(exc)})
        raise
    finally:
        (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run_dir)


if __name__ == "__main__":
    main()
