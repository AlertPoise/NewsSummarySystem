"""CNewSum ROUGE 固定样例测试。"""

import unittest

from model_training.b2_rouge import rouge_l, score, tokenize


class RougeTests(unittest.TestCase):
    def test_chinese_character_tokens(self) -> None:
        self.assertEqual(tokenize("中 文摘要"), ["中", "文", "摘", "要"])

    def test_mixed_english_numbers_and_punctuation(self) -> None:
        self.assertEqual(tokenize("Surface Phone将装载Windows 10。"), ["surface", "phone", "将", "装", "载", "windows", "10", "。"])

    def test_empty_and_exact_match(self) -> None:
        self.assertEqual(score("", "摘要")["rougeL"], 0.0)
        self.assertEqual(score("完全一致", "完全一致"), {"rouge1": 1.0, "rouge2": 1.0, "rougeL": 1.0})

    def test_lcs(self) -> None:
        self.assertAlmostEqual(rouge_l("甲乙丙", "甲丁丙"), 2 / 3)
