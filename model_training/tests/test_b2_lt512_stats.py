"""B2 短文本统计的纯逻辑测试。"""

import unittest

from model_training.b2_lt512_stats import classify_token_count, estimate_training_seconds


class Lt512StatsTests(unittest.TestCase):
    """不依赖模型下载的数据边界测试。"""

    def test_token_count_boundaries(self) -> None:
        """511、512、513 必须落入三个不同域。"""
        self.assertEqual(classify_token_count(511), "lt512")
        self.assertEqual(classify_token_count(512), "eq512")
        self.assertEqual(classify_token_count(513), "gt512")

    def test_training_estimates(self) -> None:
        """估算保持线性比例并给出 15% 保守开销。"""
        estimate = estimate_training_seconds(50, 100, 200.0, 10.0)
        self.assertEqual(estimate["sample_count_linear_seconds"], 100.0)
        self.assertEqual(estimate["throughput_raw_seconds"], 5.0)
        self.assertEqual(estimate["throughput_conservative_seconds"], 5.75)
