"""中文摘要输出规范化与硬事实一致性检查。

本模块是 C 在线 Pipeline 的质量控制层，独立于 Transformer 生成：
- normalize_summary：对模型原始输出做中文排版规范化（不改事实/数值）
- 硬事实检查：见 factcheck.py 或本文件后续扩展

设计约束（docs/ARCHITECTURE.md 冻结接口不变）：
- 只做排版与标点规范化，绝不改变数字本身的值或新闻事实
- 规范化必须在 Transformer decode 之后、返回给调用方之前执行
"""

from __future__ import annotations

import re

# 数字与单位/百分号之间的空格：如 "4 . 5 %" -> "4.5%"，"50 %" -> "50%"
_PERCENT_SPACE_PATTERN = re.compile(r"\s*%\s*")
# 中文与英文逗号/冒号：规范为中文标点
# 规则：中文字符之间的英文逗号 -> 中文逗号
_COMMA_BETWEEN_CJK = re.compile(r"(?<=[一-鿿，。；：！？）】])[,](?=[一-鿿（【])")
# 数字、百分号前后的空格统一处理：先移除百分号内空格，再处理一般性标点

# 常见全半角标点映射（规范化顺序：先处理需要上下文的，再处理盲转）
# 注意：不能盲转所有逗号——英文数字列表中的逗号(如 1,000)要保留


def _fix_percent_spacing(text: str) -> str:
    """修正百分比与数字的空格：'4 . 5 %' -> '4.5%'。

    先去掉数字内部空格（4 . 5 -> 4.5），再去掉 % 前的空格。
    """
    # 数字间的空格（如 "4 . 5"）：仅当两侧都是数字或小数点时移除
    text = re.sub(r"(?<=\d)\s*\.\s*(?=\d)", ".", text)
    # % 前的空格移除
    text = re.sub(r"\s*%", "%", text)
    # 数字与紧邻单位的空格（如 "50 万人" 保留语义，此处不处理非 % 单位）
    return text


def _fix_basic_spacing(text: str) -> str:
    """删除中文字符与中文字符之间、以及中文与标点之间的多余空格。

    保留数字与数字之间可能的必要空格不做破坏（但中文上下文一般无此需求）。
    """
    # 中文之间的空格删除：汉字 汉字 -> 汉字汉字
    text = re.sub(r"(?<=[一-鿿])\s+(?=[一-鿿])", "", text)
    # 中文与中文标点之间的空格删除
    text = re.sub(r"(?<=[一-鿿])\s+(?=[，。；：！？、）】》])", "", text)
    text = re.sub(r"(?<=[（【《])\s+(?=[一-鿿])", "", text)
    # 中文与英文字母/数字之间保留适当空格？——中文排版常不加，但为稳妥，
    # 仅处理"明显多余"的：连续多个空格压缩为单个
    return text


def _fix_punctuation(text: str) -> str:
    """把中文语境下的英文标点规范为中文标点。

    采用"先临时去掉标点两侧空格，转换，再还原必要空格"的顺序，避免被
    模型输出里标点旁的空格干扰 lookbehind/lookahead。
    """
    # 1. 记录并剔除中文字符与英文逗号/冒号之间的空格（这些空格本就该删）
    #    简化：把 "字 ," / ", 字" 这类中间的空格先标记占位删除
    # 先处理百分号/小数点已在前序完成，这里专注逗号冒号句点
    # —— 做法：把紧跟中文的英文标点（可能带空格）先抽成中缀再转换

    # 2. 用宽松边界转换：中文(或已转中文标点)与英文标点之间允许 0~1 空格
    #    逗号/分号
    text = re.sub(r"(?<=[一-鿿，。；：！？])\s*[,;]\s*(?=[一-鿿（【])",
                  lambda m: "，" if m.group(0).strip() == "," else "；", text)
    #    冒号（后面可接中文、数字、引号——如 "统计局:8月""统计局: 上半年"）
    text = re.sub(r"(?<=[一-鿿])\s*[:：]\s*(?=[一-鿿0-9（【\"'])", "：", text)
    #    句点（非小数点，两侧是中文/中文标点/行尾）——避免误转数字中的小数点
    text = re.sub(r"(?<=[一-鿿，；])\s*[.](?=\s*(?:[一-鿿（【]|$))", "。", text)
    return text


