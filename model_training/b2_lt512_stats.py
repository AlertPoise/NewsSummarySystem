"""统计 train/dev 的冻结 tokenizer 长度，不读取 test。"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import torch
import transformers
from transformers import AutoTokenizer

from model_training.b2_data import PROCESSED_DIR, ROOT, stream_jsonl

TOKENIZER_REPOSITORY = "Langboat/mengzi-t5-base"
TOKENIZER_REVISION = "6616a21ba6f42867e2c14ef4c84ef44e22af3248"
MAX_SOURCE_LENGTH = 512
SPLITS = ("train", "dev")
DERIVED_DIR = ROOT / "runtime" / "datasets" / "derived" / "cnewsum_train_lt512_manifest"
RUNS_DIR = ROOT / "runtime" / "training_runs"
FORMAL_RUN = RUNS_DIR / "b2-07-20260905T091244Z-r0-full-train" / "run.json"
HF_CACHE_DIR = ROOT / "runtime" / "hf_cache"
FORMAL_MODEL_DIR = ROOT / "runtime" / "models" / "news_summarizer"


def utc_now() -> str:
    """返回 UTC 时间，供非正式分析运行记录使用。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_token_count(token_count: int) -> str:
    """严格按正式短文本域边界分类。"""
    if token_count < MAX_SOURCE_LENGTH:
        return "lt512"
    if token_count == MAX_SOURCE_LENGTH:
        return "eq512"
    return "gt512"


def percentile(values: list[int], ratio: float) -> float:
    """使用线性插值计算可复核分位数。"""
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * ratio
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def distribution(values: list[int], *, include_min: bool = True) -> dict[str, float | int | None]:
    """汇总长度分布；空集合用空值而非虚构统计量。"""
    if not values:
        keys = ("min", "mean", "median", "p50", "p75", "p90", "p95", "p99", "max") if include_min else ("mean", "median", "p90", "p95", "p99", "max")
        return {key: None for key in keys}
    result: dict[str, float | int | None] = {
        "mean": statistics.fmean(values), "median": statistics.median(values),
        "p90": percentile(values, .90), "p95": percentile(values, .95),
        "p99": percentile(values, .99), "max": max(values),
    }
    if include_min:
        result.update({"min": min(values), "p50": percentile(values, .50), "p75": percentile(values, .75)})
    return result


def estimate_training_seconds(train_lt512_count: int, original_count: int, old_duration_seconds: float, samples_per_second: float | None = None) -> dict[str, float | None]:
    """返回样本线性基线与可选吞吐估算，均不是实际训练结果。"""
    linear = old_duration_seconds * train_lt512_count / original_count
    throughput = train_lt512_count / samples_per_second if samples_per_second and samples_per_second > 0 else None
    return {"sample_count_linear_seconds": linear, "throughput_raw_seconds": throughput,
            "throughput_conservative_seconds": throughput * 1.15 if throughput is not None else None}


def environment() -> dict[str, Any]:
    """收集本次实际环境，不推断未检测到的信息。"""
    gpu = torch.cuda.get_device_properties(0) if torch.cuda.is_available() else None
    driver_version = None
    try:
        completed = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"], capture_output=True, text=True, check=False)
        if completed.returncode == 0:
            driver_version = completed.stdout.strip().splitlines()[0]
    except OSError:
        pass
    return {"python_version": platform.python_version(), "torch_version": torch.__version__,
            "transformers_version": transformers.__version__, "cuda_runtime": torch.version.cuda,
            "gpu_name": gpu.name if gpu else None, "gpu_total_vram_bytes": gpu.total_memory if gpu else None,
            "gpu_driver_version": driver_version,
            "tokenizer_repository": TOKENIZER_REPOSITORY, "tokenizer_revision": TOKENIZER_REVISION}


