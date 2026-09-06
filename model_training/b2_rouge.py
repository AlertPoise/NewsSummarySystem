"""CNewSum 官方字符级 MLROUGE 兼容评价器。"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

EVALUATOR_VERSION = "cnewsum_mlrouge_compatible_v1"
_ASCII_WORD = re.compile(r"[A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    """按官方说明切分：中文字符，英文词和数字按空格映射。"""
    tokens: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
            continue
        match = _ASCII_WORD.match(text, index)
        if match:
            tokens.append(match.group(0).lower())
            index = match.end()
        else:
            tokens.append(char)
            index += 1
    return tokens


def f_score(overlap: int, predicted_count: int, reference_count: int) -> float:
    if not overlap or not predicted_count or not reference_count:
        return 0.0
    precision, recall = overlap / predicted_count, overlap / reference_count
    return 2 * precision * recall / (precision + recall)


def ngrams(tokens: list[str], n: int) -> Counter[tuple[str, ...]]:
    return Counter(tuple(tokens[i:i + n]) for i in range(max(0, len(tokens) - n + 1)))


def rouge_n(prediction: str, reference: str, n: int) -> float:
    predicted, expected = ngrams(tokenize(prediction), n), ngrams(tokenize(reference), n)
    return f_score(sum((predicted & expected).values()), sum(predicted.values()), sum(expected.values()))


def lcs_length(left: list[str], right: list[str]) -> int:
    """以线性额外空间计算最长公共子序列。"""
    if len(left) < len(right): left, right = right, left
    row = [0] * (len(right) + 1)
    for token in left:
        previous = 0
        for column, target in enumerate(right, 1):
            saved = row[column]
            if token == target: row[column] = previous + 1
            else: row[column] = max(row[column], row[column - 1])
            previous = saved
    return row[-1]


def rouge_l(prediction: str, reference: str) -> float:
    predicted, expected = tokenize(prediction), tokenize(reference)
    return f_score(lcs_length(predicted, expected), len(predicted), len(expected))


def score(prediction: str, reference: str) -> dict[str, float]:
    return {"rouge1": rouge_n(prediction, reference, 1), "rouge2": rouge_n(prediction, reference, 2), "rougeL": rouge_l(prediction, reference)}