def _collapse_whitespace(text: str) -> str:
    """压缩连续空白为单个空格，并去除首尾。"""
    return re.sub(r"\s+", " ", text).strip()


def _final_punctuation_fix(text: str) -> str:
    """收尾兜底：把残留的、明显属于中文句的英文逗号转为中文。

    处理对象：中文句内被空格/百分号等隔开、上面宽松规则没覆盖到的英文逗号，
    例如 "4.5% , 房地产" 中紧跟百分号的逗号。保守判断：若逗号后紧跟中文字符，
    且逗号前是数字/百分号/中文，则转中文逗号并去掉其前空格。
    """
    # 数字或百分号后、中文前的英文逗号：", 房" -> "，房"
    text = re.sub(r"(?<=[0-9%])\s*,\s*(?=[一-鿿])", "，", text)
    # 残留的 "X ," 形式（英文逗号前是中文但后接的是数字/引号）不盲转，保持保守
    return text


def normalize_summary(summary: str) -> str:
    """规范化模型生成的摘要文本（排版层，不改事实）。

    处理：
    - "4 . 5 %" -> "4.5%"（数字内部与 % 前空格）
    - 中文字符之间的多余空格删除（"房地产 出现" -> "房地产出现"）
    - 中文语境英文逗号/冒号/句点 -> 中文标点
    - 重复空格压缩
    不会改变数字本身的值，也不会增删事实性词语。
    """
    if not summary:
        return ""
    text = _fix_percent_spacing(summary)
    text = _fix_basic_spacing(text)
    text = _fix_punctuation(text)
    text = _collapse_whitespace(text)
    text = _final_punctuation_fix(text)
    # 二次清理：规范化过程中可能再引入的中文间空格
    text = _fix_basic_spacing(text)
    # 中文标点后不留空格（如 "。 市" -> "。市"）
    text = re.sub(r"(?<=[，。；：！？、）】]) +", "", text)
    return text


# ============================================================================
# 硬事实一致性检查（source-grounded validation）
# ============================================================================
# 原则：摘要中出现的"硬事实"（百分比/普通数字/年份/月份/日期/季度/
# 上半年下半年/时间范围）应能在源文/清洗后正文中找到依据。只处理可确定
# 的硬事实，不做复杂语义推断；"8月份"与"上半年"绝不视为同一事实。
# ============================================================================

# 时间范围表达（风险词）
_TIME_RANGE_PATTERNS = [
    re.compile(r"上半年"),
    re.compile(r"下半年"),
    re.compile(r"第一季度"),
    re.compile(r"第二季度"),
    re.compile(r"第三季度"),
    re.compile(r"第四季度"),
    re.compile(r"[一二三四]季度"),
]

# 月份：如 "8月"、"八月"、"8月份"、"八月份"
_MONTH_PATTERNS = [
    re.compile(r"[0-9]{1,2}月"),
    re.compile(r"[一二三四五六七八九十]{1,3}月"),
]

# 年份：如 "2024年"、"2024"
_YEAR_PATTERNS = [
    re.compile(r"20[0-2][0-9]年"),
    re.compile(r"19[0-9]{2}年"),
]

# 百分比数字：如 "4.5%"、"百分之四点五"、"50%"
_PERCENT_PATTERNS = [
    re.compile(r"[0-9]+(?:\.[0-9]+)?%"),
    re.compile(r"百分之[零一二三四五六七八九十百千万点]+"),
]

# 普通数字（不含百分号/年份/月份的裸数字）：如 "300"、"一万亿元"
_NUMBER_PATTERNS = [
    re.compile(r"[0-9]+(?:\.[0-9]+)?"),
    re.compile(r"[零一二三四五六七八九十百千万亿]+"),
]

