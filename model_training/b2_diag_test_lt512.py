"""对 CNewSum test 中不发生 512 token 截断的子集进行只读诊断评价。"""

from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from model_training.b2_data import RAW_DIR, ROOT, RUNS_DIR, SPLIT_FILES, sha256_file, stream_jsonl, utc_now
from model_training.b2_rouge import EVALUATOR_VERSION, score


MODEL_DIR = ROOT / "runtime" / "models" / "news_summarizer"
DERIVED_DIR = ROOT / "runtime" / "datasets" / "derived" / "cnewsum_test_lt512"
SOURCE_TEST = RAW_DIR / SPLIT_FILES["test"]
BASE_RUN = "b2-07-20260905T091244Z-r0-full-train"
MAX_INPUT_TOKENS = 512
BATCH_SIZE = 8
GENERATION_PARAMETERS = {"num_beams": 2, "max_new_tokens": 80, "length_penalty": 1.0, "early_stopping": True}


def model_fingerprints() -> dict[str, dict[str, Any]]:
    """返回正式模型目录的文件指纹，不修改模型。"""
    return {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(MODEL_DIR.iterdir()) if path.is_file()
    }


def stable_record_key(item: dict[str, Any]) -> str:
    """为原始记录建立可复核的稳定内容标识。"""
    text = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def article_text(item: dict[str, Any]) -> str:
    """严格复用 B2-02 的正文连接规则。"""
    article = item.get("article")
    if not isinstance(article, list) or not all(isinstance(sentence, str) for sentence in article):
        raise ValueError("原始 test article 不是 list[str]")
    return " ".join(article)


