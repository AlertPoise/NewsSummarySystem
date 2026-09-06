"""B2-10/B2-11/B2-14 共用的正式评价基础设施。"""

from __future__ import annotations

import json
import math
import platform
import hashlib
import statistics
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from model_training.b2_data import RAW_DIR, ROOT, RUNS_DIR, stream_jsonl, utc_now

MODEL_DIR = ROOT / "runtime" / "models" / "news_summarizer"
TEST_FILE = RAW_DIR / "test.simple.label.jsonl"
QUALITY_THRESHOLD = 0.40
LATENCY_THRESHOLD_MS = 1500.0


def json_dump(path: Path, value: dict[str, Any]) -> None:
    """以 UTF-8 写入可审计 JSON。"""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def article_text(record: dict[str, Any]) -> str:
    """从 CNewSum 原始记录恢复冻结的 article 文本表示。"""
    article = record.get("article")
    if not isinstance(article, list) or not all(isinstance(item, str) for item in article):
        raise ValueError("CNewSum test article 必须是字符串数组")
    return " ".join(article)


def iter_raw_test_rows() -> Iterator[dict[str, Any]]:
    """流式读取唯一正式 CNewSum test 文件，不读取 annotation/historical test。"""
    if TEST_FILE.name != "test.simple.label.jsonl" or not TEST_FILE.is_file():
        raise FileNotFoundError(f"正式 CNewSum test 不存在：{TEST_FILE}")
    for line_number, record, error in stream_jsonl(TEST_FILE):
        if error or record is None:
            raise ValueError(f"{TEST_FILE}:{line_number}: {error}")
        if not isinstance(record.get("summary"), str) or not record["summary"].strip():
            raise ValueError(f"{TEST_FILE}:{line_number}: summary 为空或不是字符串")
        text = article_text(record)
        if not text.strip():
            raise ValueError(f"{TEST_FILE}:{line_number}: article 为空")
        yield {"id": record.get("id"), "article": text, "reference": record["summary"]}


def token_count(tokenizer: Any, article: str) -> int:
    """唯一 eligibility 口径：正式 tokenizer、特殊标记、禁止截断。"""
    encoded = tokenizer(article, add_special_tokens=True, truncation=False)
    return len(encoded["input_ids"])


def eligibility_counts(rows: Iterable[dict[str, Any]], tokenizer: Any, max_input_tokens: int) -> dict[str, int | float]:
    """统计原始 test 中正式支持范围与范围外样本。"""
    full = eligible = 0
    for row in rows:
        full += 1
        if token_count(tokenizer, row["article"]) <= max_input_tokens:
            eligible += 1
    return {
        "full_test_count": full,
        "eligible_count": eligible,
        "excluded_count": full - eligible,
        "eligible_ratio": eligible / full if full else 0.0,
    }


def iter_eligible_rows(tokenizer: Any, max_input_tokens: int, *, limit: int | None = None) -> Iterator[dict[str, Any]]:
    """重新流式构造 eligible test 子集；范围外样本绝不调用 Pipeline。"""
    emitted = 0
    for row in iter_raw_test_rows():
        count = token_count(tokenizer, row["article"])
        if count > max_input_tokens:
            continue
        if limit is not None and emitted >= limit:
            return
        emitted += 1
        yield {**row, "article_token_count": count}


