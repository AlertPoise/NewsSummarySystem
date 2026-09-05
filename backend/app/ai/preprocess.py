"""中文新闻文本预处理接口。"""


def clean_text(text: str) -> str:
    """清洗新闻文本并返回标准化正文。"""
    # TODO(C-阶段2)：实现 HTML 残留、控制字符、异常字符和多余空白的标准化；输入为原始新闻正文字符串，输出为清洗后的非伪造文本或可识别的空结果，必须遵守 docs/ARCHITECTURE.md。
    raise NotImplementedError("阶段2由C实现文本清洗")


def split_sentences(text: str) -> list[str]:
    """将已清洗的中文正文分割为有序句子列表。"""
    # TODO(C-阶段2)：实现中文分句及空文本、过短文本、超长文本的基本检查；输入为 clean_text 输出，输出为保持原文顺序的有效句子列表，必须遵守 docs/ARCHITECTURE.md。
    raise NotImplementedError("阶段2由C实现中文分句")