def find_existing_full_test_runs() -> list[dict[str, Any]]:
    """仅索引已有运行记录，绝不触发全量 test 推理。"""
    result: list[dict[str, Any]] = []
    for path in RUNS_DIR.glob("*/run.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        split = record.get("dataset_split", [])
        if split == ["test"]:
            result.append({"run_id": record.get("run_id"), "task": record.get("task"), "status": record.get("status"), "path": str(path.parent.relative_to(ROOT))})
    return result


def snapshot_source() -> dict[str, Any]:
    """收集正式 test 的只读身份快照。"""
    schema: dict[str, set[str]] = {}
    count = 0
    for line_no, item, error in stream_jsonl(SOURCE_TEST):
        if error or item is None:
            raise ValueError(f"source test {line_no}: {error}")
        count += 1
        for key, value in item.items():
            schema.setdefault(key, set()).add(type(value).__name__)
    existing = find_existing_full_test_runs()
    return {
        "mapping_source": "model_training.b2_data.SPLIT_FILES['test']",
        "source_test_path_absolute": str(SOURCE_TEST.resolve()),
        "source_test_path_repository_relative": str(SOURCE_TEST.relative_to(ROOT)),
        "source_test_filename": SOURCE_TEST.name,
        "source_test_bytes": SOURCE_TEST.stat().st_size,
        "source_test_sha256": sha256_file(SOURCE_TEST),
        "source_test_sample_count": count,
        "source_test_schema": {key: sorted(types) for key, types in schema.items()},
        "existing_full_test_evaluation": bool(existing),
        "existing_full_test_runs": existing,
    }


def build_subset(tokenizer: Any, snapshot: dict[str, Any]) -> dict[str, Any]:
    """按正式 tokenizer 的含 special tokens 长度构建严格小于 512 的原始记录子集。"""
    if DERIVED_DIR.exists():
        raise FileExistsError(f"拒绝覆盖已有派生数据目录：{DERIVED_DIR}")
    DERIVED_DIR.mkdir(parents=True)
    subset_path = DERIVED_DIR / "test_lt512.jsonl"
    index_path = DERIVED_DIR / "index.jsonl"
    total = lt512 = eq512 = gt512 = 0
    subset_keys: list[str] = []
    with subset_path.open("w", encoding="utf-8", newline="\n") as subset, index_path.open("w", encoding="utf-8", newline="\n") as index:
        for original_index, (_, item, error) in enumerate(stream_jsonl(SOURCE_TEST)):
            if error or item is None:
                raise ValueError(f"source test {original_index}: {error}")
            token_count = len(tokenizer(article_text(item), add_special_tokens=True, truncation=False)["input_ids"])
            included = token_count < MAX_INPUT_TOKENS
            total += 1
            lt512 += int(included)
            eq512 += int(token_count == MAX_INPUT_TOKENS)
            gt512 += int(token_count > MAX_INPUT_TOKENS)
            record_key = stable_record_key(item)
            index.write(json.dumps({
                "original_index": original_index,
                "id": item.get("id"),
                "record_key": record_key,
                "token_count": token_count,
                "included": included,
                "source_test_sha256": snapshot["source_test_sha256"],
            }, ensure_ascii=False, separators=(",", ":")) + "\n")
            if included:
                subset.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
                subset_keys.append(record_key)
    manifest = {
        "created_at": utc_now(), "source_test_sha256": snapshot["source_test_sha256"],
        "source_test_path": snapshot["source_test_path_repository_relative"],
        "tokenizer_path": str(MODEL_DIR.relative_to(ROOT)), "tokenizer_local_files_only": True,
        "token_count_semantics": "tokenizer(article_joined_by_single_ascii_space, add_special_tokens=True, truncation=False)",
        "subset_rule": "token_count < 512", "max_input_tokens": MAX_INPUT_TOKENS,
        "total_test_count": total, "lt512_count": lt512, "eq512_count": eq512, "gt512_count": gt512,
        "lt512_ratio": lt512 / total, "eq512_ratio": eq512 / total, "gt512_ratio": gt512 / total,
        "subset_file": subset_path.name, "index_file": index_path.name,
    }
    (DERIVED_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def verify_subset(tokenizer: Any, snapshot: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    """验证子集、索引和源文件均可追溯且没有阈值越界。"""
    source_keys = set()
    for line_no, item, error in stream_jsonl(SOURCE_TEST):
        if error or item is None:
            raise ValueError(f"source verification {line_no}: {error}")
        source_keys.add(stable_record_key(item))
    subset_count = 0
    subset_keys = set()
    for line_no, item, error in stream_jsonl(DERIVED_DIR / "test_lt512.jsonl"):
        if error or item is None:
            raise ValueError(f"subset verification {line_no}: {error}")
        token_count = len(tokenizer(article_text(item), add_special_tokens=True, truncation=False)["input_ids"])
        if token_count >= MAX_INPUT_TOKENS:
            raise ValueError(f"subset threshold violation at line {line_no}: {token_count}")
        key = stable_record_key(item)
        if key in subset_keys:
            raise ValueError(f"subset duplicate record at line {line_no}")
        if key not in source_keys:
            raise ValueError(f"subset record cannot map to source at line {line_no}")
        subset_keys.add(key); subset_count += 1
    index_count = sum(1 for _, item, error in stream_jsonl(DERIVED_DIR / "index.jsonl") if not error and item is not None)
    after_sha = sha256_file(SOURCE_TEST)
    if after_sha != snapshot["source_test_sha256"]:
        raise RuntimeError("原始 test SHA-256 在派生子集后发生变化")
    if subset_count != manifest["lt512_count"] or index_count != manifest["total_test_count"]:
        raise ValueError("派生数据计数与 manifest 不一致")
    return {"subset_verified_count": subset_count, "index_verified_count": index_count, "source_test_sha256_after_subset": after_sha}


def main() -> None:
    if not MODEL_DIR.is_dir():
        raise FileNotFoundError(f"正式模型目录不存在：{MODEL_DIR}")
    run_id = "b2-diag-test-lt512-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    snapshot = snapshot_source()
    model_before = model_fingerprints()
    (run_dir / "full_test_snapshot.json").write_text(json.dumps({**snapshot, "model_files_before": model_before}, ensure_ascii=False, indent=2), encoding="utf-8")
    record: dict[str, Any] = {
        "run_id": run_id, "parent_run_id": BASE_RUN, "timestamp_start": utc_now(),
        "task": "B2-DIAG-TEST-LT512", "experiment_type": "diagnostic_subset_evaluation", "formal_result": False,
        "dataset": "CNewSum", "dataset_split": "test_lt512", "source_test_path": snapshot["source_test_path_repository_relative"],
        "source_test_sha256": snapshot["source_test_sha256"], "subset_rule": "token_count < 512",
        "tokenizer_path": str(MODEL_DIR.relative_to(ROOT)), "max_input_tokens": MAX_INPUT_TOKENS,
        "generation_parameters": GENERATION_PARAMETERS, "evaluator": EVALUATOR_VERSION,
        "existing_full_test_evaluation": snapshot["existing_full_test_evaluation"], "status": "running",
        "notes": "该结果仅为 CNewSum test 中 token_count<512 的诊断子集结果，不等价于完整 CNewSum test 正式验收结果，不得用于宣称 full-test/Pipeline 硬门槛通过。",
    }
    (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        if not torch.cuda.is_available():
            raise RuntimeError("cuda_environment")
        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
        manifest = build_subset(tokenizer, snapshot)
        verification = verify_subset(tokenizer, snapshot, manifest)
        record.update({
            "full_test_sample_count": manifest["total_test_count"], "subset_sample_count": manifest["lt512_count"],
            "sample_count": manifest["lt512_count"], "subset_ratio": manifest["lt512_ratio"],
            "eq512_count": manifest["eq512_count"], "gt512_count": manifest["gt512_count"],
            "subset_manifest": str((DERIVED_DIR / "manifest.json").relative_to(ROOT)), **verification,
        })
        model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_DIR, local_files_only=True).cuda().eval()
        scores: list[dict[str, float]] = []; lengths: list[int] = []; empty = failed = 0; total_records = 0
        index_by_key: dict[str, tuple[int, int]] = {}
        for line_no, index_item, error in stream_jsonl(DERIVED_DIR / "index.jsonl"):
            if error or index_item is None:
                raise ValueError(f"derived index {line_no}: {error}")
            if index_item.get("included"):
                key = index_item["record_key"]
                if key in index_by_key:
                    raise ValueError(f"derived index duplicate record key at line {line_no}")
                index_by_key[key] = (index_item["original_index"], index_item["token_count"])
        def write_result(rows: list[tuple[int, dict[str, Any], int]], predictions: list[str] | None, error: Exception | None, metrics: Any, predictions_out: Any) -> None:
            nonlocal empty, failed, total_records
            if error is not None:
                for index, item, token_count in rows:
                    total_records += 1; failed += 1
                    base = {"original_index": index, "id": item.get("id"), "token_count": token_count, "error_type": type(error).__name__, "error_message": str(error)}
                    metrics.write(json.dumps(base, ensure_ascii=False) + "\n")
                    predictions_out.write(json.dumps({**base, "reference_summary": item.get("summary"), "generated_summary": None}, ensure_ascii=False) + "\n")
                return
            assert predictions is not None
            for (index, item, token_count), prediction in zip(rows, predictions):
                total_records += 1
                metric = score(prediction, item["summary"]); scores.append(metric); lengths.append(len(prediction)); empty += int(not prediction.strip())
                base = {"original_index": index, "id": item.get("id"), "token_count": token_count}
                metrics.write(json.dumps({**base, **metric, "quality_pass": metric["rougeL"] >= .40, "prediction_char_length": len(prediction)}, ensure_ascii=False) + "\n")
                predictions_out.write(json.dumps({**base, "reference_summary": item["summary"], "generated_summary": prediction, "generation_parameters": GENERATION_PARAMETERS}, ensure_ascii=False) + "\n")
        with (run_dir / "metrics.jsonl").open("w", encoding="utf-8") as metrics, (run_dir / "predictions.jsonl").open("w", encoding="utf-8") as predictions_out, torch.inference_mode():
            pending: list[tuple[int, dict[str, Any], int]] = []
            for subset_index, (_, item, error) in enumerate(stream_jsonl(DERIVED_DIR / "test_lt512.jsonl")):
                if error or item is None:
                    raise ValueError(f"derived subset {subset_index}: {error}")
                token_count = len(tokenizer(article_text(item), add_special_tokens=True, truncation=False)["input_ids"])
                mapped = index_by_key.get(stable_record_key(item))
                if mapped is None:
                    raise ValueError(f"derived subset record lacks index mapping at line {subset_index}")
                original_index, indexed_token_count = mapped
                if token_count != indexed_token_count:
                    raise ValueError(f"derived subset token count differs from index at line {subset_index}")
                pending.append((original_index, item, token_count))
                if len(pending) < BATCH_SIZE:
                    continue
                try:
                    inputs = tokenizer([article_text(row[1]) for row in pending], max_length=MAX_INPUT_TOKENS, truncation=True, padding=True, return_tensors="pt").to("cuda")
                    generated = model.generate(**inputs, **GENERATION_PARAMETERS)
                    write_result(pending, tokenizer.batch_decode(generated, skip_special_tokens=True), None, metrics, predictions_out)
                except Exception as exc:
                    for row in pending:
                        try:
                            inputs = tokenizer(article_text(row[1]), max_length=MAX_INPUT_TOKENS, truncation=True, return_tensors="pt").to("cuda")
                            generated = model.generate(**inputs, **GENERATION_PARAMETERS)
                            write_result([row], tokenizer.batch_decode(generated, skip_special_tokens=True), None, metrics, predictions_out)
                        except Exception as row_exc:
                            write_result([row], None, row_exc, metrics, predictions_out)
                metrics.flush(); predictions_out.flush(); pending = []
            if pending:
                try:
                    inputs = tokenizer([article_text(row[1]) for row in pending], max_length=MAX_INPUT_TOKENS, truncation=True, padding=True, return_tensors="pt").to("cuda")
                    generated = model.generate(**inputs, **GENERATION_PARAMETERS)
                    write_result(pending, tokenizer.batch_decode(generated, skip_special_tokens=True), None, metrics, predictions_out)
                except Exception as exc:
                    for row in pending:
                        try:
                            inputs = tokenizer(article_text(row[1]), max_length=MAX_INPUT_TOKENS, truncation=True, return_tensors="pt").to("cuda")
                            generated = model.generate(**inputs, **GENERATION_PARAMETERS)
                            write_result([row], tokenizer.batch_decode(generated, skip_special_tokens=True), None, metrics, predictions_out)
                        except Exception as row_exc:
                            write_result([row], None, row_exc, metrics, predictions_out)
                metrics.flush(); predictions_out.flush()
        metrics_rows = [json.loads(line) for line in (run_dir / "metrics.jsonl").read_text(encoding="utf-8").splitlines()]
        predictions_count = sum(1 for line in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines() if line)
        successes = [item for item in metrics_rows if "rougeL" in item]
        if len(metrics_rows) != manifest["lt512_count"] or predictions_count != manifest["lt512_count"] or total_records != manifest["lt512_count"]:
            raise RuntimeError("评价产物行数与子集样本数不一致")
        if len(successes) + failed != manifest["lt512_count"]:
            raise RuntimeError("成功与失败样本数不能覆盖子集")
        if any(item["token_count"] >= MAX_INPUT_TOKENS for item in metrics_rows):
            raise RuntimeError("评价记录出现 token_count >= 512")
        recomputed = {
            "rouge1": statistics.fmean(item["rouge1"] for item in successes) if successes else None,
            "rouge2": statistics.fmean(item["rouge2"] for item in successes) if successes else None,
            "rougeL": statistics.fmean(item["rougeL"] for item in successes) if successes else None,
            "quality_pass_count": sum(item["rougeL"] >= .40 for item in successes),
        }
        model_after = model_fingerprints()
        source_after = sha256_file(SOURCE_TEST)
        if model_after != model_before:
            raise RuntimeError("正式模型文件指纹在诊断期间发生变化")
        if source_after != snapshot["source_test_sha256"]:
            raise RuntimeError("原始 test SHA-256 在评价后发生变化")
        record.update({
            "status": "completed", "timestamp_end": utc_now(), "successful_count": len(successes), "failed_count": failed,
            "rouge1": recomputed["rouge1"], "rouge2": recomputed["rouge2"], "rougeL": recomputed["rougeL"],
            "quality_pass_threshold": .40, "quality_pass_count": recomputed["quality_pass_count"],
            "quality_pass_rate": recomputed["quality_pass_count"] / len(successes) if successes else None,
            "empty_generation_count": empty, "generated_length_mean": statistics.fmean(lengths) if lengths else None,
            "generated_length_median": statistics.median(lengths) if lengths else None,
            "metrics_line_count": len(metrics_rows), "predictions_line_count": predictions_count,
            "source_test_sha256_after_evaluation": source_after, "model_files_unchanged": model_after == model_before,
            "local_files_only_load": True, "artifacts": ["full_test_snapshot.json", "metrics.jsonl", "predictions.jsonl"],
        })
    except Exception as exc:
        record.update({"status": "failed", "timestamp_end": utc_now(), "error_type": type(exc).__name__, "error_message": str(exc)})
        raise
    finally:
        (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run_dir)


if __name__ == "__main__":
    main()
