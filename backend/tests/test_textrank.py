"""textrank.py 的单元测试：余弦相似度、PageRank、Token Budget 选句。

纯 numpy 本地测试，不下载模型、不依赖网络与 torch。
"""

import numpy as np
import pytest

from app.ai.textrank import (
    rank_sentences,
    select_sentences_by_budget,
    split_overlong_sentence,
)


class TestRankSentences:
    """TextRank/PageRank 得分计算测试。"""

    def test_empty_input(self) -> None:
        """空输入返回空得分列表。"""
        assert rank_sentences([]) == []

    def test_single_sentence(self) -> None:
        """单句返回长度为 1 的得分。"""
        scores = rank_sentences([np.array([1.0, 0.0])])
        assert len(scores) == 1

    def test_returns_one_score_per_sentence(self) -> None:
        """得分数量与句子数量一一对应。"""
        vectors = [np.random.rand(8) for _ in range(5)]
        scores = rank_sentences(vectors)
        assert len(scores) == 5

    def test_pagerank_converges_and_bounded(self) -> None:
        """PageRank 得分收敛到 [0,1] 之间的有限值。"""
        vectors = [np.random.rand(16) for _ in range(20)]
        scores = rank_sentences(vectors)
        assert all(0.0 <= s <= 1.0 for s in scores)

    def test_similar_sentences_rank_higher(self) -> None:
        """与多数句子相似的中心句得分更高。"""
        # 句0 与三句两两正交的句向量保持均匀较高余弦，构成图中的中心节点
        v0 = np.array([1.0, 0.0, 0.0])
        others = [
            np.array([1.0, 2.0, 0.0]),
            np.array([1.0, 0.0, 2.0]),
            np.array([1.0, -2.0, 0.0]),
        ]
        vectors = [v0] + others
        scores = rank_sentences(vectors)
        assert scores[0] == max(scores)

    def test_deterministic(self) -> None:
        """相同输入得分结果稳定可复现。"""
        vectors = [np.random.rand(8) for _ in range(6)]
        first = rank_sentences(vectors)
        second = rank_sentences(vectors)
        assert first == second

    def test_zero_vectors_do_not_crash(self) -> None:
        """零向量（全 0）不导致除零或崩溃。"""
        vectors = [np.zeros(4), np.ones(4), np.zeros(4)]
        scores = rank_sentences(vectors)  # 不应抛异常
        assert len(scores) == 3


class TestTokenBudget:
    """Token Budget 贪心选句测试。"""

    def test_empty(self) -> None:
        """空句子返回空索引。"""
        assert select_sentences_by_budget([], [], 100) == []

    def test_short_text_fits_entirely(self) -> None:
        """文本总 token 低于预算时全部入选，顺序保持原文。"""
        sentences = ["甲句。", "乙句。", "丙句。"]
        scores = [0.9, 0.1, 0.5]
        idx = select_sentences_by_budget(sentences, scores, max_input_tokens=500)
        assert idx == [0, 1, 2]  # 全部入选，保持原序

    def test_selects_highest_scoring_under_budget(self) -> None:
        """预算不足时按得分贪心，返回原序索引。"""
        # 每句约 5 字，char_per_token=2 时约 3 token
        sentences = ["这是第一句很长。", "这是第二句很长。", "这是第三句很长。"]
        scores = [0.1, 0.9, 0.2]
        # 预算只够约 2 句（3 token/句），应选得分最高的第1句(索引1)与次高的第2句(索引2)
        idx = select_sentences_by_budget(sentences, scores, max_input_tokens=8)
        assert idx == sorted(idx)  # 原序
        assert 1 in idx
        assert len(idx) >= 1

    def test_not_fixed_top_n(self) -> None:
        """选句数量由预算决定，不固定为 Top-N。"""
        sentences = ["句一内容。", "句二内容。", "句三内容。", "句四内容。", "句五内容。"]
        scores = [0.5, 0.4, 0.3, 0.2, 0.1]
        # 大预算选全部，小预算只选部分，证明不是硬编码 N
        big = select_sentences_by_budget(sentences, scores, max_input_tokens=100)
        small = select_sentences_by_budget(sentences, scores, max_input_tokens=6)
        assert len(big) == 5
        assert len(small) < 5

    def test_overlong_sentence_split(self) -> None:
        """超长句被切分为不超限的分段。"""
        segs = split_overlong_sentence("这是" * 30, max_len=10)
        assert all(len(s) <= 10 for s in segs)
        assert "".join(segs) == "这是" * 30

    def test_overlong_under_budget(self) -> None:
        """含超长句时能二次切分并入预算，不整体丢弃。"""
        long_sentence = "，" .join(["重要内容" * 5] * 3)  # 含逗号的长句
        sentences = [long_sentence, "短句。"]
        scores = [0.95, 0.05]
        idx = select_sentences_by_budget(sentences, scores, max_input_tokens=20)
        assert 0 in idx  # 高分长句通过切分进入摘要


if __name__ == "__main__":
    # 允许直接运行本文件做快速冒烟
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
