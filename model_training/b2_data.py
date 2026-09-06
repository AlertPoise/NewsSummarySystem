"""CNewSum 阶段2的数据审计、标准化与统计工具。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "runtime" / "datasets" / "CNewSum_v2" / "final"
PROCESSED_DIR = ROOT / "runtime" / "datasets" / "CNewSum_v2" / "processed"
RUNS_DIR = ROOT / "runtime" / "training_runs"
CORE_FIELDS = ("article", "summary", "id", "label")
SPLIT_FILES = {
    "train": "train.simple.label.jsonl",
    "dev": "dev.simple.label.jsonl",
    "test": "test.simple.label.jsonl",
    "test_anno": "test.simple.anno.label.jsonl",
    "test2017": "test2017.simple.label.jsonl",
    "test2018": "test2018.simple.label.jsonl",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stream_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any] | None, str | None]]:
    """逐行读取 JSONL，绝不把大文件整体装入内存。"""
    with path.open("r", encoding="utf-8-sig", newline=None) as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                yield line_number, None, "empty_line"
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                yield line_number, None, f"json_decode:{exc.msg}"
                continue
            if not isinstance(item, dict):
                yield line_number, None, "not_dict"
            else:
                yield line_number, item, None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compact_fingerprint(values: Iterator[str]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(value.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def record_run(run_id: str, task: str, payload: dict[str, Any]) -> Path:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    base = {
        "run_id": run_id, "parent_run_id": None, "timestamp_start": utc_now(),
        "timestamp_end": utc_now(), "task": task, "experiment_type": "data",
        "formal_result": False, "dataset": "CNewSum", "status": "completed",
        "test_model_evaluation": False, "corpus_rougeL": None,
        "quality_pass_rate": None, "avg_generation_time_ms": None,
        "p95_generation_time_ms": None, "latency_pass_rate": None,
    }
    base.update(payload)
    (run_dir / "run.json").write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir


def article_signature(item: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(item.get("article"), ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def inspect_file(path: Path) -> tuple[dict[str, Any], set[str], dict[str, tuple[str, str]]]:
    result: dict[str, Any] = {
        "filename": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path),
        "utf8_read": True, "bom": path.read_bytes()[:3] == b"\xef\xbb\xbf", "line_count": 0,
        "valid_lines": 0, "empty_lines": 0, "parse_errors": [], "non_dict": 0,
        "missing_required": Counter(), "field_types": {}, "field_frequency": Counter(),
        "article_empty": 0, "summary_empty": 0, "article_empty_sentences": 0,
        "duplicate_ids": 0, "duplicate_articles": 0, "duplicate_summaries": 0,
        "length_extremes": {"article_chars_max": 0, "summary_chars_max": 0},
    }
    ids: set[str] = set(); articles: set[str] = set(); summaries: set[str] = set()
    pairs: dict[str, tuple[str, str]] = {}
    type_counts: dict[str, Counter[str]] = {}
    with path.open("rb") as handle:
        newline_bytes = handle.read(1024 * 1024)
    result["newline"] = "CRLF" if b"\r\n" in newline_bytes else "LF"
    for line_no, item, error in stream_jsonl(path):
        result["line_count"] += 1
        if error:
            if error == "empty_line": result["empty_lines"] += 1
            elif error == "not_dict": result["non_dict"] += 1
            else: result["parse_errors"].append({"line": line_no, "error": error})
            continue
        assert item is not None
        result["valid_lines"] += 1
        for key, value in item.items():
            result["field_frequency"][key] += 1
            type_counts.setdefault(key, Counter())[type(value).__name__] += 1
        for key in CORE_FIELDS:
            if key not in item: result["missing_required"][key] += 1
        article = item.get("article"); summary = item.get("summary"); item_id = item.get("id")
        if isinstance(article, list):
            result["article_empty_sentences"] += sum(not isinstance(sentence, str) or not sentence.strip() for sentence in article)
            text = "".join(sentence for sentence in article if isinstance(sentence, str))
            result["article_empty"] += int(not text.strip())
            result["length_extremes"]["article_chars_max"] = max(result["length_extremes"]["article_chars_max"], len(text))
        else:
            result.setdefault("field_type_violations", Counter())["article_not_list"] += 1
            text = ""
        if isinstance(summary, str):
            result["summary_empty"] += int(not summary.strip())
            result["length_extremes"]["summary_chars_max"] = max(result["length_extremes"]["summary_chars_max"], len(summary))
        else:
            result.setdefault("field_type_violations", Counter())["summary_not_str"] += 1
            summary = ""
        id_key = json.dumps(item_id, ensure_ascii=False, sort_keys=True)
        if id_key in ids: result["duplicate_ids"] += 1
        ids.add(id_key)
        signature = hashlib.sha256(text.encode()).hexdigest()
        if signature in articles: result["duplicate_articles"] += 1
        articles.add(signature)
        summary_signature = hashlib.sha256(summary.encode()).hexdigest()
        if summary_signature in summaries: result["duplicate_summaries"] += 1
        summaries.add(summary_signature)
        pairs[id_key] = (article_signature(item), hashlib.sha256(summary.encode()).hexdigest())
    result["field_frequency"] = dict(result["field_frequency"])
    result["missing_required"] = dict(result["missing_required"])
    result["field_types"] = {key: dict(value) for key, value in type_counts.items()}
    for key in ("field_type_violations",):
        if key in result: result[key] = dict(result[key])
    return result, ids, pairs


def inspect() -> None:
    run_id = "b2-01-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-cnewsum-audit"
    run_dir = record_run(run_id, "B2-01", {"source_directory": str(RAW_DIR), "official_sources": [
        "https://dqwang122.github.io/projects/CNewSum/",
        "CNewSum NLPCC 2021: 304,307 core documents; test annotations are adequacy/deducibility.",
    ]})
    files: dict[str, Any] = {}; ids_by_split: dict[str, set[str]] = {}; pairs_by_split: dict[str, dict[str, tuple[str, str]]] = {}
    for split, filename in SPLIT_FILES.items():
        path = RAW_DIR / filename
        if not path.exists(): raise FileNotFoundError(path)
        files[split], ids_by_split[split], pairs_by_split[split] = inspect_file(path)
    core_pairs = (("train", "dev"), ("train", "test"), ("dev", "test"))
    core_overlap = {f"{a}_{b}": len(ids_by_split[a] & ids_by_split[b]) for a, b in core_pairs}
    content_overlap = {
        f"{a}_{b}": len(set(pairs_by_split[a].values()) & set(pairs_by_split[b].values()))
        for a, b in core_pairs
    }
    anno_ids = ids_by_split["test"] & ids_by_split["test_anno"]
    pair_mismatches = sum(pairs_by_split["test"][key] != pairs_by_split["test_anno"][key] for key in anno_ids)
    report = {"schema_version": "cnewsum-audit-v1", "raw_directory": str(RAW_DIR), "files": files,
        "core_id_overlaps": core_overlap,
        "core_article_summary_pair_overlaps": content_overlap,
        "test_anno": {"same_id_count": len(anno_ids), "test_only_ids": len(ids_by_split["test"] - ids_by_split["test_anno"]),
                      "anno_only_ids": len(ids_by_split["test_anno"] - ids_by_split["test"]), "article_or_summary_mismatches": pair_mismatches},
        "historical_test_overlap": {key: len(ids_by_split[key] & ids_by_split["test"]) for key in ("test2017", "test2018")},
        "completed_at": utc_now()}
    (run_dir / "dataset_inspection.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run_dir)


def normalize_record(item: dict[str, Any], source_split: str, source_file: str) -> dict[str, Any]:
    article_sentences = item["article"]
    return {"id": item["id"], "article": " ".join(article_sentences), "article_sentences": article_sentences,
            "summary": item["summary"], "label": item["label"], "source_split": source_split, "source_file": source_file,
            **{key: item[key] for key in ("adequacy", "deducibility") if key in item}}


def prepare() -> None:
    run_id = "b2-02-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-normalize"
    run_dir = record_run(run_id, "B2-02", {"schema_version": "cnewsum-processed-v1", "normalization": "article joins original sentence strings with one ASCII space; article_sentences is retained verbatim"})
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    reports: dict[str, Any] = {}
    for split, filename in SPLIT_FILES.items():
        source = RAW_DIR / filename; destination = PROCESSED_DIR / f"{split}.jsonl"
        if destination.exists():
            raise FileExistsError(f"为避免覆盖既有标准化数据，已停止：{destination}")
        count = 0; digest = hashlib.sha256()
        with destination.open("w", encoding="utf-8", newline="\n") as out:
            for line_no, item, error in stream_jsonl(source):
                if error or item is None: raise ValueError(f"{source}:{line_no}: {error}")
                normalized = normalize_record(item, split, filename)
                text = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
                out.write(text + "\n"); digest.update((text + "\n").encode()); count += 1
        reports[split] = {"input": filename, "output": destination.name, "input_count": count, "output_count": count, "sha256": digest.hexdigest()}
    (run_dir / "conversion_report.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run_dir)


def percentile(values: list[int], ratio: float) -> float:
    if not values: return 0.0
    ordered = sorted(values); position = (len(ordered) - 1) * ratio; lo = math.floor(position); hi = math.ceil(position)
    return ordered[lo] if lo == hi else ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def summarize(values: list[int]) -> dict[str, float]:
    return {"min": min(values), "mean": statistics.fmean(values), "median": statistics.median(values),
            "p90": percentile(values, .90), "p95": percentile(values, .95), "p99": percentile(values, .99), "max": max(values)}


def statistics_report(tokenizer_name: str | None = None) -> None:
    run_id = "b2-03-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-train-dev-stats"
    run_dir = record_run(run_id, "B2-03", {"dataset_split": ["train", "dev"], "test_model_evaluation": False, "tokenizer": tokenizer_name})
    tokenizer = None
    if tokenizer_name:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_name, trust_remote_code=False)
    results: dict[str, Any] = {}
    for split in ("train", "dev"):
        fields = {"article_sentences": [], "article_chars": [], "summary_chars": [], "article_space_tokens": [], "summary_space_tokens": []}
        if tokenizer: fields.update({"article_model_tokens": [], "summary_model_tokens": []})
        for _, item, error in stream_jsonl(PROCESSED_DIR / f"{split}.jsonl"):
            if error or item is None: raise ValueError(f"processed {split}: {error}")
            fields["article_sentences"].append(len(item["article_sentences"]))
            fields["article_chars"].append(len(item["article"]))
            fields["summary_chars"].append(len(item["summary"]))
            fields["article_space_tokens"].append(len(item["article"].split()))
            fields["summary_space_tokens"].append(len(item["summary"].split()))
            if tokenizer:
                fields["article_model_tokens"].append(len(tokenizer(item["article"], add_special_tokens=True, truncation=False)["input_ids"]))
                fields["summary_model_tokens"].append(len(tokenizer(item["summary"], add_special_tokens=True, truncation=False)["input_ids"]))
        results[split] = {"sample_count": len(fields["article_chars"]), **{name: summarize(values) for name, values in fields.items()}}
    (run_dir / "data_statistics.json").write_text(json.dumps({"scope": "train/dev only", "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="CNewSum B2 数据工具")
    parser.add_argument("command", choices=("inspect", "prepare", "stats"))
    parser.add_argument("--tokenizer", help="仅用于 train/dev 的真实 tokenizer 长度统计")
    args = parser.parse_args()
    if args.command == "stats": statistics_report(args.tokenizer)
    else: {"inspect": inspect, "prepare": prepare}[args.command]()


if __name__ == "__main__":
    main()
