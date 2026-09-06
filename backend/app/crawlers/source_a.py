"""第一个真实新闻来源：新华网（www.news.cn）。

策略：新华网频道页正文链接多为 JS 渲染，但首页是服务端渲染，含大量带频道前缀的
文章链接（/politics/、/world/、/sports/、/tech/、/fortune/ 等）。本采集器读取首页，
按 URL 前缀把文章归类到系统六类，再抓取详情页静态正文。
新华网 robots.txt 为 Allow:/，无 Crawl-delay。

网页级清洗只移除 DOM 噪声，中文分句等 NLP 清洗不属于本模块职责。
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin

from app.crawlers.base import NewsSource, RawArticle
from app.crawlers.html_cleaner import (
    count_chinese,
    extract_paragraphs,
    extract_title,
)
from app.crawlers.http_client import fetch_fresh_text, fetch_text

# 新华网首页文章页路径：/频道/YYYYMMDD/32位哈希/c.html
# 注意：当天稿块不一定位于带引号的 href 属性内，故不限定引号，直接匹配路径出现处
_ARTICLE_HREF = re.compile(r"(?P<path>/[a-z]+/20\d{6}/[0-9a-f]{32}/c\.html)")
# 详情页发布时间常见书写
_DATETIME_TEXT = re.compile(r"20\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2}(:\d{2})?")

# 发现文章所读取的列表页：首页 + 已确认服务端渲染的频道页
_LIST_PAGES: list[str] = [
    "http://www.news.cn/",
    "http://www.news.cn/politics/",
    "http://www.news.cn/world/",
    "http://www.news.cn/sports/",
    "http://www.news.cn/tech/",
]

# 采集到的正文最少汉字数，用于过滤过短碎片页
_MIN_BODY_CHARS = 60

# URL 频道前缀 -> 系统分类；未列出的前缀不采集，避免误分类。
# 注意：/leaders/ 页面为 JS 动态版式，静态正文无法提取，故不纳入。
_PREFIX_CATEGORY: dict[str, str] = {
    "politics": "国内",
    "government": "国内",
    "local": "国内",
    "world": "国际",
    "sports": "体育",
    "tech": "科技",
    "digital": "科技",
    "fortune": "财经",
    "money": "财经",
    "energy": "财经",
    "legal": "社会",
}

# 只保留最近 N 天内的文章，聚焦最新新闻并避免无效抓取
_KEEP_DAYS = 2


class SourceA(NewsSource):
    """新华网新闻来源采集器。

    读取首页发现新闻，按 URL 前缀映射系统六类，逐篇抓取静态正文。
    """

    def __init__(self, limit: int = 20, request_interval: float = 1.0) -> None:
        # limit：单次运行最多返回条数；request_interval：相邻详情请求间隔秒数，克制抓取
        self._limit = limit
        self._interval = request_interval

    def _collect_page(
        self,
        html: str,
        page: str,
        deadline: datetime,
        grouped: dict[str, list[str]],
        today: str,
    ) -> int:
        """把一个列表页的文章并入 grouped，返回新加入的当天稿件数量。"""
        added_today = 0
        for match in _ARTICLE_HREF.finditer(html):
            path = match.group("path")
            prefix = path.split("/")[1]
            category = _PREFIX_CATEGORY.get(prefix)
            if category is None:
                continue
            date_match = re.search(r"/(20\d{6})/", path)
            if not date_match:
                continue
            try:
                publish = datetime.strptime(date_match.group(1), "%Y%m%d")
            except ValueError:
                continue
            if publish < deadline:
                continue
            url = urljoin(page, path)
            bucket = grouped.setdefault(category, [])
            if url not in bucket:
                bucket.append(url)
                if date_match.group(1) == today:
                    added_today += 1
        return added_today

    def _discover_grouped(self) -> dict[str, list[str]]:
        """读取多个列表页，返回 {分类: [文章URL...]}，聚焦最新并按日期倒序。"""
        grouped: dict[str, list[str]] = {}
        deadline = datetime.now() - timedelta(days=_KEEP_DAYS)
        today = datetime.now().strftime("%Y%m%d")
        # 首页由 CDN 负载均衡随机返回不同子集，多抓几次并合并，提高当天各分类覆盖
        today_categories: set[str] = set()
        for attempt in range(5):
            html = fetch_fresh_text(_LIST_PAGES[0])
            if not html:
                continue
            added = self._collect_page(html, _LIST_PAGES[0], deadline, grouped, today)
            for match in _ARTICLE_HREF.finditer(html):
                path = match.group("path")
                category = _PREFIX_CATEGORY.get(path.split("/")[1])
                date_match = re.search(r"/" + today + r"/", path)
                if category is not None and date_match:
                    today_categories.add(category)
            if len(today_categories) >= 3:
                break
            time.sleep(1)
        # 其余频道页补充一次即可
        for page in _LIST_PAGES[1:]:
            html = fetch_fresh_text(page)
            if html:
                self._collect_page(html, page, deadline, grouped, today)
        # 各分类内按 URL 日期倒序，确保当天稿先被轮询到
        def _date_key(url: str) -> str:
            date_match = re.search(r"/(20\d{6})/", url)
            return date_match.group(1) if date_match else "00000000"

        for category in grouped:
            grouped[category].sort(key=_date_key, reverse=True)
        return grouped

    def _parse_publish_time(self, url: str, html: str) -> datetime | None:
        """解析发布时间：优先详情页可见时间，其次 URL 中的日期。"""
        for match in _DATETIME_TEXT.finditer(html):
            text = match.group(0)
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(text, fmt)
                except ValueError:
                    continue
        # 回退：URL /YYYYMMDD/ 作为当天 0 点
        date_match = re.search(r"/(20\d{6})/", url)
        if date_match:
            try:
                return datetime.strptime(date_match.group(1), "%Y%m%d")
            except ValueError:
                return None
        return None

    def _build_article(self, url: str, category: str) -> RawArticle | None:
        """抓取并解析单篇新华网文章，失败或正文过短返回 None。"""
        html = fetch_text(url)
        if not html:
            return None
        paragraphs = extract_paragraphs(
            html, container_selectors=["div.main-left", "div.main", "div.content"]
        )
        content = "\n".join(paragraphs)
        if count_chinese(content) < _MIN_BODY_CHARS:
            return None

        title = extract_title(html, site_suffix="-新华网")
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
            source="新华网",
            source_url=url,
            publish_time=publish_time,
        )

    def fetch_articles(self) -> list[RawArticle]:
        """采集新华网新闻，各分类轮询取稿以覆盖不同栏目，克制抓取。"""
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
