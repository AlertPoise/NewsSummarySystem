"""B2-04 候选模型元数据调查。"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from huggingface_hub import HfApi

from model_training.b2_data import RUNS_DIR, utc_now


CANDIDATES = (
    {"repository": "Langboat/mengzi-t5-base", "role": "deep_candidate_1", "reason": "Apache-2.0，中文 T5，Transformers 原生加载。"},
    {"repository": "IDEA-CCNL/Randeng-Pegasus-238M-Summary-Chinese", "role": "survey_only", "reason": "摘要适配，但模型卡要求额外 tokenizer 源码，且许可证未明确。"},
)


def main() -> None:
    run_id = "b2-04-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-metadata-survey"
    run_dir = RUNS_DIR / run_id; run_dir.mkdir(parents=True)
    api = HfApi(); surveyed = []
    for candidate in CANDIDATES:
        info = api.model_info(candidate["repository"])
        surveyed.append({**candidate, "revision": info.sha, "license": (info.cardData or {}).get("license"),
                         "pipeline_tag": info.pipeline_tag, "tags": info.tags, "downloads": info.downloads,
                         "trust_remote_code": False if candidate["repository"].startswith("Langboat/") else "not_acceptable_by_default",
                         "contamination_risk": "not documented as CNewSum-trained; requires pilot results only" if candidate["repository"].startswith("Langboat/") else "uncertain; fine-tuned on multiple Chinese summary corpora"})
    payload = {"run_id": run_id, "timestamp_start": utc_now(), "timestamp_end": utc_now(), "task": "B2-04", "experiment_type": "metadata_survey", "formal_result": False, "dataset": "CNewSum", "dataset_split": ["train", "dev"], "test_model_evaluation": False, "status": "completed", "surveyed": surveyed, "deep_candidate_count": 1, "notes": "未下载或运行 survey_only 候选；未执行 test 推理或评价。"}
    (run_dir / "run.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "candidate_survey.json").write_text(json.dumps(surveyed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run_dir)


if __name__ == "__main__":
    main()
