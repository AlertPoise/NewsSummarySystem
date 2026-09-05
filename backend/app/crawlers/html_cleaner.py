"""网页级正文提取与噪声清理工具。

职责边界：仅处理网页 DOM 结构噪声（导航、脚本、广告、非正文容器），
输出干净的正文段落列表。中文分句、控制字符规范化属于 C 的 NLP 清洗范围，
本模块不实现分词、分句或语义处理。
"""

from __future__ import annotations

import html
import re

from bs4 import BeautifulSoup, Tag

# 正文段落常见的最小字数阈值，用于排除短链接、无意义碎片
_MIN_PARAGRAPH_CHARS = 20


def _strip_block_noise(soup: BeautifulSoup) -> None:
    """原地移除对正文无意义的内容块。"""
    for selector in (
        "script",
        "style",
        "noscript",
        "iframe",
        "nav",
        "aside",
        "form",
        "footer",
    ):
        for node in soup.find_all(selector):
            node.decompose()
    # 去除页面注释与 svg 等
    for node in soup.find_all(["svg", "comment"]):
        node.decompose()


def extract_paragraphs(html: str, container_selectors: list[str]) -> list[str]:
    """从 HTML 中按候选容器提取正文段落。

    依次尝试容器选择器，取首个能定位到的容器；再从容器内收集足够长的 <p> 文本。
    返回按文档顺序排列的、已去除首尾空白的段落列表（不含 HTML 标签）。
    """
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    _strip_block_noise(soup)

    container: Tag | None = None
    for selector in container_selectors:
        container = soup.select_one(selector)
        if container is not None:
            break
    if container is None:
        container = soup

    paragraphs: list[str] = []
    for paragraph in container.find_all("p"):
        text = clean_web_text(paragraph.get_text(" ", strip=True))
        if len(text) >= _MIN_PARAGRAPH_CHARS:
            paragraphs.append(text)
    return _dedupe_consecutive(paragraphs)


def _dedupe_consecutive(paragraphs: list[str]) -> list[str]:
    """去掉连续重复的段落（新闻图集每张配图会重复同一句导语）。

    仅折叠相邻完全相同的段落，保留正文语序与语义；不处理语义级重复。
    """
    result: list[str] = []
    for text in paragraphs:
        if not result or text != result[-1]:
            result.append(text)
    return result


def clean_web_text(text: str) -> str:
    """网页级文本清理：折叠空白、剔除无意义字符，不改变句子结构。"""
    text = text.replace("　", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    # 去掉首尾常见编辑残留标点与空白
    return text.strip().strip("·:")


def count_chinese(text: str) -> int:
    """统计文本中的汉字数量，用于判断正文是否过短。"""
    return len(re.findall(r"[一-鿿]", text))


def extract_title(html_text: str, site_suffix: str = "") -> str:
    """从 HTML 提取文章标题，剥离内嵌标签与 HTML 实体。

    优先取 og:title，其次页面内 <h1>，最后回退 <title>；site_suffix 为站点后缀，
    命中时从标题末尾去除（如“-新华网”）。
    """
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "lxml")
    title = ""
    og = soup.find("meta", attrs={"property": "og:title"}) or soup.find("meta", attrs={"name": "og:title"})
    if og and og.get("content"):
        title = og["content"]
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(" ", strip=True)
    if not title:
        h2 = soup.find("h2")
        if h2:
            title = h2.get_text(" ", strip=True)
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)
    title = html.unescape(title)
    if site_suffix and title.endswith(site_suffix):
        title = title[: -len(site_suffix)]
    return clean_web_text(title)
