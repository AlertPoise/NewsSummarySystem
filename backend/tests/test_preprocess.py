"""preprocess.py 的单元测试：文本清洗与中文分句。

这些测试为本地纯逻辑测试，不下载模型、不依赖网络，秒级完成。
"""

import pytest

from app.ai.preprocess import clean_text, split_sentences


class TestCleanText:
    """clean_text 清洗行为测试。"""

    def test_empty_input(self) -> None:
        """空输入返回空字符串。"""
        assert clean_text("") == ""
        assert clean_text(None) == ""  # type: ignore[arg-type]

    def test_control_characters_removed(self) -> None:
        """控制字符与不可见字符被移除。"""
        text = chr(0) + "新华社" + chr(0x1f) + "报道" + chr(7) + "今天天气。"
        assert clean_text(text) == "新华社报道今天天气。"

    def test_zero_width_removed(self) -> None:
        """零宽字符被移除。"""
        text = "新​华‍社报道。"
        assert clean_text(text) == "新华社报道。"

    def test_html_entity_resolved(self) -> None:
        """常见 HTML 实体残留被还原为可见字符。"""
        text = "房价&amp;租金&lt;预期&gt;上涨&nbsp;明显"
        assert clean_text(text) == "房价&租金<预期>上涨 明显"

    def test_fullwidth_normalized(self) -> None:
        """全角字母数字被 NFKC 规范为半角。"""
        text = "Ｈｕａｗｅｉ发布Ｍａｔｅ６０。１２３元"
        assert clean_text(text) == "Huawei发布Mate60。123元"

    def test_repeated_whitespace_compressed(self) -> None:
        """行内重复空白被压缩为单个空格，首尾空白被去除。"""
        text = "  今天   天气  不错 。  "
        assert clean_text(text) == "今天 天气 不错 。"


class TestSplitSentences:
    """split_sentences 中文分句行为测试。"""

    def test_empty_input(self) -> None:
        """空输入返回空列表。"""
        assert split_sentences("") == []
        assert split_sentences(None) == []  # type: ignore[arg-type]

    def test_simple_chinese_sentences(self) -> None:
        """按中文句末标点切分多句。"""
        text = "今天天气很好。我们决定去公园。"
        assert split_sentences(text) == ["今天天气很好。", "我们决定去公园。"]

    def test_exclamation_and_question(self) -> None:
        """问号、感叹号同样作为分句边界。"""
        text = "这太棒了！你确定吗？当然确定。"
        assert split_sentences(text) == ["这太棒了！", "你确定吗？", "当然确定。"]

    def test_quotes_kept_with_sentence(self) -> None:
        """句末标点后的右引号/右括号归属本句。"""
        text = '他说："开始吧。"然后离开了。'
        assert split_sentences(text) == ['他说："开始吧。"', "然后离开了。"]

    def test_multiple_puncts_merged(self) -> None:
        """连续句末标点被合并为一个边界。"""
        text = "真的假的？？我完全不信……"
        # 多个问号同属一句的强调，?？后不再重复产生空句
        result = split_sentences(text)
        assert len(result) == 2
        assert result[0].startswith("真的假的")
        assert result[1].startswith("我完全不信")

    def test_newline_separates_sentences(self) -> None:
        """换行分隔的独立句子被分别切出。"""
        text = "第一句。\n第二句也独立。"
        assert split_sentences(text) == ["第一句。", "第二句也独立。"]

    def test_meaningless_sentence_filtered(self) -> None:
        """纯数字、纯英文、纯标点等无中文字符的句子被过滤。"""
        text = "新华社北京电。12345。hello world。记者报道。"
        result = split_sentences(text)
        assert result == ["新华社北京电。", "记者报道。"]

    def test_short_noise_filtered(self) -> None:
        """过短（去空白后不足 2 字）的噪声片段被过滤。"""
        text = "新华社电。仅。报道继续。"
        assert split_sentences(text) == ["新华社电。", "报道继续。"]

    def test_order_preserved(self) -> None:
        """句子保持原文顺序。"""
        text = "第三句先说？不对，第一句在前。第二句随后。"
        result = split_sentences(text)
        assert len(result) == 3
        assert result[0].startswith("第三句先说")
        assert result[1].startswith("不对，第一句在前")
        assert result[2].startswith("第二句随后")
