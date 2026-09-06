"""B2-SHORT512：只训练 train_lt512 一次完整 epoch。"""

from __future__ import annotations

import json
import math
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

import torch
import yaml
from torch.optim import AdamW
from torch.utils.data import DataLoader, IterableDataset
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from model_training.b2_data import ROOT
from model_training.b2_short512_common import (EXPECTED_COUNTS, EXPECTED_TOTALS, RUNS_DIR, TOKENIZER_REPOSITORY,
    TOKENIZER_REVISION, disk_usage, environment, git_state, iter_manifest_rows, load_manifest, manifest_fingerprint,
    model_fingerprint, utc_now, verify_base_snapshot, verify_manifest_domain, verify_old_model, BASE_MODEL_SNAPSHOT, OLD_MODEL_DIR)


class ManifestRows(IterableDataset):
    """基于已验证 manifest 流式返回短文本训练样本。"""
    def __init__(self, entries): self.entries = entries
    def __iter__(self): yield from iter_manifest_rows("train", self.entries)


def main() -> None:
    """执行唯一一次 batch=4、梯度累积=4 的正式训练。"""
    parser = argparse.ArgumentParser(description="short512 正式训练")
    parser.add_argument("--dry-run", action="store_true", help="只执行训练前核验，不加载或训练模型")
    args = parser.parse_args()
    config_path = Path(__file__).with_name("config_short512.yaml")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")); training = config["training"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"b2-short512-{stamp}-r0-full-train"; run_dir = RUNS_DIR / run_id
    if run_dir.exists(): raise FileExistsError(run_dir)
    run_dir.mkdir(parents=True); checkpoint = run_dir / "checkpoint"
    train_manifest = ROOT / config["dataset"]["train_manifest"]
    dev_manifest = ROOT / config["dataset"]["validation_manifest"]
    record = {"run_id": run_id, "parent_run_id": "b2-short512-20260906T035804Z-r0-full-train", "previous_blocked_run": "b2-short512-20260906T035804Z-r0-full-train", "change_reason": "人工确认 B2-09 核心模型文件 SHA-256 未变化；新增 model_metadata.json 为后续 sidecar 元数据，不代表旧模型权重发生修改。按核心文件指纹重新定义 baseline integrity。", "timestamp_start": utc_now(),
              "task": "B2-SHORT512-TRAIN", "experiment_type": "formal_training_short_domain", "formal_result": True, "tuning_round": 0,
              "domain": "token_count_lt_512", "domain_definition": "tokenizer add_special_tokens=true, truncation=false, token_count<512",
              "candidate_model": config["model"]["checkpoint"], "model_source": config["model"]["checkpoint"], "model_revision": config["model"]["revision"],
              "tokenizer_source": TOKENIZER_REPOSITORY, "tokenizer_revision": TOKENIZER_REVISION, "license": "apache-2.0", "dataset": "CNewSum",
              "train_split": "train_lt512", "validation_split": "dev_lt512", "train_sample_count": EXPECTED_COUNTS["train"], "validation_sample_count": EXPECTED_COUNTS["dev"],
              "source_train_count": EXPECTED_TOTALS["train"], "source_dev_count": EXPECTED_TOTALS["dev"], "train_manifest": manifest_fingerprint(train_manifest),
              "dev_manifest": manifest_fingerprint(dev_manifest), "test_model_evaluation": False, "seed": training["seed"], "num_train_epochs": training["num_train_epochs"],
              "learning_rate": training["learning_rate"], "per_device_train_batch_size": training["per_device_train_batch_size"], "gradient_accumulation_steps": training["gradient_accumulation_steps"],
              "effective_batch_size": 16, "max_source_length": training["max_source_length"], "max_target_length": training["max_target_length"], "precision": "fp32", "optimizer": "AdamW",
              "generation_parameters": config["evaluation"], "status": "running", "corpus_rougeL": None, "quality_pass_rate": None, "avg_generation_time_ms": None,
              "p95_generation_time_ms": None, "latency_pass_rate": None, "artifacts": ["config_snapshot.yaml", "environment.json", "metrics.jsonl", "train.log", "artifacts.json", "checkpoint"]}
    (run_dir / "config_snapshot.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (run_dir / "environment.json").write_text(json.dumps({**environment(), "git": git_state(), "disk_usage_before": disk_usage()}, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        if not torch.cuda.is_available(): raise RuntimeError("cuda_environment")
        old_before = verify_old_model(); base_snapshot = verify_base_snapshot()
        tokenizer = AutoTokenizer.from_pretrained(OLD_MODEL_DIR, local_files_only=True, trust_remote_code=False)
        train_entries, dev_entries = load_manifest(train_manifest), load_manifest(dev_manifest)
        dry = {"train": verify_manifest_domain("train", train_entries, tokenizer), "dev": verify_manifest_domain("dev", dev_entries, tokenizer)}
        (run_dir / "dry_validation.json").write_text(json.dumps({"status": "passed", "checks": dry, "old_model_fingerprint": old_before, "base_model_snapshot": base_snapshot, "tokenizer_load": "runtime/models/news_summarizer local_files_only"}, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.dry_run:
            record.update({"status": "dry_validation_completed", "timestamp_end": utc_now(), "dry_validation": dry, "notes": "只执行训练前核验，未加载模型或开始训练。"})
            print(run_id)
            return
        torch.manual_seed(42); torch.cuda.manual_seed_all(42)
        model = AutoModelForSeq2SeqLM.from_pretrained(BASE_MODEL_SNAPSHOT, local_files_only=True, trust_remote_code=False).cuda().train()
        optimizer = AdamW(model.parameters(), lr=float(training["learning_rate"])); accumulation = int(training["gradient_accumulation_steps"])
        def collate(rows):
            inputs = tokenizer([row["article"] for row in rows], max_length=512, truncation=True, padding=True, return_tensors="pt")
            labels = tokenizer(text_target=[row["summary"] for row in rows], max_length=80, truncation=True, padding=True, return_tensors="pt").input_ids
            labels[labels == tokenizer.pad_token_id] = -100; inputs["labels"] = labels; return inputs
        loader = DataLoader(ManifestRows(train_entries), batch_size=4, collate_fn=collate)
        started = time.perf_counter(); losses = []; samples_seen = tokens_seen = optimizer_steps = 0; micro_steps = 0; optimizer.zero_grad(set_to_none=True)
        with (run_dir / "metrics.jsonl").open("w", encoding="utf-8") as metrics, (run_dir / "train.log").open("w", encoding="utf-8") as log:
            for micro_steps, batch in enumerate(loader, 1):
                tokens_seen += int(batch["attention_mask"].sum().item()); samples_seen += len(batch["input_ids"])
                batch = {key: value.cuda(non_blocking=True) for key, value in batch.items()}; output = model(**batch); raw_loss = float(output.loss.detach().cpu())
                if not math.isfinite(raw_loss): raise FloatingPointError("NaN_or_Inf_train_loss")
                (output.loss / accumulation).backward(); losses.append(raw_loss)
                if micro_steps % accumulation == 0:
                    optimizer.step(); optimizer.zero_grad(set_to_none=True); optimizer_steps += 1
                if micro_steps % 100 == 0:
                    elapsed = time.perf_counter() - started; item = {"step": micro_steps, "optimizer_step": optimizer_steps, "train_loss_window": sum(losses[-100:]) / min(100, len(losses)), "elapsed_seconds": elapsed, "samples_seen": samples_seen, "tokens_seen": tokens_seen, "samples_per_second": samples_seen / elapsed, "tokens_per_second": tokens_seen / elapsed, "allocated_gpu_memory": torch.cuda.memory_allocated(), "reserved_gpu_memory": torch.cuda.memory_reserved()}
                    metrics.write(json.dumps(item, ensure_ascii=False) + "\n"); metrics.flush(); log.write(json.dumps(item, ensure_ascii=False) + "\n"); log.flush()
            if micro_steps % accumulation:
                optimizer.step(); optimizer.zero_grad(set_to_none=True); optimizer_steps += 1
        torch.cuda.synchronize(); duration = time.perf_counter() - started
        if samples_seen != EXPECTED_COUNTS["train"]: raise RuntimeError(f"samples_processed_mismatch:{samples_seen}")
        model.save_pretrained(checkpoint, safe_serialization=True); tokenizer.save_pretrained(checkpoint)
        AutoTokenizer.from_pretrained(checkpoint, local_files_only=True); AutoModelForSeq2SeqLM.from_pretrained(checkpoint, local_files_only=True)
        old_after = verify_old_model()
        if old_before != old_after: raise RuntimeError("existing_formal_model_changed")
        artifacts = model_fingerprint(checkpoint); (run_dir / "artifacts.json").write_text(json.dumps(artifacts, ensure_ascii=False, indent=2), encoding="utf-8")
        record.update({"status": "completed", "timestamp_end": utc_now(), "duration_seconds": duration, "train_loss": sum(losses) / len(losses), "peak_gpu_memory_allocated": torch.cuda.max_memory_allocated(), "peak_gpu_memory_reserved": torch.cuda.max_memory_reserved(), "optimizer_steps": optimizer_steps, "micro_steps": micro_steps, "samples_processed": samples_seen, "training_samples_per_second": samples_seen / duration, "training_input_tokens_per_second": tokens_seen / duration, "best_checkpoint": str(checkpoint.relative_to(ROOT)), "local_files_only_reload": "PASS", "dry_validation": dry})
    except Exception as exc:
        record.update({"status": "failed", "timestamp_end": utc_now(), "duration_seconds": time.perf_counter() - started if "started" in locals() else None, "error_type": type(exc).__name__, "error_message": str(exc), "last_step": locals().get("micro_steps", 0)})
        raise
    finally:
        (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run_id)


if __name__ == "__main__": main()
