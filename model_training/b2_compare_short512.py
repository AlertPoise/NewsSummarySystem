"""B2-SHORT512：比较同域 validation，并仅在新模型更优时导出候选。"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from model_training.b2_data import ROOT
from model_training.b2_short512_common import RUNS_DIR, model_fingerprint, utc_now, verify_old_model


def main() -> None:
    """依据 ROUGE-L 严格大于关系选择是否导出 short512 候选。"""
    parser = argparse.ArgumentParser(description="short512 同域比较")
    parser.add_argument("--training-run-id", required=True); parser.add_argument("--new-validation-run-id", required=True); parser.add_argument("--old-validation-run-id", required=True)
    args = parser.parse_args(); new = json.loads((RUNS_DIR / args.new_validation_run_id / "summary.json").read_text(encoding="utf-8")); old = json.loads((RUNS_DIR / args.old_validation_run_id / "summary.json").read_text(encoding="utf-8"))
    if new["sample_count"] != 5734 or old["sample_count"] != 5734: raise ValueError("validation 覆盖不完整，禁止比较")
    selection = "short512_candidate_preferred" if new["validation_rougeL"] > old["validation_rougeL"] else "old_model_preferred_on_dev_lt512"
    run_dir = RUNS_DIR / args.training_run_id; checkpoint = run_dir / "checkpoint"; result = {"domain": "token_count < 512", "dev_sample_count": 5734, "old_model": {"source": "runtime/models/news_summarizer", **old}, "new_model": {"source": str(checkpoint.relative_to(ROOT)), **new}, "delta": {key: new[key] - old[key] for key in ("validation_rouge1", "validation_rouge2", "validation_rougeL", "validation_quality_pass_rate")}, "old_model_train_domain": "full CNewSum train with truncation at max_source_length=512", "new_model_train_domain": "CNewSum train_lt512, no source truncation", "selection_status": selection, "timestamp": utc_now()}
    if selection == "short512_candidate_preferred":
        target = ROOT / "runtime" / "models" / "news_summarizer_short512_candidate"
        if target.exists(): raise FileExistsError(f"拒绝覆盖既有 candidate：{target}")
        shutil.copytree(checkpoint, target); AutoTokenizer.from_pretrained(target, local_files_only=True, trust_remote_code=False); AutoModelForSeq2SeqLM.from_pretrained(target, local_files_only=True, trust_remote_code=False)
        result["candidate"] = {"path": str(target.relative_to(ROOT)), "local_files_only_reload": "PASS", **model_fingerprint(target), "source_training_run": args.training_run_id}
    result["old_formal_model_fingerprint"] = verify_old_model()
    (run_dir / "short512_model_comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
