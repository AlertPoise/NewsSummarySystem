"""基于句向量的 TextRank 接口。"""


def rank_sentences(sentence_vectors: object) -> list[float]:
    """计算与输入句子顺序对应的重要性得分。"""
    # TODO(C-阶段2)：使用余弦相似度构造句子图并真实执行 TextRank/PageRank；输入为 BertEncoder 输出的句向量，输出为一一对应的浮点重要性得分，必须遵守 docs/AI_PIPELINE.md。
    raise NotImplementedError("阶段2由C实现TextRank")
