"""B2-09：导出唯一正式模型并执行本地加载验证。"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from model_training.b2_data import PROCESSED_DIR, ROOT, RUNS_DIR, stream_jsonl, utc_now

SOURCE_RUN = "b2-07-20260905T091244Z-r0-full-train"
TARGET = ROOT / "runtime" / "models" / "news_summarizer"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()


def main() -> None:
    source = RUNS_DIR / SOURCE_RUN / "checkpoint"
    if not source.is_dir(): raise FileNotFoundError(source)
    if TARGET.exists() and any(TARGET.iterdir()): raise FileExistsError(f"拒绝覆盖来源未知正式目录：{TARGET}")
    run_id = "b2-09-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-export"
    run_dir = RUNS_DIR / run_id; run_dir.mkdir(parents=True)
    record = {"run_id": run_id, "parent_run_id": SOURCE_RUN, "timestamp_start": utc_now(), "task": "B2-09", "experiment_type": "export", "formal_result": True, "dataset": "CNewSum", "dataset_split": ["dev"], "test_model_evaluation": False, "corpus_rougeL": None, "quality_pass_rate": None, "avg_generation_time_ms": None, "p95_generation_time_ms": None, "latency_pass_rate": None, "status": "running"}
    try:
        TARGET.mkdir(parents=True, exist_ok=False); shutil.copytree(source, TARGET, dirs_exist_ok=True)
        tokenizer = AutoTokenizer.from_pretrained(TARGET, local_files_only=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(TARGET, local_files_only=True)
        _, dev_row, error = next(stream_jsonl(PROCESSED_DIR / "dev.jsonl"))
        if error or dev_row is None: raise ValueError(error)
        tokens = tokenizer(dev_row["article"], max_length=512, truncation=True, return_tensors="pt")
        generated = model.generate(**tokens, max_new_tokens=80, num_beams=2, length_penalty=1.0)
        text = tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
        if not text.strip():
            raise RuntimeError("导出后的本地模型在 dev 冒烟样本上生成了空文本")
        files = [{"name": file.name, "bytes": file.stat().st_size, "sha256": sha256(file)} for file in TARGET.iterdir() if file.is_file()]
        record.update({"status": "completed", "timestamp_end": utc_now(), "source_run": SOURCE_RUN, "local_files_only_load": True, "dev_smoke_nonempty": bool(text.strip()), "files": files, "total_bytes": sum(item["bytes"] for item in files), "notes": "未创建 model_metadata.json；该文件属于 B2-12。"})
    except Exception as exc:
        record.update({"status": "failed", "timestamp_end": utc_now(), "error_type": type(exc).__name__, "error_message": str(exc)})
        raise
    finally:
        (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run_dir)


if __name__ == "__main__":
    main()