def stable_sample_identity(row: dict[str, Any]) -> str:
    """返回与 JSONL 顺序无关的稳定样本身份；缺 id 时退回内容指纹。"""
    item_id = row.get("id")
    if item_id is not None:
        return json.dumps(item_id, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload = json.dumps({"article": row["article"], "reference": row["reference"]}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "content:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def deterministic_sample(rows: Iterable[dict[str, Any]], sample_size: int, seed: str) -> list[dict[str, Any]]:
    """用 SHA-256(seed:id) 排序抽样，绝不依赖 Python hash 或输入顺序。"""
    if sample_size <= 0:
        raise ValueError("sample_size 必须为正数")
    ranked: list[tuple[str, str, str, dict[str, Any]]] = []
    for row in rows:
        identity = stable_sample_identity(row)
        content_fingerprint = hashlib.sha256((row["article"] + "\n" + row["reference"]).encode("utf-8")).hexdigest()
        selection_hash = hashlib.sha256(f"{seed}:{identity}".encode("utf-8")).hexdigest()
        ranked.append((selection_hash, identity, content_fingerprint, row))
    ranked.sort(key=lambda item: item[:3])
    return [item[3] for item in ranked[:sample_size]]


def sample_manifest(rows: list[dict[str, Any]], *, sample_size_requested: int, seed: str, counts: dict[str, int | float], profile: str = "course_sampled") -> dict[str, Any]:
    """生成可复现 sampled 运行的旁路清单。"""
    return {"profile": profile, "seed": seed, "selection_method": "SHA256(seed + ':' + stable_sample_id) ascending", "sample_size_requested": sample_size_requested, "sample_size_actual": len(rows), "full_test_count": counts["full_test_count"], "eligible_count": counts["eligible_count"], "excluded_count": counts["excluded_count"], "selected_ids": [row["id"] for row in rows]}


def aggregate_rouge(metrics: Iterable[dict[str, float]]) -> dict[str, float | int | None]:
    """按冻结 evaluator 的逐样本 F 值作算术宏平均，得到 corpus 指标。"""
    values = list(metrics)
    if not values:
        return {"rouge1": None, "rouge2": None, "rougeL": None, "corpus_rougeL": None, "evaluated_count": 0}
    return {
        "rouge1": statistics.fmean(item["rouge1"] for item in values),
        "rouge2": statistics.fmean(item["rouge2"] for item in values),
        "rougeL": statistics.fmean(item["rougeL"] for item in values),
        "corpus_rougeL": statistics.fmean(item["rougeL"] for item in values),
        "evaluated_count": len(values),
    }


def quality_summary(metrics: Iterable[dict[str, float]], threshold: float = QUALITY_THRESHOLD) -> dict[str, int | float | None]:
    """计算单样本 ROUGE-L 硬门槛通过数量与比例。"""
    values = list(metrics)
    passed = sum(item["rougeL"] >= threshold for item in values)
    return {"quality_pass_count": passed, "quality_pass_rate": passed / len(values) if values else None}


def percentile(values: list[float], ratio: float) -> float | None:
    """线性插值分位数；P95 规则可由原始 latency 复算。"""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * ratio
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def latency_summary(latencies: list[float], threshold_ms: float = LATENCY_THRESHOLD_MS) -> dict[str, int | float | None]:
    """汇总完整 Pipeline 单篇延迟；阈值严格为小于 1500ms。"""
    if not latencies:
        return {
            "sample_count": 0, "avg_generation_time_ms": None, "median_generation_time_ms": None,
            "p95_generation_time_ms": None, "min_generation_time_ms": None, "max_generation_time_ms": None,
            "latency_pass_count": 0, "latency_pass_rate": None,
        }
    passed = sum(value < threshold_ms for value in latencies)
    return {
        "sample_count": len(latencies), "avg_generation_time_ms": statistics.fmean(latencies),
        "median_generation_time_ms": statistics.median(latencies), "p95_generation_time_ms": percentile(latencies, 0.95),
        "min_generation_time_ms": min(latencies), "max_generation_time_ms": max(latencies),
        "latency_pass_count": passed, "latency_pass_rate": passed / len(latencies),
    }


def latency_target_met(metrics: dict[str, Any], threshold_ms: float = LATENCY_THRESHOLD_MS) -> bool:
    """只按课程规定的 latency 指标判断是否还需要 C2-14 性能优化。"""
    rate, p95 = metrics.get("latency_pass_rate"), metrics.get("p95_generation_time_ms")
    return rate is not None and p95 is not None and rate >= 0.95 and p95 < threshold_ms


def make_run_dir(prefix: str, suffix: str) -> tuple[str, Path]:
    """创建唯一且可追溯的运行目录。"""
    timestamp = utc_now().replace("-", "").replace(":", "").replace("+00:00", "").replace("Z", "Z")
    run_id = f"{prefix}-{timestamp}-{suffix}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def hardware_environment() -> dict[str, Any]:
    """记录实际可见的 Python、Torch 与 GPU 环境，不推测不可见字段。"""
    import torch

    properties = torch.cuda.get_device_properties(0) if torch.cuda.is_available() else None
    return {
        "platform": platform.platform(), "python_version": platform.python_version(),
        "torch_version": torch.__version__, "cuda_available": torch.cuda.is_available(),
        "torch_cuda_version": torch.version.cuda, "gpu_name": properties.name if properties else None,
        "gpu_total_vram_bytes": properties.total_memory if properties else None,
    }


def pipeline_imports() -> tuple[type[Any], type[BaseException]]:
    """在离线工具中导入 C 的唯一正式 Pipeline，不复制实现。"""
    import sys

    backend_dir = str(ROOT / "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from app.ai.pipeline import InputTooLongError, SummaryPipeline

    return SummaryPipeline, InputTooLongError
