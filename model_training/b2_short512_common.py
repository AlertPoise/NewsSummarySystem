"""B2-SHORT512 的 manifest、环境和模型保护共用工具。"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Iterator

import torch
import transformers

from model_training.b2_data import PROCESSED_DIR, ROOT, RUNS_DIR, stream_jsonl, utc_now
from model_training.b2_lt512_stats import TOKENIZER_REPOSITORY, TOKENIZER_REVISION

OLD_MODEL_DIR = ROOT / "runtime" / "models" / "news_summarizer"
OLD_EXPORT_RECORD = RUNS_DIR / "b2-09-20260905T152641Z-export" / "run.json"
BASE_MODEL_SNAPSHOT = ROOT / "runtime" / "hf_cache" / "hub" / "models--Langboat--mengzi-t5-base" / "snapshots" / TOKENIZER_REVISION
EXPECTED_COUNTS = {"train": 107826, "dev": 5734}
EXPECTED_TOTALS = {"train": 275596, "dev": 14356}


def sha256_file(path: Path) -> str:
    """计算单个文件的 SHA-256。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def model_fingerprint(path: Path) -> dict[str, Any]:
    """生成模型目录的稳定文件清单和大小。"""
    files = [{"name": item.name, "bytes": item.stat().st_size, "sha256": sha256_file(item)}
             for item in sorted(path.iterdir()) if item.is_file()]
    return {"files": files, "total_bytes": sum(item["bytes"] for item in files)}


def verify_old_model() -> dict[str, Any]:
    """仅按 B2-09 核心文件校验旧模型，并审计允许的元数据 sidecar。"""
    expected = json.loads(OLD_EXPORT_RECORD.read_text(encoding="utf-8"))
    expected_files = {item["name"]: item for item in expected.get("files", [])}
    actual_files = {item["name"]: item for item in model_fingerprint(OLD_MODEL_DIR)["files"]}
    mismatches = [name for name, item in expected_files.items() if actual_files.get(name) != item]
    if mismatches:
        raise RuntimeError("existing_formal_model_changed")
    sidecar = OLD_MODEL_DIR / "model_metadata.json"
    sidecar_record: dict[str, Any] = {"allowed_post_b2_09_sidecar": False}
    if sidecar.exists():
        try:
            metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("existing_formal_model_changed") from exc
        tokenizer = metadata.get("tokenizer")
        valid = (metadata.get("model_name") == TOKENIZER_REPOSITORY and metadata.get("dataset") == "CNewSum"
                 and isinstance(tokenizer, dict) and tokenizer.get("name_or_path") == TOKENIZER_REPOSITORY
                 and tokenizer.get("revision") == TOKENIZER_REVISION and metadata.get("max_input_tokens") == 512
                 and metadata.get("max_new_tokens") == 80 and isinstance(metadata.get("generation_config"), dict))
        if not valid:
            raise RuntimeError("existing_formal_model_changed")
        sidecar_record = {"allowed_post_b2_09_sidecar": True, "name": sidecar.name, "bytes": sidecar.stat().st_size,
                          "sha256": sha256_file(sidecar), "content": metadata, "metadata_origin": "unknown_but_sidecar_only"}
    return {"core_model_integrity": "PASS", "b2_09_core_files": list(expected_files.values()), "sidecar": sidecar_record}


def load_manifest(path: Path) -> list[dict[str, Any]]:
    """读取轻量 ID/source_index/token_count 清单并检查重复条目。"""
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    indexes = [entry.get("source_index") for entry in entries]
    ids = [json.dumps(entry.get("id"), ensure_ascii=False, sort_keys=True) for entry in entries]
    if len(indexes) != len(set(indexes)) or len(ids) != len(set(ids)):
        raise ValueError(f"manifest 存在重复 id 或 source_index：{path}")
    return entries