def source_fingerprint(path: Path) -> dict[str, Any]:
    """按字节读取文件指纹，记录分析输入。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def load_frozen_tokenizer() -> Any:
    """核验 B2-09 导出的 tokenizer 身份后以本地只读方式加载。"""
    metadata = json.loads((FORMAL_MODEL_DIR / "model_metadata.json").read_text(encoding="utf-8"))
    tokenizer_info = metadata.get("tokenizer", {})
    if tokenizer_info.get("name_or_path") != TOKENIZER_REPOSITORY or tokenizer_info.get("revision") != TOKENIZER_REVISION:
        raise ValueError("正式导出 tokenizer 与 B2-05/B2-06 冻结来源或 revision 不一致")
    return AutoTokenizer.from_pretrained(FORMAL_MODEL_DIR, trust_remote_code=False, local_files_only=True)


def formal_model_fingerprints() -> dict[str, str]:
    """返回正式导出目录的文件指纹，用于只读运行前后核验。"""
    return {path.name: source_fingerprint(path)["sha256"] for path in sorted(FORMAL_MODEL_DIR.iterdir()) if path.is_file()}


def analyze_split(split: str, tokenizer: Any, manifest_path: Path) -> dict[str, Any]:
    """流式统计一个 processed split，并只写入短文本 ID/token 清单。"""
    source = PROCESSED_DIR / f"{split}.jsonl"
    article_tokens: list[int] = []
    article_chars: list[int] = []
    summary_tokens: list[int] = []
    lt_article_tokens: list[int] = []
    lt_summary_tokens: list[int] = []
    counts = {"lt512": 0, "eq512": 0, "gt512": 0}
    digest = hashlib.sha256()
    with manifest_path.open("w", encoding="utf-8", newline="\n") as manifest:
        for source_index, (_, row, error) in enumerate(stream_jsonl(source)):
            if error or row is None:
                raise ValueError(f"{source}:{source_index + 1}: {error}")
            article, summary = row.get("article"), row.get("summary")
            if not isinstance(article, str) or not isinstance(summary, str):
                raise ValueError(f"{source}:{source_index + 1}: processed 字段不是字符串")
            article_count = len(tokenizer(article, add_special_tokens=True, truncation=False)["input_ids"])
            summary_count = len(tokenizer(summary, add_special_tokens=True, truncation=False)["input_ids"])
            category = classify_token_count(article_count)
            counts[category] += 1
            article_tokens.append(article_count); article_chars.append(len(article)); summary_tokens.append(summary_count)
            if category == "lt512":
                lt_article_tokens.append(article_count); lt_summary_tokens.append(summary_count)
                item = {"source_index": source_index, "id": row.get("id"), "token_count": article_count}
                line = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
                manifest.write(line + "\n"); digest.update((line + "\n").encode("utf-8"))
    total = sum(counts.values())
    return {"source": source_fingerprint(source), "sample_count": total, **{f"{key}_count": value for key, value in counts.items()},
            **{f"{key}_ratio": value / total for key, value in counts.items()},
            "token_length": distribution(article_tokens), "article_char_length": distribution(article_chars),
            "summary_token_length": distribution(summary_tokens), "lt512_token_length": {"count": counts["lt512"], **distribution(lt_article_tokens, include_min=False)},
            "summary_token_length_in_lt512": {"count": counts["lt512"], **distribution(lt_summary_tokens, include_min=False)},
            "lt512_manifest": {"path": str(manifest_path.relative_to(ROOT)), "sha256": digest.hexdigest(), "line_count": counts["lt512"]}}


def main() -> None:
    """执行 train/dev 分析；只允许读取两份 processed 数据。"""
    run_id = "b2-analysis-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-lt512-stats"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest_dir = DERIVED_DIR / run_id
    manifest_dir.mkdir(parents=True, exist_ok=False)
    tokenizer = load_frozen_tokenizer()
    manifests = {split: manifest_dir / f"{split}_lt512_ids.jsonl" for split in SPLITS}
    formal = json.loads(FORMAL_RUN.read_text(encoding="utf-8"))
    result = {"run_id": run_id, "task": "B2-ANALYSIS-LT512", "experiment_type": "length_statistics", "formal_result": False,
              "timestamp_start": utc_now(), "dataset": "CNewSum", "dataset_split": ["train", "dev"], "test_model_evaluation": False,
              "corpus_rougeL": None, "quality_pass_rate": None, "p95_generation_time_ms": None, "latency_pass_rate": None,
              "token_count_definition": "len(tokenizer(article, add_special_tokens=True, truncation=False)[input_ids])",
              "short_text_definition": "token_count < 512", "tokenizer_load_source": str(FORMAL_MODEL_DIR.relative_to(ROOT)),
              "environment": environment(), "status": "running"}
    (run_dir / "run.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        splits = {split: analyze_split(split, tokenizer, manifests[split]) for split in SPLITS}
        train = splits["train"]
        original_count = int(formal["sample_count"])
        if train["sample_count"] != original_count:
            raise ValueError(f"train 样本数与 B2-07 记录不一致：{train['sample_count']} != {original_count}")
        estimates = estimate_training_seconds(int(train["lt512_count"]), original_count, float(formal["duration_seconds"]))
        result.update({"status": "completed", "timestamp_end": utc_now(), "splits": splits,
                       "future_train_lt512": {"original_train_count": original_count, "train_lt512_count": train["lt512_count"],
                                             "retained_ratio": train["lt512_ratio"], "reduced_ratio": 1 - train["lt512_ratio"]},
                       "previous_formal_training": {"run_id": formal["run_id"], "duration_seconds": formal["duration_seconds"]},
                       "training_time_estimates": estimates})
        (run_dir / "lt512_statistics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        result.update({"status": "failed", "timestamp_end": utc_now(), "error_type": type(exc).__name__, "error_message": str(exc)})
        raise
    finally:
        (run_dir / "run.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run_dir)


if __name__ == "__main__":
    main()
