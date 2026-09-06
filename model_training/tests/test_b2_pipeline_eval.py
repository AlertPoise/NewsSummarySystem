"""B2-10 评价逻辑的无大模型测试。"""

import io
import json

import pytest

from model_training.b2_evaluate_pipeline_test import evaluate_pipeline
from model_training.b2_pipeline_eval_common import (aggregate_rouge, deterministic_sample, eligibility_counts,
    quality_summary, sample_manifest, token_count)


class FakeTokenizer:
    def __init__(self) -> None:
        self.calls = []

    def __call__(self, text, **kwargs):
        self.calls.append(kwargs)
        return {"input_ids": list(range(len(text)))}


class Result:
    def __init__(self, text: str) -> None:
        self.summary = text
        self.model_version = "v1"
        self.generation_time_ms = 1


class Pipeline:
    def generate(self, article: str):
        if article == "long":
            raise InputTooLongError("unexpected")
        if article == "bad":
            raise RuntimeError("boom")
        return Result("摘要")


class InputTooLongError(Exception):
    pass


def test_eligibility_uses_untruncated_special_tokens_and_boundaries() -> None:
    tokenizer = FakeTokenizer()
    assert token_count(tokenizer, "abc") == 3
    assert tokenizer.calls == [{"add_special_tokens": True, "truncation": False}]
    result = eligibility_counts(({"article": "aaaa"}, {"article": "aaaaa"}), tokenizer, 4)
    assert result == {"full_test_count": 2, "eligible_count": 1, "excluded_count": 1, "eligible_ratio": 0.5}


def test_macro_metrics_quality_and_empty_result() -> None:
    values = [{"rouge1": 0.2, "rouge2": 0.1, "rougeL": 0.4}, {"rouge1": 0.6, "rouge2": 0.3, "rougeL": 0.8}]
    assert aggregate_rouge(values)["corpus_rougeL"] == pytest.approx(0.6)
    assert quality_summary(values) == {"quality_pass_count": 2, "quality_pass_rate": 1.0}
    assert aggregate_rouge([])["evaluated_count"] == 0
    assert quality_summary([])["quality_pass_rate"] is None


def test_pipeline_failure_and_contract_mismatch_are_recorded(monkeypatch) -> None:
    rows = iter(({"id": 1, "article": "good", "reference": "摘要", "article_token_count": 4}, {"id": 2, "article": "long", "reference": "摘要", "article_token_count": 4}, {"id": 3, "article": "bad", "reference": "摘要", "article_token_count": 4}))
    monkeypatch.setattr("model_training.b2_evaluate_pipeline_test.iter_eligible_rows", lambda *args, **kwargs: rows)
    output = io.StringIO()
    values, failures, mismatch = evaluate_pipeline(Pipeline(), FakeTokenizer(), InputTooLongError, max_input_tokens=4, output=output)
    records = [json.loads(line) for line in output.getvalue().splitlines()]
    assert len(values) == 1 and failures == 2 and mismatch is True
    assert records[1]["status"] == "pipeline_contract_mismatch"
    assert records[2]["status"] == "failed"


def test_sha256_sampling_is_reproducible_and_order_independent() -> None:
    rows = [{"id": value, "article": str(value), "reference": "摘要", "article_token_count": 1} for value in range(400)]
    selected = deterministic_sample(rows, 300, "20260907")
    reordered = deterministic_sample(list(reversed(rows)), 300, "20260907")
    assert [row["id"] for row in selected] == [row["id"] for row in reordered]
    assert len(selected) == 300
    assert len(deterministic_sample(rows[:2], 300, "20260907")) == 2
    manifest = sample_manifest(selected, sample_size_requested=300, seed="20260907", counts={"full_test_count": 500, "eligible_count": 400, "excluded_count": 100, "eligible_ratio": 0.8})
    assert manifest["selection_method"].startswith("SHA256")
    assert manifest["sample_size_actual"] == 300
