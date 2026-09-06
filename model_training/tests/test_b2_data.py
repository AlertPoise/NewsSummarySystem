"""B2 数据工具的关键纯逻辑测试。"""

import unittest

from model_training.b2_data import normalize_record, percentile, summarize


class DataToolTests(unittest.TestCase):
    def test_normalize_retains_sentence_boundary_and_fields(self) -> None:
        value = normalize_record({"id": 7, "article": ["甲", "乙"], "summary": "丙", "label": [0], "adequacy": 1}, "test_anno", "x")
        self.assertEqual(value["article"], "甲 乙")
        self.assertEqual(value["article_sentences"], ["甲", "乙"])
        self.assertEqual(value["adequacy"], 1)

    def test_summary_statistics(self) -> None:
        values = [1, 2, 3, 4, 5]
        self.assertEqual(percentile(values, .95), 4.8)
        self.assertEqual(summarize(values)["median"], 3)