def manifest_fingerprint(path: Path) -> dict[str, Any]:
    """返回 manifest 的可追溯字节指纹。"""
    return {"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "line_count": sum(1 for line in path.open(encoding="utf-8") if line.strip())}


def iter_manifest_rows(split: str, entries: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """以 source_index 映射回 processed 数据，严格验证 id 和数量。"""
    expected = {int(entry["source_index"]): entry for entry in entries}
    found = 0
    source_count = 0
    for index, (_, row, error) in enumerate(stream_jsonl(PROCESSED_DIR / f"{split}.jsonl")):
        source_count += 1
        if error or row is None:
            raise ValueError(f"{split}:{index + 1}:{error}")
        entry = expected.get(index)
        if entry is None:
            continue
        if row.get("id") != entry.get("id"):
            raise ValueError(f"{split}:{index + 1}:manifest id 与 processed 不一致")
        found += 1
        yield row
    if found != len(entries):
        raise ValueError(f"{split}:manifest 未能完整映射：{found} != {len(entries)}")
    if source_count != EXPECTED_TOTALS[split]:
        raise ValueError(f"{split}:source 样本数不符：{source_count} != {EXPECTED_TOTALS[split]}")


def verify_manifest_domain(split: str, entries: list[dict[str, Any]], tokenizer: Any) -> dict[str, Any]:
    """重算所有 manifest 样本长度，确保严格满足 token_count < 512。"""
    count = nonempty = 0
    for row, entry in zip(iter_manifest_rows(split, entries), entries, strict=True):
        article, summary = row.get("article"), row.get("summary")
        if not isinstance(article, str) or not isinstance(summary, str) or not article.strip() or not summary.strip():
            raise ValueError(f"{split}:发现 article 或 summary 为空")
        tokens = len(tokenizer(article, add_special_tokens=True, truncation=False)["input_ids"])
        if tokens != entry.get("token_count") or tokens >= 512:
            raise ValueError(f"{split}:token_count 或 <512 域验证失败")
        count += 1; nonempty += 1
    if count != EXPECTED_COUNTS[split]:
        raise ValueError(f"{split}:lt512 数量不符：{count}")
    return {"verified_count": count, "nonempty_count": nonempty}


def environment() -> dict[str, Any]:
    """只收集可真实读取的本机训练环境。"""
    gpu = torch.cuda.get_device_properties(0) if torch.cuda.is_available() else None
    driver = None
    try:
        output = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"], capture_output=True, text=True, check=False)
        if output.returncode == 0:
            driver = output.stdout.strip().splitlines()[0]
    except OSError:
        pass
    return {"os": platform.platform(), "python_version": platform.python_version(), "torch_version": torch.__version__,
            "transformers_version": transformers.__version__, "tokenizers_version": __import__("tokenizers").__version__,
            "huggingface_hub_version": __import__("huggingface_hub").__version__, "cuda_available": torch.cuda.is_available(),
            "torch_cuda_version": torch.version.cuda, "cuda_runtime": torch.version.cuda, "gpu_name": gpu.name if gpu else None,
            "gpu_total_vram_bytes": gpu.total_memory if gpu else None, "nvidia_driver_version": driver,
            "cpu": platform.processor() or None, "ram_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") if hasattr(os, "sysconf") else None,
            "precision": "fp32"}


def git_state() -> dict[str, Any]:
    """记录真实 Git 状态，不修改工作区。"""
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    return {"branch": run("branch", "--show-current"), "commit_sha": run("rev-parse", "HEAD"), "dirty_worktree": bool(run("status", "--porcelain"))}


def disk_usage() -> dict[str, int]:
    """统计运行时关键目录占用，避免额外复制大文件。"""
    def size(directory: Path) -> int:
        return sum(item.stat().st_size for item in directory.rglob("*") if item.is_file()) if directory.exists() else 0
    return {"hf_cache_bytes": size(ROOT / "runtime" / "hf_cache"), "training_runs_bytes": size(RUNS_DIR), "models_bytes": size(ROOT / "runtime" / "models")}


def verify_base_snapshot() -> dict[str, Any]:
    """确认已缓存的冻结 base checkpoint 可离线使用，避免重复下载。"""
    required = ("config.json", "model.safetensors", "spiece.model")
    missing = [name for name in required if not (BASE_MODEL_SNAPSHOT / name).is_file()]
    if missing:
        raise FileNotFoundError(f"冻结 base checkpoint 本地缓存缺失：{missing}")
    return {"path": str(BASE_MODEL_SNAPSHOT.relative_to(ROOT)), "revision": TOKENIZER_REVISION,
            "files": [{"name": name, "bytes": (BASE_MODEL_SNAPSHOT / name).stat().st_size, "sha256": sha256_file(BASE_MODEL_SNAPSHOT / name)} for name in required]}
