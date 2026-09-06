"""B2-04 单候选、train/dev-only CUDA pilot。"""

from __future__ import annotations

import hashlib
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
from torch.optim import AdamW
from torch.utils.data import DataLoader
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from model_training.b2_data import PROCESSED_DIR, RUNS_DIR, stream_jsonl, utc_now
from model_training.b2_rouge import EVALUATOR_VERSION, score

MODEL = "Langboat/mengzi-t5-base"
SEED = 42
TRAIN_COUNT = 2048
DEV_COUNT = 256
MAX_SOURCE = 512
MAX_TARGET = 80
BATCH_SIZE = 2
ACCUMULATION = 8


def reservoir(path: Path, count: int, seed: int) -> list[dict]:
    """稳定 seed 的流式 reservoir sampling，不读取 test。"""
    rng = random.Random(seed); chosen: list[dict] = []
    for index, (_, item, error) in enumerate(stream_jsonl(path)):
        if error or item is None: raise ValueError(f"{path}:{index + 1}: {error}")
        if index < count: chosen.append(item)
        else:
            replacement = rng.randint(0, index)
            if replacement < count: chosen[replacement] = item
    return chosen


def fingerprint(rows: list[dict]) -> str:
    value = "\n".join(hashlib.sha256(json.dumps({"id": row["id"], "article": row["article"], "summary": row["summary"]}, ensure_ascii=False, sort_keys=True).encode()).hexdigest() for row in rows)
    return hashlib.sha256(value.encode()).hexdigest()


def collate(tokenizer, rows: list[dict]) -> dict[str, torch.Tensor]:
    inputs = tokenizer([row["article"] for row in rows], max_length=MAX_SOURCE, truncation=True, padding=True, return_tensors="pt")
    labels = tokenizer(text_target=[row["summary"] for row in rows], max_length=MAX_TARGET, truncation=True, padding=True, return_tensors="pt").input_ids
    labels[labels == tokenizer.pad_token_id] = -100
    inputs["labels"] = labels
    return inputs


def main() -> None:
    run_id = "b2-04-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-mengzi-pilot"
    run_dir = RUNS_DIR / run_id; run_dir.mkdir(parents=True)
    record = {"run_id": run_id, "parent_run_id": "b2-04-20260905T085316Z-mengzi-smoke", "timestamp_start": utc_now(), "task": "B2-04", "experiment_type": "pilot", "formal_result": False, "candidate_model": MODEL, "model_source": MODEL, "tokenizer_source": MODEL, "license": "apache-2.0", "contamination_risk": "model card does not document CNewSum fine-tuning", "dataset": "CNewSum", "dataset_split": ["train", "dev"], "seed": SEED, "test_model_evaluation": False, "corpus_rougeL": None, "quality_pass_rate": None, "avg_generation_time_ms": None, "p95_generation_time_ms": None, "latency_pass_rate": None, "status": "failed"}
    try:
        if not torch.cuda.is_available(): raise RuntimeError("cuda_environment")
        torch.manual_seed(SEED); torch.cuda.manual_seed_all(SEED)
        train_rows = reservoir(PROCESSED_DIR / "train.jsonl", TRAIN_COUNT, SEED)
        dev_rows = reservoir(PROCESSED_DIR / "dev.jsonl", DEV_COUNT, SEED)
        (run_dir / "pilot_ids.json").write_text(json.dumps({"train_ids": [x["id"] for x in train_rows], "dev_ids": [x["id"] for x in dev_rows]}, ensure_ascii=False), encoding="utf-8")
        tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=False)
        model = AutoModelForSeq2SeqLM.from_pretrained(MODEL, trust_remote_code=False).cuda().train()
        optimizer = AdamW(model.parameters(), lr=2e-5)
        loader = DataLoader(train_rows, batch_size=BATCH_SIZE, shuffle=True, generator=torch.Generator().manual_seed(SEED), collate_fn=lambda rows: collate(tokenizer, rows))
        losses: list[float] = []; start = time.perf_counter(); optimizer.zero_grad(set_to_none=True)
        for step, batch in enumerate(loader, 1):
            batch = {key: value.cuda(non_blocking=True) for key, value in batch.items()}
            result = model(**batch); loss = result.loss / ACCUMULATION; loss.backward(); losses.append(float(result.loss.detach().cpu()))
            if step % ACCUMULATION == 0 or step == len(loader): optimizer.step(); optimizer.zero_grad(set_to_none=True)
        torch.cuda.synchronize(); training_seconds = time.perf_counter() - start
        model.eval(); generated: list[str] = []; references: list[str] = []; diagnostic_ms: list[float] = []
        with torch.inference_mode():
            for row in dev_rows:
                input_batch = tokenizer(row["article"], max_length=MAX_SOURCE, truncation=True, return_tensors="pt").to("cuda")
                one_start = time.perf_counter(); tokens = model.generate(**input_batch, max_new_tokens=MAX_TARGET, num_beams=2, length_penalty=1.0, early_stopping=True); torch.cuda.synchronize()
                diagnostic_ms.append((time.perf_counter() - one_start) * 1000)
                generated.append(tokenizer.batch_decode(tokens, skip_special_tokens=True)[0]); references.append(row["summary"])
        sample_scores = [score(pred, ref) for pred, ref in zip(generated, references)]
        metrics = {key: sum(row[key] for row in sample_scores) / len(sample_scores) for key in ("rouge1", "rouge2", "rougeL")}
        quality = sum(row["rougeL"] >= .40 for row in sample_scores) / len(sample_scores)
        model.save_pretrained(run_dir / "checkpoint", safe_serialization=True); tokenizer.save_pretrained(run_dir / "checkpoint")
        (run_dir / "metrics.jsonl").write_text("\n".join(json.dumps({"index": i, **value}, ensure_ascii=False) for i, value in enumerate(sample_scores)) + "\n", encoding="utf-8")
        record.update({"status": "completed", "sample_count": {"train": len(train_rows), "dev": len(dev_rows)}, "dataset_fingerprint": {"train": fingerprint(train_rows), "dev": fingerprint(dev_rows)}, "training_parameters": {"learning_rate": 2e-5, "batch_size": BATCH_SIZE, "gradient_accumulation": ACCUMULATION, "max_source_length": MAX_SOURCE, "max_target_length": MAX_TARGET}, "generation_parameters": {"num_beams": 2, "max_new_tokens": MAX_TARGET, "length_penalty": 1.0}, "evaluator": EVALUATOR_VERSION, "validation_rouge1": metrics["rouge1"], "validation_rouge2": metrics["rouge2"], "validation_rougeL": metrics["rougeL"], "validation_quality_pass_rate": quality, "train_loss": sum(losses) / len(losses), "peak_gpu_memory": torch.cuda.max_memory_allocated(), "duration_seconds": training_seconds, "diagnostic_generation_mean_ms": sum(diagnostic_ms) / len(diagnostic_ms), "empty_generation_count": sum(not text.strip() for text in generated), "best_checkpoint": "checkpoint", "artifacts": ["checkpoint", "pilot_ids.json", "metrics.jsonl"], "notes": "裸模型生成时间仅作诊断；未使用或读取 test。"})
    except Exception as exc:
        record.update({"error_type": type(exc).__name__, "error_message": str(exc)})
        raise
    finally:
        record["timestamp_end"] = utc_now()
        (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run_dir)


if __name__ == "__main__":
    main()
