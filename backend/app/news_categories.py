"""新闻六类分类常量（D 维护）。

固定顺序与 docs/API.md 一致，NewsService 入库校验与爬虫映射共用，
避免多处重复定义造成不一致。
"""

# 系统固定六类，顺序与 API 契约一致
SIX_CATEGORIES: list[str] = ["科技", "财经", "社会", "体育", "国内", "国际"]


def is_valid_category(category: str) -> bool:
    """判断分类是否为系统六类之一。"""
    return category in SIX_CATEGORIES
