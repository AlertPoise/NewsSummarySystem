"""B2-12/B2-13 的来源一致性和固定交付字段测试。"""

import pytest

from model_training.b2_delivery import DELIVERY_FIELDS, build_course_sampled_payload, build_payload
from model_training.b2_metadata import expected_metadata, validate_metadata_value


def test_metadata_validation_rejects_model_version_mismatch() -> None:
    metadata = expected_metadata()
    metadata["model_version"] = "wrong"
    assert "mismatch:model_version" in validate_metadata_value(metadata, expected_metadata())


def test_delivery_has_exact_fields_and_rejects_unaccepted_dependency() -> None:
    metadata = expected_metadata()
    quality = {"task": "B2-10", "formal_result": True, "acceptance_status": "passed", "model_name": metadata["model_name"], "model_version": metadata["model_version"], "evaluated_count": 2, "rouge1": 0.5, "rouge2": 0.4, "corpus_rougeL": 0.5}
    benchmark = {"task": "B2-14", "formal_result": True, "acceptance_status": "passed", "model_version": metadata["model_version"], "avg_generation_time_ms": 12.0, "p95_generation_time_ms": 15.0}
    assert tuple(build_payload(quality, benchmark)) == DELIVERY_FIELDS
    benchmark["acceptance_status"] = "failed"
    with pytest.raises(ValueError, match="delivery_requires"):
        build_payload(quality, benchmark)


def test_delivery_rejects_different_model_versions() -> None:
    metadata = expected_metadata()
    quality = {"task": "B2-10", "formal_result": True, "acceptance_status": "passed", "model_name": metadata["model_name"], "model_version": "quality-v", "evaluated_count": 1, "rouge1": 0.5, "rouge2": 0.5, "corpus_rougeL": 0.5}
    benchmark = {"task": "B2-14", "formal_result": True, "acceptance_status": "passed", "model_version": "benchmark-v", "avg_generation_time_ms": 1.0, "p95_generation_time_ms": 1.0}
    with pytest.raises(ValueError, match="model_version_mismatch"):
        build_payload(quality, benchmark)


def test_course_sampled_delivery_writes_real_quality_sample_count_and_provenance() -> None:
    metadata = expected_metadata()
    quality = {"run_id": "quality", "task": "B2-10", "evaluation_profile": "course_sampled", "status": "completed", "model_name": metadata["model_name"], "model_version": metadata["model_version"], "evaluated_count": 300, "rouge1": 0.5, "rouge2": 0.4, "corpus_rougeL": 0.5, "full_test_count": 14355, "eligible_count": 5447, "excluded_count": 8908, "sampling_seed": "20260907", "sampling_method": "SHA256", "course_sampled_acceptance": True}
    benchmark = {"run_id": "benchmark", "task": "B2-11", "evaluation_profile": "course_sampled", "status": "completed", "model_version": metadata["model_version"], "sample_count": 100, "avg_generation_time_ms": 10.0, "p95_generation_time_ms": 12.0, "course_sampled_acceptance": True, "c2_14_required": False, "b2_14_required": False}
    payload, provenance = build_course_sampled_payload(quality, benchmark)
    assert payload["sample_count"] == 300
    assert provenance["performance_sample_size"] == 100
    assert provenance["full_evaluation"] is False
    assert provenance["c2_14_required"] is False


def test_course_sampled_delivery_requires_non_aborted_runs() -> None:
    metadata = expected_metadata()
    quality = {"task": "B2-10", "evaluation_profile": "course_sampled", "status": "aborted", "model_name": metadata["model_name"], "model_version": metadata["model_version"]}
    benchmark = {"task": "B2-11", "evaluation_profile": "course_sampled", "status": "completed", "model_version": metadata["model_version"]}
    with pytest.raises(ValueError, match="delivery_requires_course"):
        build_course_sampled_payload(quality, benchmark)
