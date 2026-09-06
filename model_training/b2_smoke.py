"""候选模型的 CUDA smoke 验证。"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from model_training.b2_data import PROCESSED_DIR, RUNS_DIR, utc_now


MODEL = "Langboat/mengzi-t5-base"


def main() -> None:
    run_id = "b2-04-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-mengzi-smoke"
    run_dir = RUNS_DIR / run_id; run_dir.mkdir(parents=True)
    record = {"run_id": run_id, "parent_run_id": None, "timestamp_start": utc_now(), "task": "B2-04", "experiment_type": "smoke", "formal_result": False, "candidate_model": MODEL, "dataset": "CNewSum", "dataset_split": ["train"], "sample_count": 1, "test_model_evaluation": False, "corpus_rougeL": None, "quality_pass_rate": None, "avg_generation_time_ms": None, "p95_generation_time_ms": None, "latency_pass_rate": None, "status": "failed"}
    try:
        if not torch.cuda.is_available(): raise RuntimeError("cuda_environment")
        tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=False)
        model = AutoModelForSeq2SeqLM.from_pretrained(MODEL, trust_remote_code=False).cuda().train()
        sample = json.loads((PROCESSED_DIR / "train.jsonl").open(encoding="utf-8").readline())
        batch = tokenizer(sample["article"], max_length=128, truncation=True, return_tensors="pt").to("cuda")
        labels = tokenizer(sample["summary"], max_length=64, truncation=True, return_tensors="pt").input_ids.to("cuda")
        output = model(**batch, labels=labels); output.loss.backward(); torch.cuda.synchronize()
        loss = float(output.loss.detach().cpu()); model.eval()
        with torch.inference_mode(): generated = model.generate(**batch, max_new_tokens=16)
        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
        model.save_pretrained(run_dir / "smoke_model", safe_serialization=True); tokenizer.save_pretrained(run_dir / "smoke_model")
        reloaded = AutoModelForSeq2SeqLM.from_pretrained(run_dir / "smoke_model", local_files_only=True).cuda().eval()
        with torch.inference_mode(): reloaded_output = reloaded.generate(**batch, max_new_tokens=16)
        reloaded_text = tokenizer.batch_decode(reloaded_output, skip_special_tokens=True)[0]
        record.update({"status": "completed", "train_loss": loss, "generated_nonempty": bool(decoded.strip()), "reloaded_generated_nonempty": bool(reloaded_text.strip()), "save_load_verified": True, "peak_gpu_memory": torch.cuda.max_memory_allocated(), "artifacts": ["smoke_model"], "notes": "CUDA forward/backward/save/local reload/generate 已执行；生成内容仅作 smoke 诊断，不作质量评价。"})
    except Exception as exc:
        record.update({"error_type": type(exc).__name__, "error_message": str(exc)})
        raise
    finally:
        record["timestamp_end"] = utc_now()
        (run_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run_dir)


if __name__ == "__main__":
    main()
