"""B2 Benchmark 统计与 warmup 逻辑测试。"""

from model_training.b2_pipeline_eval_common import latency_summary, latency_target_met, percentile
from model_training.benchmark import measure_pipeline


class Result:
    summary = "摘要"
    model_version = "v1"


class Pipeline:
    def __init__(self) -> None:
        self.calls = []

    def generate(self, article: str):
        self.calls.append(article)
        return Result()


def test_percentile_and_strict_latency_threshold() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0, 5.0], 0.95) == 4.8
    result = latency_summary([1499.9, 1500.0])
    assert result["latency_pass_count"] == 1
    assert result["latency_pass_rate"] == 0.5


def test_warmup_is_not_in_latency_records() -> None:
    pipeline = Pipeline()
    rows = [{"id": 1, "article": "a", "article_token_count": 1}, {"id": 2, "article": "b", "article_token_count": 1}]
    values, failures = measure_pipeline(pipeline, rows, warmup_runs=1, synchronize=lambda: None)
    assert failures == 0
    assert len(values) == 2
    assert pipeline.calls == ["a", "a", "b"]


def test_course_performance_decision_uses_latency_target() -> None:
    assert latency_target_met({"latency_pass_rate": 0.95, "p95_generation_time_ms": 1499.9}) is True
    assert latency_target_met({"latency_pass_rate": 0.94, "p95_generation_time_ms": 100.0}) is False
