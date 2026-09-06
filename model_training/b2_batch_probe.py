"""以 train_lt512 固定样本进行短时真实训练 batch probe，不保存模型。"""

from __future__ import annotations

import hashlib
import json
import random
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from torch.optim import AdamW
from transformers import AutoModelForSeq2SeqLM

from model_training.b2_data import PROCESSED_DIR, ROOT, stream_jsonl
from model_training.b2_lt512_stats import (FORMAL_MODEL_DIR, FORMAL_RUN, MAX_SOURCE_LENGTH, TOKENIZER_REPOSITORY,
                                            TOKENIZER_REVISION, environment, estimate_training_seconds,
                                            formal_model_fingerprints, load_frozen_tokenizer, percentile)

RUNS_DIR = ROOT / "runtime" / "training_runs"
SEED = 42
MAX_TARGET_LENGTH = 80
WARMUP_MICRO_BATCHES = 4
MEASURED_MICRO_BATCHES = 24
CONFIGURATIONS = ((2, 8), (4, 4), (8, 2))


def utc_now() -> str:
    """返回可用于运行目录的 UTC 时间。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def latest_statistics() -> dict[str, Any]:
    """找到最近成功的本任务统计运行，避免猜测 manifest。"""
    candidates: list[tuple[Path, dict[str, Any]]] = []
    for path in RUNS_DIR.glob("b2-analysis-*-lt512-stats/lt512_statistics.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") == "completed":
            candidates.append((path, data))
    if not candidates:
        raise FileNotFoundError("未找到成功的 B2-ANALYSIS-LT512 统计运行")
    return max(candidates, key=lambda item: item[0].parent.name)[1]


def load_manifest(path: str) -> list[dict[str, Any]]:
    """读取仅含 ID、source_index、token_count 的轻量 manifest。"""
    manifest_path = ROOT / path
    return [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line]


def select_probe_entries(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """用固定 seed 从典型分位和近上限域选择可复现样本。"""
    if len(entries) < 64:
        raise ValueError("train_lt512 样本不足以建立 probe")
    ordered = sorted(entries, key=lambda item: (item["token_count"], item["source_index"]))
    rng = random.Random(SEED)
    chosen: dict[int, dict[str, Any]] = {}
    representative: list[dict[str, Any]] = []
    for target in (percentile([item["token_count"] for item in ordered], .50), percentile([item["token_count"] for item in ordered], .75), percentile([item["token_count"] for item in ordered], .90)):
        nearby = sorted(ordered, key=lambda item: (abs(item["token_count"] - target), item["source_index"]))[:128]
        rng.shuffle(nearby)
        for item in nearby:
            if item["source_index"] not in chosen:
                chosen[item["source_index"]] = item; representative.append(item)
            if len(representative) % 8 == 0:
                break
    stress_candidates = [item for item in ordered if 480 <= item["token_count"] < 512]
    stress_rule = "480 <= token_count < 512"
    if len(stress_candidates) < 32:
        stress_candidates = [item for item in ordered if 448 <= item["token_count"] < 512]
        stress_rule = "448 <= token_count < 512"
    if len(stress_candidates) < 32:
        raise ValueError("近上限 train_lt512 样本不足 32 条")
    rng.shuffle(stress_candidates)
    return {"representative": representative, "stress": stress_candidates[:32], "stress_rule": stress_rule}


def materialize_samples(selected: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """仅流式回读 train，按 source_index 提取已选小样本。"""
    target_indexes = {item["source_index"] for key in ("representative", "stress") for item in selected[key]}
    rows: dict[int, dict[str, Any]] = {}
    for source_index, (_, row, error) in enumerate(stream_jsonl(PROCESSED_DIR / "train.jsonl")):
        if error or row is None:
            raise ValueError(f"train:{source_index + 1}: {error}")
        if source_index in target_indexes:
            rows[source_index] = row
    if len(rows) != len(target_indexes):
        raise ValueError("probe source_index 无法完整映射回 train")
    result: dict[str, list[dict[str, Any]]] = {"stress_rule": selected["stress_rule"]}
    for name in ("representative", "stress"):
        result[name] = [{**item, "article": rows[item["source_index"]]["article"], "summary": rows[item["source_index"]]["summary"]} for item in selected[name]]
    return result


def sample_metadata(samples: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """输出不含正文的样本审计信息与稳定指纹。"""
    output: dict[str, Any] = {"seed": SEED, "stress_rule": samples["stress_rule"]}
    for name in ("representative", "stress"):
        rows = [{key: item[key] for key in ("source_index", "id", "token_count")} for item in samples[name]]
        text = "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for item in rows)
        output[name] = {"count": len(rows), "samples": rows, "fingerprint": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    return output


def collate(tokenizer: Any, rows: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
    """复用正式训练的动态 padding、512 输入和 80 输出长度。"""
    inputs = tokenizer([row["article"] for row in rows], max_length=MAX_SOURCE_LENGTH, truncation=True, padding=True, return_tensors="pt")
    labels = tokenizer(text_target=[row["summary"] for row in rows], max_length=MAX_TARGET_LENGTH, truncation=True, padding=True, return_tensors="pt").input_ids
    labels[labels == tokenizer.pad_token_id] = -100
    inputs["labels"] = labels
    return inputs


def cycle_batches(rows: list[dict[str, Any]], batch_size: int, total: int, seed_offset: int) -> list[list[dict[str, Any]]]:
    """生成固定 seed 的完整微批，保证各候选重复使用同一 probe 数据池。"""
    rng = random.Random(SEED + seed_offset)
    ordered = list(rows); rng.shuffle(ordered)
    return [[ordered[(step * batch_size + offset) % len(ordered)] for offset in range(batch_size)] for step in range(total)]


def run_case(tokenizer: Any, rows: list[dict[str, Any]], probe_kind: str, batch_size: int, accumulation: int) -> dict[str, Any]:
    """执行真实 forward/backward/optimizer probe，捕获 OOM 并保留记录。"""
    result: dict[str, Any] = {"probe_kind": probe_kind, "batch_size": batch_size, "gradient_accumulation_steps": accumulation,
                              "effective_batch_size": batch_size * accumulation, "warmup_micro_batches": WARMUP_MICRO_BATCHES,
                              "measured_micro_batches": MEASURED_MICRO_BATCHES, "precision": "fp32", "status": "running"}
    model = optimizer = None
    try:
        torch.cuda.empty_cache()
        model = AutoModelForSeq2SeqLM.from_pretrained(FORMAL_MODEL_DIR, trust_remote_code=False, local_files_only=True).cuda().train()
        optimizer = AdamW(model.parameters(), lr=2e-5)
        warmup = cycle_batches(rows, batch_size, WARMUP_MICRO_BATCHES, batch_size)
        for batch_rows in warmup:
            batch = {key: value.cuda(non_blocking=True) for key, value in collate(tokenizer, batch_rows).items()}
            (model(**batch).loss / accumulation).backward()
        optimizer.step(); optimizer.zero_grad(set_to_none=True); torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats(); optimizer.zero_grad(set_to_none=True)
        durations: list[float] = []; samples_processed = input_tokens = optimizer_steps = 0
        measured = cycle_batches(rows, batch_size, MEASURED_MICRO_BATCHES, batch_size * 100)
        for micro_index, batch_rows in enumerate(measured, 1):
            batch = {key: value.cuda(non_blocking=True) for key, value in collate(tokenizer, batch_rows).items()}
            torch.cuda.synchronize(); started = time.perf_counter()
            (model(**batch).loss / accumulation).backward()
            if micro_index % accumulation == 0:
                optimizer.step(); optimizer.zero_grad(set_to_none=True); optimizer_steps += 1
            torch.cuda.synchronize()
            durations.append((time.perf_counter() - started) * 1000)
            samples_processed += batch_size; input_tokens += int(batch["attention_mask"].sum().item())
        if MEASURED_MICRO_BATCHES % accumulation:
            optimizer.step(); optimizer.zero_grad(set_to_none=True); optimizer_steps += 1
        measured_seconds = sum(durations) / 1000
        properties = torch.cuda.get_device_properties(0)
        allocated, reserved, total = torch.cuda.max_memory_allocated(), torch.cuda.max_memory_reserved(), properties.total_memory
        result.update({"status": "completed", "optimizer_steps": optimizer_steps, "samples_processed": samples_processed,
                       "input_tokens_processed": input_tokens, "measured_seconds": measured_seconds,
                       "samples_per_second": samples_processed / measured_seconds, "input_tokens_per_second": input_tokens / measured_seconds,
                       "mean_step_ms": statistics.fmean(durations), "p50_step_ms": percentile([int(value * 1000) for value in durations], .50) / 1000,
                       "p95_step_ms": percentile([int(value * 1000) for value in durations], .95) / 1000,
                       "peak_allocated_bytes": allocated, "peak_reserved_bytes": reserved, "gpu_total_vram_bytes": total,
                       "peak_allocated_ratio": allocated / total, "peak_reserved_ratio": reserved / total,
                       "peak_allocated_gib": allocated / 1024 ** 3, "peak_reserved_gib": reserved / 1024 ** 3})
    except torch.cuda.OutOfMemoryError as exc:
        result.update({"status": "oom", "error_type": type(exc).__name__, "error_message": str(exc)})
    except Exception as exc:
        result.update({"status": "failed", "error_type": type(exc).__name__, "error_message": str(exc)})
    finally:
        del optimizer, model
        torch.cuda.empty_cache()
    return result


def recommendation(results: list[dict[str, Any]]) -> dict[str, Any]:
    """只从 stress 稳定、至少 10% 显存余量的结果推荐配置。"""
    candidates = [row for row in results if row["probe_kind"] == "stress" and row["status"] == "completed" and row["peak_allocated_ratio"] <= .90]
    if not candidates:
        return {"recommended_batch_size": None, "recommended_gradient_accumulation_steps": None, "reason": "没有同时满足 stress 稳定和至少 10% allocated VRAM 余量的候选。"}
    best = max(candidates, key=lambda row: row["samples_per_second"])
    return {"recommended_batch_size": best["batch_size"], "recommended_gradient_accumulation_steps": best["gradient_accumulation_steps"],
            "effective_batch_size": best["effective_batch_size"], "basis": "stress probe 稳定通过、allocated VRAM 保留至少 10% 余量，且 samples/s 最高。",
            "samples_per_second": best["samples_per_second"], "peak_allocated_ratio": best["peak_allocated_ratio"]}


def main() -> None:
    """运行 2/4/8 的小型训练 probe，必要时才尝试 16。"""
    if not torch.cuda.is_available():
        raise RuntimeError("cuda_environment")
    statistics_data = latest_statistics()
    entries = load_manifest(statistics_data["splits"]["train"]["lt512_manifest"]["path"])
    samples = materialize_samples(select_probe_entries(entries))
    metadata = sample_metadata(samples)
    run_id = "b2-analysis-" + utc_now() + "-batch-probe"
    run_dir = RUNS_DIR / run_id; run_dir.mkdir(parents=True, exist_ok=False)
    tokenizer = load_frozen_tokenizer()
    record: dict[str, Any] = {"run_id": run_id, "task": "B2-ANALYSIS-BATCH-PROBE", "experiment_type": "batch_probe", "formal_result": False,
                               "timestamp_start": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "dataset": "CNewSum", "dataset_split": ["train_lt512"],
                               "test_model_evaluation": False, "corpus_rougeL": None, "quality_pass_rate": None, "p95_generation_time_ms": None,
                               "latency_pass_rate": None, "model_repository": TOKENIZER_REPOSITORY, "model_revision": TOKENIZER_REVISION,
                               "model_load_source": str(FORMAL_MODEL_DIR.relative_to(ROOT)),
                               "tokenizer_repository": TOKENIZER_REPOSITORY, "tokenizer_revision": TOKENIZER_REVISION, "environment": environment(), "status": "running"}
    model_before = formal_model_fingerprints()
    (run_dir / "probe_samples.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    results: list[dict[str, Any]] = []
    try:
        for batch_size, accumulation in CONFIGURATIONS:
            for probe_kind in ("representative", "stress"):
                result = run_case(tokenizer, samples[probe_kind], probe_kind, batch_size, accumulation)
                results.append(result)
                (run_dir / "batch_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            if results[-1]["status"] == "oom":
                break
        stress_eight = next((row for row in results if row["probe_kind"] == "stress" and row["batch_size"] == 8), None)
        if stress_eight and stress_eight["status"] == "completed" and stress_eight["peak_allocated_ratio"] < .70:
            for probe_kind in ("representative", "stress"):
                results.append(run_case(tokenizer, samples[probe_kind], probe_kind, 16, 1))
        recommended = recommendation(results)
        formal = json.loads(FORMAL_RUN.read_text(encoding="utf-8"))
        estimate = estimate_training_seconds(int(statistics_data["splits"]["train"]["lt512_count"]), int(formal["sample_count"]), float(formal["duration_seconds"]), recommended.get("samples_per_second"))
        model_after = formal_model_fingerprints()
        if model_after != model_before:
            raise RuntimeError("正式模型文件指纹在 batch probe 期间发生变化")
        record.update({"status": "completed", "timestamp_end": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "results": results,
                       "recommended": recommended, "training_time_estimates": estimate, "previous_formal_duration_seconds": formal["duration_seconds"],
                       "model_files_unchanged": True})
    except Exception as exc:
        record.update({"status": "failed", "timestamp_end": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "error_type": type(exc).__name__, "error_message": str(exc)})
        raise
    finally:
        (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run_dir)


if __name__ == "__main__":
    main()