# 季度 + 年份组合：如 "2024年第一季度"
_YEAR_QUARTER_PATTERNS = [
    re.compile(r"20[0-2][0-9]年[一二三四]季度"),
]


def _collect_hard_facts(text: str) -> dict[str, list[str]]:
    """从文本中收集硬事实，按类型分组返回（用于 source-grounded 比对）。

    返回形如：{"percent": [...], "month": [...], "year": [...], ...}
    只收集可以明确界定的硬事实，宁少勿滥。
    """
    facts: dict[str, list[str]] = {}
    # 年份+季度 复合（先匹配，避免被拆成单独年份）
    for pat in _YEAR_QUARTER_PATTERNS:
        facts.setdefault("year_quarter", []).extend(pat.findall(text))
    for pat in _PERCENT_PATTERNS:
        facts.setdefault("percent", []).extend(pat.findall(text))
    for pat in _MONTH_PATTERNS:
        facts.setdefault("month", []).extend(pat.findall(text))
    for pat in _YEAR_PATTERNS:
        facts.setdefault("year", []).extend(pat.findall(text))
    # 季度词（不与年绑定的 "上半年" 等单独在 _TIME_RANGE 处理）
    for pat in _TIME_RANGE_PATTERNS:
        facts.setdefault("time_range", []).extend(pat.findall(text))
    # 普通裸数字（如 "300家医院"）——收集，但比对时降噪
    for pat in _NUMBER_PATTERNS:
        facts.setdefault("number", []).extend(pat.findall(text))
    return facts


def _normalize_number(value: str) -> str:
    """数值归一：全角转半角、去掉空格与无意义前后缀，便于比对。

    "百分之四点五" -> "4.5"（中文数字转阿拉伯）
    "4 . 5" -> "4.5"
    "4.5%" -> "4.5"（去掉百分号交由 percent 类型处理）
    """
    # 全角转半角
    value = (
        value.replace("０", "0").replace("１", "1").replace("２", "2")
        .replace("３", "3").replace("４", "4").replace("５", "5")
        .replace("６", "6").replace("７", "7").replace("８", "8").replace("９", "9")
    )
    value = re.sub(r"\s+", "", value)
    return value


def _contains_supported(candidate_fact: str, source_facts: list[str]) -> bool:
    """判断单个候选硬事实是否在源文硬事实集合中有依据（字符级包含）。"""
    if not source_facts:
        return False
    # 归一化（去掉百分号、统一数字写法）后做包含判断
    cand_norm = _normalize_number(candidate_fact).rstrip("%")
    for src in source_facts:
        src_norm = _normalize_number(src).rstrip("%")
        if not cand_norm or not src_norm:
            continue
        # 数值相等或一方包含另一方（如 "4.5" vs "百分之四点五" 归一后都是 "4.5"）
        if cand_norm == src_norm:
            return True
    return False


def check_factual_consistency(candidate: str, source: str) -> list[str]:
    """检查摘要(candidate)的硬事实是否都有源文(source)依据。

    返回违反列表；空列表表示通过。只检查硬事实，普通语义不判断。
    若源文为空或候选为空，保守返回空（不做误报）。
    """
    violations: list[str] = []
    if not candidate or not source:
        return violations

    src_facts = _collect_hard_facts(source)
    cand_facts = _collect_hard_facts(candidate)

    # 逐类型检查候选硬事实是否在源文有依据
    # percent / month / year 为高置信类型
    for fact_type in ("year_quarter", "percent", "month", "year"):
        for fact in cand_facts.get(fact_type, []):
            supported = _contains_supported(fact, src_facts.get(fact_type, []))
            if not supported:
                violations.append(f"{fact_type}: {fact}（源文无依据）")

    # time_range（上半年/下半年/季度）：需要源文含有相同的 time_range 词
    for tr in cand_facts.get("time_range", []):
        if tr not in src_facts.get("time_range", []):
            violations.append(f"time_range: {tr}（源文无依据）")

    return violations
