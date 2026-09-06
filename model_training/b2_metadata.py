"""B2-12：正式模型 metadata 的生成来源核验与本地加载验证。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from model_training.b2_data import ROOT, RUNS_DIR, utc_now
from model_training.b2_pipeline_eval_common import MODEL_DIR, json_dump, make_run_dir

TRAIN_RUN = RUNS_DIR / "b2-07-20260905T091244Z-r0-full-train" / "run.json"
CONFIG_PATH = ROOT / "model_training" / "config.yaml"
REQUIRED = ("model_name", "model_version", "dataset", "tokenizer", "max_input_tokens", "max_new_tokens", "generation_config")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 根节点必须为对象：{path}")
    return value


def expected_metadata() -> dict[str, Any]:
    """只从 B2-07 正式训练记录和冻结 config 推导 metadata。"""
    import yaml

    train = load_json(TRAIN_RUN)
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    generation = train["generation_parameters"]
    return {
        "model_name": train["candidate_model"], "model_version": config["model"]["version"], "dataset": train["dataset"],
        "tokenizer": {"name_or_path": train["tokenizer_source"], "revision": train["tokenizer_revision"]},
        "max_input_tokens": train["training_parameters"]["max_source_length"],
        "max_new_tokens": train["training_parameters"]["max_target_length"],
        "generation_config": {key: value for key, value in generation.items() if key != "max_new_tokens"},
    }


def validate_metadata_value(metadata: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    """校验侧车字段及训练/配置来源的一致性，返回全部问题。"""
    errors = [f"missing:{name}" for name in REQUIRED if name not in metadata]
    for key, expected_value in expected.items():
        if key in metadata and metadata[key] != expected_value:
            errors.append(f"mismatch:{key}")
    if metadata.get("dataset") != "CNewSum":
        errors.append("dataset_must_be_CNewSum")
    if not isinstance(metadata.get("tokenizer"), dict):
        errors.append("tokenizer_must_be_object")
    if not isinstance(metadata.get("generation_config"), dict):
        errors.append("generation_config_must_be_object")
    return errors


def validate_loadability(model_dir: Path, loader: Callable[[Path], None] | None = None) -> None:
    """验证正式 tokenizer 与权重能以本地模式加载；不下载也不改写模型。"""
    if loader is not None:
        loader(model_dir)
        return
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    AutoTokenizer.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False)
    del model


def validate(model_dir: Path = MODEL_DIR, *, loader: Callable[[Path], None] | None = None) -> dict[str, Any]:
    """执行 B2-12 全量核验，核心不一致立即失败。"""
    metadata_path = model_dir / "model_metadata.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(metadata_path)
    metadata, expected = load_json(metadata_path), expected_metadata()
    errors = validate_metadata_value(metadata, expected)
    if errors:
        raise ValueError("metadata_validation_failed:" + ",".join(errors))
    required_files = ("config.json", "generation_config.json", "tokenizer.json")
    missing_files = [name for name in required_files if not (model_dir / name).is_file()]
    if not any((model_dir / name).is_file() for name in ("model.safetensors", "pytorch_model.bin")):
        missing_files.append("model_weights")
    if missing_files:
        raise FileNotFoundError("missing_model_files:" + ",".join(missing_files))
    validate_loadability(model_dir, loader)
    return {"metadata": metadata, "expected": expected, "model_dir": str(model_dir.relative_to(ROOT))}


def main() -> None:
    parser = argparse.ArgumentParser(description="B2-12 正式模型元信息核验")
    parser.add_argument("--validate", action="store_true", help="校验既有 metadata（默认行为）")
    parser.add_argument("--write-if-missing", action="store_true", help="仅在缺失且来源完整时写入 metadata")
    args = parser.parse_args()
    run_id, run_dir = make_run_dir("b2-12", "metadata-validate")
    record: dict[str, Any] = {"run_id": run_id, "parent_run_id": "b2-09-20260905T152641Z-export", "timestamp_start": utc_now(), "task": "B2-12", "experiment_type": "metadata_validation", "formal_result": True, "status": "running", "metadata_path": str((MODEL_DIR / "model_metadata.json").relative_to(ROOT)), "error": None}
    json_dump(run_dir / "run.json", record)
    try:
        target = MODEL_DIR / "model_metadata.json"
        if args.write_if_missing and not target.exists():
            json_dump(target, expected_metadata())
            record["metadata_written"] = True
        result = validate()
        record.update({"status": "completed", "timestamp_end": utc_now(), "model_name": result["metadata"]["model_name"], "model_version": result["metadata"]["model_version"], "max_input_tokens": result["metadata"]["max_input_tokens"], "max_new_tokens": result["metadata"]["max_new_tokens"], "generation_config": result["metadata"]["generation_config"]})
    except Exception as exc:
        record.update({"status": "failed", "timestamp_end": utc_now(), "error": f"{type(exc).__name__}: {exc}"})
        raise
    finally:
        json_dump(run_dir / "run.json", record)
    print(run_dir)


if __name__ == "__main__":
    main()
