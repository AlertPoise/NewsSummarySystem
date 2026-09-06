"""中文新闻文本预处理：NLP 级清洗与中文分句。

边界说明（见 docs/ARCHITECTURE.md 第 6 节）：
- D 负责网页级清洗（HTML 标签、导航、广告等 DOM 噪声），C 不解析 DOM。
- C 只做 NLP 级：控制字符、异常空白、HTML 实体残留、字符规范化、
  中文分句，以及空文本、无意义句和超长输入的处理。
"""

from __future__ import annotations

import re
import unicodedata

# 常见 HTML 实体残留（D 的网页级清洗后可能仍残留的少量转义）
_HTML_ENTITY_PATTERN = re.compile(
    r"&(?:nbsp|#160|amp|lt|gt|quot|#39|#x27);",
    flags=re.IGNORECASE,
)
# 分句结束标点
_END_PUNCT = "。！？!?…"
# 可紧跟在句末标点之后、仍归属于本句的收尾字符（引号/括号等）
_TRAILING_CHARS = "”’」』）)]\"'"
# 无意义句判定：去掉空白与标点后，不含任何中文字符
_CJK_PATTERN = re.compile(r"[一-鿿]")
# 控制字符与不可见字符（保留正常制表/换行之外的可见内容）
_CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HTML_ENTITY_MAP = {
    "&nbsp;": " ",
    "&#160;": " ",
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&#x27;": "'",
}


def clean_text(text: str) -> str:
    """清洗新闻正文，返回标准化后的非空文本（空输入返回空字符串）。

    处理内容（NLP 级，不处理 DOM）：
    - 控制字符、零宽与不可见字符的移除
    - HTML 实体残留的还原
    - 字符规范化（NFKC，全角字母数字转半角、全角空格转半角）
    - 异常空白与重复空白/空行的压缩
    """
    if not text:
        return ""
    text = _CONTROL_PATTERN.sub("", text)
    text = _HTML_ENTITY_PATTERN.sub(lambda m: _HTML_ENTITY_MAP.get(m.group(0).lower(), " "), text)
    text = unicodedata.normalize("NFKC", text)
    # 移除零宽字符与格式控制符（NFKC 不能全部覆盖的 Cf/Cc）
    text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cf", "Cc"))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)  # 压缩行内空白（全角空格已被 NFKC 转为半角）
    text = re.sub(r"\n\s*\n+", "\n", text)  # 压缩连续空行
    return text.strip()


def _is_meaningless_sentence(sentence: str) -> bool:
    """判断句子是否为无意义句（无中文字符或过短）。

    C 不负责 DOM 噪声，但纯标点、纯 URL、纯数字这类 NLP 级无意义片段
    不应进入 BERT/TextRank，以免被选入摘要或浪费 Token 预算。
    """
    stripped = re.sub(r"\s+", "", sentence)
    # 需至少两个中文字符才视为有意义的新闻句子，过滤单字应答与噪声片段
    if len(_CJK_PATTERN.findall(stripped)) < 2:
        return True
    return False


def split_sentences(text: str) -> list[str]:
    """将已清洗的中文正文切分为保持原文顺序的非空句子列表。

    分句后剔除无意义句，空文本返回空列表。超长输入的分段由调用方
    （TextRank/Token Budget）按模型预算处理，本函数不截断文本。
    """
    if not text:
        return []
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    sentences: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        sentences.extend(_split_line(line))
    return sentences


def _split_line(line: str) -> list[str]:
    """将单行文本切分为句子，句末标点连同其后引号/括号归属本句。

    连续出现的结束标点（如“？？”“！！”）视为同一分句边界。
    """
    sentences: list[str] = []
    buffer: list[str] = []
    index = 0
    length = len(line)
    while index < length:
        ch = line[index]
        buffer.append(ch)
        if ch in _END_PUNCT:
            # 吞并连续结束标点（？.？！！！等强调连用）与紧邻收尾引号/括号
            cursor = index + 1
            while cursor < length and line[cursor] in _END_PUNCT + _TRAILING_CHARS:
                buffer.append(line[cursor])
                cursor += 1
            sentence = "".join(buffer).strip()
            if sentence and not _is_meaningless_sentence(sentence):
                sentences.append(sentence)
            buffer = []
            index = cursor
        else:
            index += 1
    if buffer:
        sentence = "".join(buffer).strip()
        if sentence and not _is_meaningless_sentence(sentence):
            sentences.append(sentence)
    return sentences
