"""采集 HTTP 请求工具。

统一模拟浏览器 UA、超时与失败处理，避免污染 base.py 的抽象接口。
"""

import httpx

# 固定浏览器标识，降低被误判为异常抓取的概率
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    # 请求最新列表时避免命中 CDN 缓存的旧快照
    "Cache-Control": "no-cache",
}

_client = httpx.Client(headers=_DEFAULT_HEADERS, timeout=15, follow_redirects=True)


def _site_referer(url: str) -> str | None:
    """生成与目标同源的 Referer，降低被新闻站点风控误判的概率。"""
    from urllib.parse import urlsplit

    parsed = urlsplit(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}/"
    return None


def fetch_text(url: str) -> str | None:
    """请求指定 URL 并返回 HTML 文本。

    返回 None 表示请求失败（超时、404、连接异常等），由调用方决定跳过该地址。
    请求失败时自动重试一次（新闻站点偶发连接重置）。
    """
    for attempt in range(2):
        try:
            headers = dict(_client.headers)
            referer = _site_referer(url)
            if referer:
                headers["Referer"] = referer
            response = _client.get(url, headers=headers)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError:
            return None
        except httpx.RequestError:
            if attempt == 1:
                return None
    return None


def fetch_json_text(url: str) -> str | None:
    """请求 JSON/JSONP 接口并返回原始文本。

    与 fetch_text 行为一致，仅保留语义以便阅读接口代码时区分用途。
    """
    return fetch_text(url)


def _cache_busted(url: str) -> str:
    """为 URL 追加时间戳参数，绕过 CDN 对列表页的陈旧缓存。"""
    import time

    separator = "&" if "?" in url else "?"
    return f"{url}{separator}_={int(time.time())}"


def fetch_fresh_text(url: str) -> str | None:
    """请求列表页并绕开 CDN 缓存，返回最新 HTML 文本。"""
    return fetch_text(_cache_busted(url))
