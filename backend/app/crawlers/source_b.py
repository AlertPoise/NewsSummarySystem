"""第二个真实新闻来源：光明网（www.gmw.cn）。

策略：光明网首页及各子域频道页为服务端渲染，文章链接格式为
<子域>.gmw.cn/YYYY-MM/DD/content_<数字>.htm。读取首页与少数频道页，按链接的
主机子域把文章归类到系统六类，再抓取详情页静态正文。
光明网 robots.txt 未限制正文路径，无 Crawl-delay。

网页级清洗只移除 DOM 噪声，中文分句等 NLP 清洗不属于本模块职责。
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from app.crawlers.base import NewsSource, RawArticle
from app.crawlers.html_cleaner import (
    clean_web_text,
    count_chinese,
    extract_paragraphs,
    extract_title,
)
from app.crawlers.http_client import fetch_fresh_text, fetch_text

# 明显非文章的页面标题（导航/栏目聚合页），采到即跳过
_NAV_TITLES = {"全部导航", "光明网导航", "网站地图", "栏目导航"}

# 光明网文章链接：主机子域 + 日期路径 + content_数字.htm（允许出现在任意属性/脚本中）
_ARTICLE_HREF = re.compile(
    r"(?P<url>https?://(?P<host>[a-z]+\.gmw\.cn)/"
    r"\d{4}-\d{2}/\d{2}/content_\d+\.htm)"
)
# 页面内可见的完整发布时间（备用）
_DATETIME_TEXT = re.compile(r"20\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2}")

# 读取哪些列表页（首页最全，另加综合与科技频道补充）
_LIST_PAGES: list[str] = [
    "https://www.gmw.cn/",
    "https://news.gmw.cn/",
    "https://tech.gmw.cn/",
]

# 采集到的正文最少汉字数，用于过滤过短碎片页
_MIN_BODY_CHARS = 60

# 主机子域 -> 系统分类；未列出的子域（如 culture/ent 等）不采集，避免误分类
_HOST_CATEGORY: dict[str, str] = {
    "www": "国内",
    "news": "国内",
    "politics": "国内",
    "world": "国际",
    "economy": "财经",
    "sports": "体育",
    "tech": "科技",
    "legal": "社会",
    "society": "社会",
}


class SourceB(NewsSource):
    """光明网新闻来源采集器。

    读取列表页发现新闻，按主机子域映射系统六类，逐篇抓取静态正文。
    """

    def __init__(self, limit: int = 20, request_interval: float = 1.0) -> None:
        # limit：单次运行最多返回条数；request_interval：相邻详情请求间隔秒数，克制抓取
        self._limit = limit
        self._interval = request_interval

    def _discover_grouped(self) -> dict[str, list[str]]:
        """读取列表页，返回 {分类: [文章URL...]}，URL 去重保序，剔除超期旧稿。"""
        grouped: dict[str, list[str]] = {}
        deadline = datetime.now() - timedelta(days=3)
        for page in _LIST_PAGES:
            html = fetch_fresh_text(page)
            if not html:
                continue
            for match in _ARTICLE_HREF.finditer(html):
                url = match.group("url")
                subdomain = match.group("host").removesuffix(".gmw.cn")
                category = _HOST_CATEGORY.get(subdomain)
                if category is None:
                    continue
                date_match = re.search(r"/(\d{4}-\d{2})/(\d{2})/", url)
                if not date_match:
                    continue
                try:
                    publish = datetime.strptime(
                        f"{date_match.group(1)}-{date_match.group(2)}", "%Y-%m-%d"
                    )
                except ValueError:
                    continue
                if publish < deadline:
                    continue
                grouped.setdefault(category, [])
                if url not in grouped[category]:
                    grouped[category].append(url)
        return grouped

    def _parse_publish_time(self, url: str, html: str) -> datetime | None:
        """解析发布时间：优先页面可见时间，其次 meta publishdate，最后 URL 日期。"""
        for match in _DATETIME_TEXT.finditer(html):
            try:
                return datetime.strptime(match.group(0), "%Y-%m-%d %H:%M")
            except ValueError:
                continue
        soup_date = re.search(
            r'<meta[^>]+name="publishdate"[^>]+content="(\d{4}-\d{2}-\d{2})"', html
        )
        if soup_date:
            try:
                return datetime.strptime(soup_date.group(1), "%Y-%m-%d")
            except ValueError:
                pass
        date_match = re.search(r"/(\d{4}-\d{2})/(\d{2})/", url)
        if date_match:
            try:
                return datetime.strptime(
                    f"{date_match.group(1)}-{date_match.group(2)}", "%Y-%m-%d"
                )
            except ValueError:
                return None
        return None

    def _build_article(self, url: str, category: str) -> RawArticle | None:
        """抓取并解析单篇光明网文章，失败或正文过短返回 None。"""
        html = fetch_text(url)
        if not html:
            return None
        paragraphs = extract_paragraphs(
            html,
            container_selectors=[
                "#article_inbox",
                "div.con-text",
                "div.u-mainText",
                "div.g-main",
            ],
        )
        content = "\n".join(paragraphs)
        if count_chinese(content) < _MIN_BODY_CHARS:
            return None

        # 光明网正文页 <title> 即为完整标题，先取它，避免被页面导航 h1/h2 干扰
        soup = BeautifulSoup(html, "lxml")
        title = clean_web_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
        if title in _NAV_TITLES:
            return None
        # 去除标题尾部的站点后缀（形如“ _光明网”）
        for suffix in (" _光明网", " - 光明网", "｜光明网", "_光明网"):
            if title.endswith(suffix):
                title = title[: -len(suffix)].strip()
                break
        if not title:
            title = extract_title(html)
        if not title:
            return None

        publish_time = self._parse_publish_time(url, html)
        # 仅接收发布时间在 3 天内的文章，避免旧稿堆积
        if publish_time and publish_time < datetime.now() - timedelta(days=3):
            return None
        return RawArticle(
            title=title,
            content=content,
            category=category,
            source="光明网",
            source_url=url,
            publish_time=publish_time,
        )

    def fetch_articles(self) -> list[RawArticle]:
        """采集光明网新闻，各分类轮询取稿以覆盖不同栏目，克制抓取。"""
        grouped = self._discover_grouped()
        categories = list(grouped.keys())
        index = 0
        articles: list[RawArticle] = []
        while len(articles) < self._limit:
            progressed = False
            for category in categories:
                urls = grouped[category]
                if index < len(urls) and len(articles) < self._limit:
                    article = self._build_article(urls[index], category)
                    if article is not None:
                        articles.append(article)
                    progressed = True
                    time.sleep(self._interval)
            index += 1
            if not progressed:
                break
        return articles
