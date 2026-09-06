"""基于句向量的 TextRank 关键句提取与 Token Budget 选句。

流程（docs/ARCHITECTURE.md 第 5 节、REQUIREMENTS FR-09/FR-10）：
- 由 BertEncoder 得到每句一个语义向量（列表，元素为类数组）；
- 构造句间余弦相似度矩阵；
- 在其上真实执行 TextRank（PageRank 迭代）得到每句重要性得分；
- Token Budget 按 max_input_tokens 预算、按得分贪心选句，
  超长句做二次切分，最后恢复原文顺序返回选中的文本片段。
  （返回文本而非索引：索引只能表达"整句"，无法表达超长句被采纳的分段，
   选句函数须返回实际送进模型的文本，预算才算得一致。）

本文件不依赖模型与网络，便于离线单元测试。
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def _as_matrix(sentence_vectors: Sequence[object]) -> np.ndarray:
    """将句向量列表堆叠为二维数组（支持 torch Tensor / list / numpy）。"""
    rows = [np.asarray(v, dtype=np.float32) for v in sentence_vectors]
    if not rows:
        return np.empty((0, 0), dtype=np.float32)
    return np.stack(rows)


def _cosine_similarity_matrix(vectors: np.ndarray) -> np.ndarray:
    """计算句向量两两余弦相似度矩阵，对角线与零范数行做安全处理。"""
    norm = np.linalg.norm(vectors, axis=1, keepdims=True)
    # 零向量（或退化向量）范数为 0，置为极小值避免除零，视作与任何句不相似
    safe_norm = np.where(norm == 0, 1e-8, norm)
    normalized = vectors / safe_norm
    similarity = normalized @ normalized.T
    # 对角线清零（TextRank 图不应含自环），负值截断为 0
    count = similarity.shape[0]
    if count > 0:
        np.fill_diagonal(similarity, 0.0)
    return np.clip(similarity, 0.0, None)


def _pagerank(adjacency: np.ndarray, damping: float = 0.85,
              max_iter: int = 100, tol: float = 1e-4) -> np.ndarray:
    """在邻接矩阵上执行 PageRank 幂迭代，返回节点得分。

    使用与 TextRank 一致的随机游走：行随机归一化（出边归一），
    配合阻尼因子做平滑，保证图不连通的稳定性。
    """
    count = adjacency.shape[0]
    if count == 0:
        return np.empty((0,), dtype=np.float64)
    # 出度归一（每行和化为 1）；无出边的行按均匀分布处理
    out_sum = adjacency.sum(axis=1, keepdims=True)
    out_sum = np.where(out_sum == 0, 1.0, out_sum)
    transition = adjacency / out_sum
    # 随机游走矩阵：damping * transition + (1-damping)/n 的跳转
    teleport = (1.0 - damping) / count
    score = np.full(count, 1.0 / count, dtype=np.float64)
    for _ in range(max_iter):
        prev = score
        score = damping * (transition.T @ score) + teleport
        if float(np.linalg.norm(score - prev, ord=1)) < tol:
            break
    return score


def rank_sentences(sentence_vectors: object) -> list[float]:
    """计算与输入句子顺序一一对应的 TextRank 重要性得分。

    - 参数 sentence_vectors：BertEncoder 输出的每句一个向量的序列。
    - 返回：与句子顺序一致的浮点得分列表（值越大越重要，非排序索引）。
    """
    vectors = _as_matrix(sentence_vectors)  # type: ignore[arg-type]
    if vectors.shape[0] == 0:
        return []
    adjacency = _cosine_similarity_matrix(vectors)
    scores = _pagerank(adjacency)
    return [float(v) for v in scores]


# Token Budget：按 max_input_tokens 预算贪心选句，不固定 Top-N
# （见 REQUIREMENTS FR-10 与 ARCHITECTURE 第 5 节）。

def split_overlong_sentence(sentence: str, max_len: int) -> list[str]:
    """将超长句子按内部语义边界切分为不超 max_len 的分段。

    优先按子句/逗号层边界切；若仍超长则按字符硬切，避免整句超预算被丢弃。
    """
    if max_len <= 0:
        return [] if not sentence else []
    if len(sentence) <= max_len:
        return [sentence]
    # 子句边界：中文/英文逗号、顿号、分号后
    segments = _split_on_boundaries(sentence, "，,、；;")
    result: list[str] = []
    buffer = ""
    for seg in segments:
        if len(buffer) + len(seg) <= max_len:
            buffer += seg
        else:
            if buffer:
                result.append(buffer)
                buffer = ""
            # 单个子句仍超长时按字符硬切
            while len(seg) > max_len:
                result.append(seg[:max_len])
                seg = seg[max_len:]
            buffer = seg
    if buffer:
        result.append(buffer)
    return [seg for seg in result if seg.strip()]


def _split_on_boundaries(text: str, boundary_chars: str) -> list[str]:
    """在 boundary_chars 中任一分界字符处切分文本，分界字符留在前段末尾。"""
    pieces: list[str] = []
    start = 0
    for index, ch in enumerate(text):
        if ch in boundary_chars:
            pieces.append(text[start : index + 1])
            start = index + 1
    if start < len(text):
        pieces.append(text[start:])
    elif not text:
        pieces.append("")
    return pieces


def select_sentences_by_budget(
    sentences: list[str],
    scores: Sequence[float],
    max_input_tokens: int,
    *,
    char_per_token: float = 2.0,
) -> list[str]:
    """按得分贪心选择填入 Token 预算的句子片段，按原文顺序返回**文本**。

    - sentences：原文顺序的分句列表（与 scores 一一对应）。
    - scores：TextRank 重要性得分。
    - max_input_tokens：B 正式模型元信息中的 max_input_tokens 上限。
    - char_per_token：中文字符与 token 的经验折算（默认约 2 字符/token），
      实际估算在 Pipeline 中可用 tokenizer 精确化。

    策略（不固定 Top-N）：按得分从高到低尝试加入整句，使累计估算 token
    不超预算；装不下的超长句用 split_overlong_sentence 二次切分，逐段放入
    仍能容纳的分段。返回**实际选中的文本片段**（保持原文顺序直接可拼），
    因为只有"文本即预算对象"才能保证送进模型的每一段都 ≤ 预算，杜绝
    超长句按切片记账却把整句送进模型（P1-1）。
    """
    budget = int(max_input_tokens)
    if budget <= 0 or not sentences:
        return []

    def estimate_tokens(sentence: str) -> int:
        """粗略估算句子 token 数，为字符数除以折算系数后向上取整。"""
        return max(1, int(np.ceil(len(sentence) / char_per_token)))

    # 预计算每句估算 token
    token_estimates = [estimate_tokens(s) for s in sentences]
    # 以 (得分, 原文索引) 记录，按得分降序贪心
    order = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)

    # 按原文索引收集入选文本；累计估算 token 只对"实际入选文本"记账，
    # 保证送进模型的内容与预算一致（超长句只纳入能装下的分段，P1-1）。
    chosen: dict[int, list[str]] = {}
    used = 0
    for idx in order:
        token_need = token_estimates[idx]
        if token_need <= budget - used:
            # 整句可容纳
            chosen.setdefault(idx, []).append(sentences[idx])
            used += token_need
            continue
        # 整句放不下：二次切分，逐段放入仍能容纳的分段（分段按切分顺序拼接）
        for seg in split_overlong_sentence(sentences[idx], int(budget * char_per_token)):
            seg_token = estimate_tokens(seg)
            if seg_token <= budget - used:
                chosen.setdefault(idx, []).append(seg)
                used += seg_token
    return [piece for i in sorted(chosen) for piece in chosen[i]]
