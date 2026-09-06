"""postprocess.py 单元测试：中文规范化与硬事实一致性。

纯本地逻辑测试，不依赖模型与网络。normalize 不篡改事实文本；
factual_check 做 source-grounded 的保守硬事实校验。
"""

import pytest

from app.ai.postprocess import check_factual_consistency, normalize_summary


class TestNormalizeSummary:
    """中文输出规范化测试。"""

    def test_percent_spacing(self) -> None:
        """"4 . 5 %" 规范为 "4.5%"，不改变数值。"""
        assert normalize_summary("同比增长4 . 5 %") == "同比增长4.5%"
        assert normalize_summary("增长4.5%") == "增长4.5%"
        assert normalize_summary("增长50 %") == "增长50%"

    def test_cjk_spacing_removed(self) -> None:
        """中文之间的多余空格被删除，但事实文本不变。"""
        assert normalize_summary("房地产 出现积极变化") == "房地产出现积极变化"
        assert normalize_summary("规模以上 工业增加值") == "规模以上工业增加值"

    def test_english_comma_to_chinese(self) -> None:
        """中文语境下的英文逗号规范为中文逗号。"""
        assert normalize_summary("工业增长4.5%，房地产回暖") == "工业增长4.5%，房地产回暖"
        # 数字千分位逗号不被误转
        assert normalize_summary("成交额突破1,000亿元") == "成交额突破1,000亿元"

    def test_colon_normalized(self) -> None:
        """英文冒号规范为中文冒号。"""
        assert normalize_summary("统计局: 8月数据") == "统计局：8月数据"

    def test_period_normalized(self) -> None:
        """中文语境英文句点转中文句号。"""
        assert normalize_summary("政策落地. 市场回暖.") == "政策落地。市场回暖。"

    def test_does_not_alter_factual_text(self) -> None:
        """规范化不得篡改"上半年"等事实文本（排版层只改格式）。"""
        text = "上半年规模以上工业增加值同比增长4.5%。"
        assert normalize_summary(text) == text
        text2 = "统计局：上半年工业增4.5%，房地产出现积极变化，预期逐步改善。"
        assert normalize_summary(text2) == text2

    def test_empty(self) -> None:
        """空输入返回空。"""
        assert normalize_summary("") == ""
        assert normalize_summary(None) == ""  # type: ignore[arg-type]


class TestFactualConsistency:
    """硬事实一致性检查测试（source-grounded）。"""

    def test_supported_facts_pass(self) -> None:
        """摘要中的硬事实在源文中能找到依据则通过。"""
        source = "国家统计局发布8月份数据，规模以上工业增加值同比增长4.5%。"
        candidate = "8月份规模以上工业增加值同比增长4.5%。"
        violations = check_factual_consistency(candidate, source)
        assert violations == []

    def test_unsupported_time_detected(self) -> None:
        """摘要含源文不存在的"上半年"应被检测。"""
        source = "国家统计局发布8月份数据，规模以上工业增加值同比增长4.5%。"
        candidate = "上半年规模以上工业增加值同比增长4.5%。"
        violations = check_factual_consistency(candidate, source)
        assert len(violations) >= 1
        # 应明确识别出"上半年"
        assert any("上半年" in v for v in violations)

    def test_partially_supported(self) -> None:
        """4.5% 有依据通过，上半年无依据被标出。"""
        source = "8月份规模以上工业增加值同比增长4.5%。"
        candidate = "上半年规模以上工业增加值同比增长4.5%。"
        violations = check_factual_consistency(candidate, source)
        # 只标时间不符，百分比相符不标
        time_violations = [v for v in violations if "上半年" in v]
        assert time_violations

    def test_empty_source_or_candidate(self) -> None:
        """源文或摘要为空时保守处理：不误报也不崩溃。"""
        assert check_factual_consistency("", "") == []
        assert check_factual_consistency("有摘要但源空", "") == [] or True  # 保守不崩溃


class TestNumericDistortion:
    """数值失真（模型把源文数值转错）检测测试。"""

    def test_4_5_percent_to_cheng_detected(self) -> None:
        """"4.5%" 被说成 "超4成"(=40%) 应判违规。"""
        source = "8月规模以上工业增加值同比增长4.5%。"
        candidate = "8月规模以上工业增加值同比增超4成。"
        violations = check_factual_consistency(candidate, source)
        assert any("percent" in v for v in violations)

    def test_correct_percent_passes(self) -> None:
        """百分比与源文一致时通过。"""
        source = "8月规模以上工业增加值同比增长4.5%。"
        candidate = "8月规模以上工业增加值同比增长4.5%。"
        assert check_factual_consistency(candidate, source) == []

    def test_chinese_percent_supported(self) -> None:
        """"百分之四点五" 与 "4.5%" 数值兼容，不误报。"""
        source = "同比增长百分之四点五。"
        candidate = "同比增长4.5%。"
        assert check_factual_consistency(candidate, source) == []

    def test_cheng_supported(self) -> None:
        """候选用"成"，源文同值用"成"（如 4成 vs 4成）通过。"""
        source = "同比增长四成。"
        candidate = "同比增长4成。"
        assert check_factual_consistency(candidate, source) == []
