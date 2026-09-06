"""D6-01 Crawler 测试：提取、去噪、映射、去重四项覆盖。

全部用例不访问真实网络：列表页/详情页 HTML 由夹具内嵌，HTTP 函数经
monkeypatch 替换（§6 允许的模块隔离 Mock）；去重用 SQLite 内存库验证
NewsService 的 SHA-256 逻辑。日期一律由当前时间动态生成，避免用例随
真实日期漂移失效。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.crawlers.base import RawArticle
from app.crawlers.html_cleaner import (
    clean_web_text,
    count_chinese,
    extract_paragraphs,
    extract_title,
)
from app.crawlers.source_a import SourceA
from app.crawlers.source_b import SourceB
from app.exceptions import BusinessError
from app.models import NewsArticle
from app.news_categories import SIX_CATEGORIES, is_valid_category
from app.services.news_service import NewsService


# ---------- 夹具工具 ----------


def _today_compact() -> str:
    """当天日期（YYYYMMDD），用于新华网 URL 路径。"""
    return datetime.now().strftime("%Y%m%d")


def _today_dash() -> str:
    """当天日期（YYYY-MM-DD），用于光明网 URL 路径。"""
    return datetime.now().strftime("%Y-%m-%d")


def _days_ago_compact(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")


def _body_paragraph(marker: str) -> str:
    """生成一段超过 20 字符的正文段落（提取器会丢弃更短碎片）。"""
    return f"{marker}这是一段足够长的正文内容，用于通过网页级清洗的最小段落长度阈值校验。"


def _long_detail_body() -> str:
    """生成总汉字数超过 60 的正文段落列表，绕过来源的最短正文过滤。"""
    return "\n".join(_body_paragraph(f"段落{i}：") for i in range(3))


def _paragraphs_html() -> str:
    """把多段正文包成 <p> 序列，供详情页夹具复用。"""
    body = _long_detail_body().replace("\n", "</p>\n<p>")
    return f"<p>{body}</p>"


def _make_raw(title: str, content: str, category: str = "科技") -> RawArticle:
    """构造一条合法 RawArticle，供去重/校验用例使用。"""
    return RawArticle(
        title=title,
        content=content,
        category=category,
        source="测试来源",
        source_url=f"https://example.invalid/{title}",
        publish_time=datetime.now(),
    )


# ---------- 去噪：html_cleaner ----------


def test_extract_paragraphs_strips_block_noise() -> None:
    """无正文容器回退整页时，nav/aside/footer 等噪声块被整体移除。"""
    page = f"""
    <html><head><style>.x{{color:red}}</style></head><body>
    <nav><p>{'导航' * 15}</p></nav>
    <script>var tracking = 1;</script>
    <aside><p>{'侧栏' * 15}</p></aside>
    <p>{_body_paragraph("真实正文：")}</p>
    <footer><p>{'页脚' * 15}</p></footer>
    </body></html>
    """
    paragraphs = extract_paragraphs(page, container_selectors=["div.not-exist"])
    assert paragraphs == [_body_paragraph("真实正文：")]


def test_extract_paragraphs_uses_first_matching_container() -> None:
    """命中首个容器选择器：容器内正文保留，容器外内容不混入。"""
    page = f"""
    <html><body>
    <div class="ad"><p>{_body_paragraph("广告广告：")}</p></div>
    <div class="main-left">
      <p>{_body_paragraph("正文一：")}</p>
      <p>{_body_paragraph("正文二：")}</p>
    </div>
    </body></html>
    """
    paragraphs = extract_paragraphs(
        page, container_selectors=["div.main-left", "div.content"]
    )
    assert paragraphs == [_body_paragraph("正文一："), _body_paragraph("正文二：")]


def test_extract_paragraphs_drops_short_fragments() -> None:
    """不足 20 字的短段落（链接、碎片）不进入正文。"""
    page = f"""
    <html><body><div class="content">
      <p>短段落</p>
      <p>{_body_paragraph("达标段落：")}</p>
    </div></body></html>
    """
    paragraphs = extract_paragraphs(page, container_selectors=["div.content"])
    assert paragraphs == [_body_paragraph("达标段落：")]


def test_extract_paragraphs_drops_photo_captions_and_newspaper_line(
) -> None:
    """图注（新华社发/记者××摄/（…日摄））与报纸来源行被识别剔除。"""
    page = f"""
    <html><body><div class="content">
      <p>{_body_paragraph("真实正文：")}</p>
      <p>图为发射现场，火箭腾空而起十分壮观。新华社记者 李四 摄</p>
      <p>救援人员正在现场紧张作业（2026年9月5日摄）。这一幕令人动容。</p>
      <p>本文刊于《光明日报》（2026年09月05日 09版）</p>
    </div></body></html>
    """
    paragraphs = extract_paragraphs(page, container_selectors=["div.content"])
    assert paragraphs == [_body_paragraph("真实正文：")]


def test_extract_paragraphs_dedupes_identical_paragraphs() -> None:
    """非图注的完全相同段落重复出现（图集页常见）只保留首次出现。"""
    repeated = "图为比赛现场，运动员正在激烈拼抢，看台上观众呐喊助威，气氛十分热烈。"
    page = f"""
    <html><body><div class="content">
      <p>{_body_paragraph("导语：")}</p>
      <p>{repeated}</p>
      <p>{_body_paragraph("中段：")}</p>
      <p>{repeated}</p>
    </div></body></html>
    """
    paragraphs = extract_paragraphs(page, container_selectors=["div.content"])
    assert paragraphs.count(repeated) == 1
    assert len(paragraphs) == 3


def test_clean_web_text_and_count_chinese() -> None:
    """空白折叠、全角/nbsp 归一、首尾编辑残留标点剔除；汉字计数准确。"""
    # 尾部 "·" 紧跟文本时随首尾剥离一并去除
    assert clean_web_text("　你好\xa0 世界· ") == "你好 世界"
    assert count_chinese("abc 你好世界123") == 4


def test_extract_title_priority_and_suffix() -> None:
    """标题提取优先级 og:title > h1 > <title>，站点后缀与实体被正确处理。"""
    og_page = """
    <html><head><meta property="og:title" content="og标题-新华网"/></head>
    <body><h1>h1标题</h1><title>title标题</title></body></html>
    """
    assert extract_title(og_page, site_suffix="-新华网") == "og标题"

    h1_page = "<html><body><h1>h1标题-新华网</h1><title>title标题</title></body></html>"
    assert extract_title(h1_page, site_suffix="-新华网") == "h1标题"

    only_title = "<html><head><title>仅title可用-新华网</title></head></html>"
    assert extract_title(only_title, site_suffix="-新华网") == "仅title可用"

    entity_page = (
        '<html><head><meta property="og:title" content="&quot;引号&quot;标题"/></head></html>'
    )
    assert extract_title(entity_page) == '"引号"标题'


# ---------- 映射：URL 前缀/子域 → 六类 ----------


def test_source_a_collect_page_maps_prefix_to_six_categories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """新华网按频道前缀映射六类，未知前缀与超期旧稿不采集。"""
    monkeypatch.setattr("app.crawlers.source_a.time.sleep", lambda _s: None)
    today = _today_compact()
    page_url = "http://www.news.cn/"

    def link(prefix: str, date: str) -> str:
        return f'<a href="http://www.news.cn/{prefix}/{date}/{"a" * 32}/c.html">新闻</a>'

    html = (
        f"<html><body>"
        f"{link('politics', today)}{link('world', today)}{link('sports', today)}"
        f"{link('tech', today)}{link('fortune', today)}{link('legal', today)}"
        f"{link('culture', today)}"  # 未登记前缀，不采集
        f"{link('world', _days_ago_compact(30))}"  # 超期旧稿，不采集
        f"</body></html>"
    )

    source = SourceA(limit=5, request_interval=0.0)
    grouped: dict[str, list[str]] = {}
    source._collect_page(
        html, page_url, datetime.now() - timedelta(days=2), grouped, today
    )

    assert set(grouped.keys()) == {"国内", "国际", "体育", "科技", "财经", "社会"}
    all_urls = [url for urls in grouped.values() for url in urls]
    assert all("culture" not in url for url in all_urls)
    assert all(_days_ago_compact(30) not in url for url in all_urls)


def test_source_b_discover_maps_host_to_categories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """光明网按主机子域映射六类，未登记子域与超期旧稿不采集，URL 去重。"""
    monkeypatch.setattr("app.crawlers.source_b.time.sleep", lambda _s: None)
    # 光明网真实路径为 /YYYY-MM/DD/content_N.htm
    month_path = datetime.now().strftime("%Y-%m")
    day_path = datetime.now().strftime("%d")
    old_month = (datetime.now() - timedelta(days=30)).strftime("%Y-%m")

    def link(sub: str, month: str, day: str, n: int) -> str:
        return f'<a href="https://{sub}.gmw.cn/{month}/{day}/content_{n}.htm">新闻</a>'

    pages = {
        "https://www.gmw.cn/": (
            f"<html><body>{link('news', month_path, day_path, 1)}"
            f"{link('world', month_path, day_path, 2)}"
            f"{link('culture', month_path, day_path, 3)}</body></html>"  # 未登记
        ),
        "https://news.gmw.cn/": (
            f"<html><body>{link('news', month_path, day_path, 1)}"  # 与首页重复
            f"{link('economy', month_path, day_path, 4)}"
            f"{link('sports', month_path, day_path, 5)}"
            f"{link('news', old_month, day_path, 6)}</body></html>"  # 超期
        ),
        "https://tech.gmw.cn/": (
            f"<html><body>{link('tech', month_path, day_path, 7)}"
            f"{link('society', month_path, day_path, 8)}</body></html>"
        ),
    }
    monkeypatch.setattr(
        "app.crawlers.source_b.fetch_fresh_text", lambda url: pages.get(url)
    )

    grouped = SourceB(limit=5, request_interval=0.0)._discover_grouped()

    assert set(grouped.keys()) == {"国内", "国际", "财经", "体育", "科技", "社会"}
    assert grouped["国内"] == [f"https://news.gmw.cn/{month_path}/{day_path}/content_1.htm"]
    all_urls = [url for urls in grouped.values() for url in urls]
    assert all("culture" not in url for url in all_urls)
    assert all("content_6" not in url for url in all_urls)


def test_fixed_six_categories_contract() -> None:
    """系统固定六类顺序与 NewsService/API 契约一致，未知分类被拒。"""
    assert NewsService.list_categories() == SIX_CATEGORIES
    assert NewsService.list_categories() == ["科技", "财经", "社会", "体育", "国内", "国际"]
    assert is_valid_category("国内") and not is_valid_category("娱乐")


# ---------- 提取：两来源详情页 → RawArticle ----------


def test_source_a_build_article_parses_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """新华网详情页解析：标题去后缀、正文提取、发布时间来自页面文本。"""
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    url = f"http://www.news.cn/politics/{_today_compact()}/{'a' * 32}/c.html"
    detail = f"""
    <html><head><meta property="og:title" content="瑞金延安高铁直达-新华网"/></head>
    <body><div class="main-left">
      <span class="pub-time">{now_text}</span>
      {_paragraphs_html()}
    </div></body></html>
    """
    monkeypatch.setattr("app.crawlers.source_a.fetch_text", lambda _u: detail)

    article = SourceA(limit=1, request_interval=0.0)._build_article(url, "国内")

    assert article is not None
    assert isinstance(article, RawArticle)
    assert article.title == "瑞金延安高铁直达"
    assert article.source == "新华网"
    assert article.category == "国内"
    assert article.source_url == url
    assert article.publish_time is not None
    assert count_chinese(article.content) >= 60


def test_source_a_rejects_short_body_and_old_news(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正文不足 60 汉字或发布超过 3 天的文章返回 None，不入采集结果。"""
    url = f"http://www.news.cn/world/{_today_compact()}/{'b' * 32}/c.html"
    short_body = """
    <html><head><meta property="og:title" content="短文"/></head>
    <body><div class="main-left"><p>太短的正文</p></div></body></html>
    """
    old_body = f"""
    <html><head><meta property="og:title" content="旧稿"/></head>
    <body><div class="main-left">
      <span>30 天前发布：{(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")}</span>
      {_paragraphs_html()}
    </div></body></html>
    """
    source = SourceA(limit=1, request_interval=0.0)
    monkeypatch.setattr("app.crawlers.source_a.fetch_text", lambda _u: short_body)
    assert source._build_article(url, "国际") is None
    monkeypatch.setattr("app.crawlers.source_a.fetch_text", lambda _u: old_body)
    assert source._build_article(url, "国际") is None


def test_source_b_build_article_parses_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """光明网详情页解析：<title> 取标题并去站点后缀，正文来自正文容器。"""
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M")
    url = (
        f"https://tech.gmw.cn/{datetime.now().strftime('%Y-%m')}/"
        f"{datetime.now().strftime('%d')}/content_100.htm"
    )
    detail = f"""
    <html><head><title>固态电池观察 _光明网</title></head>
    <body><div id="article_inbox">
      <span>{now_text}</span>
      {_paragraphs_html()}
    </div></body></html>
    """
    monkeypatch.setattr("app.crawlers.source_b.fetch_text", lambda _u: detail)

    article = SourceB(limit=1, request_interval=0.0)._build_article(url, "科技")

    assert article is not None
    assert article.title == "固态电池观察"
    assert article.source == "光明网"
    assert article.publish_time is not None


def test_source_b_rejects_nav_title_and_falls_back_to_url_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """导航聚合页标题直接拒绝；页面无时间时回退 URL 日期作为发布时间。"""
    url = (
        f"https://news.gmw.cn/{datetime.now().strftime('%Y-%m')}/"
        f"{datetime.now().strftime('%d')}/content_200.htm"
    )
    nav_page = f"""
    <html><head><title>全部导航</title></head>
    <body><div id="article_inbox">{_paragraphs_html()}</div></body></html>
    """
    no_time_page = f"""
    <html><head><title>无时间戳稿件</title></head>
    <body><div id="article_inbox">{_paragraphs_html()}</div></body></html>
    """
    source = SourceB(limit=1, request_interval=0.0)
    monkeypatch.setattr("app.crawlers.source_b.fetch_text", lambda _u: nav_page)
    assert source._build_article(url, "国内") is None

    monkeypatch.setattr("app.crawlers.source_b.fetch_text", lambda _u: no_time_page)
    article = source._build_article(url, "国内")
    assert article is not None
    assert article.publish_time == datetime.strptime(_today_dash(), "%Y-%m-%d")


def test_raw_article_structure_uniform_between_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D3-01/02 契约：两来源输出 RawArticle 的字段结构完全相同。"""
    expected_fields = {"title", "content", "category", "source", "source_url", "publish_time"}
    a_page = f"""
    <html><head><meta property="og:title" content="结构对照"/></head>
    <body><div class="main-left">{_paragraphs_html()}</div></body></html>
    """
    b_page = f"""
    <html><head><title>结构对照</title></head>
    <body><div id="article_inbox">{_paragraphs_html()}</div></body></html>
    """
    monkeypatch.setattr("app.crawlers.source_a.fetch_text", lambda _u: a_page)
    monkeypatch.setattr("app.crawlers.source_b.fetch_text", lambda _u: b_page)

    article_a = SourceA(limit=1, request_interval=0.0)._build_article(
        f"http://www.news.cn/politics/{_today_compact()}/{'c' * 32}/c.html", "国内"
    )
    article_b = SourceB(limit=1, request_interval=0.0)._build_article(
        f"https://news.gmw.cn/{datetime.now().strftime('%Y-%m')}/"
        f"{datetime.now().strftime('%d')}/content_300.htm", "国内"
    )
    assert article_a is not None and article_b is not None
    assert set(RawArticle.__dataclass_fields__.keys()) == expected_fields
    assert set(article_a.__dict__.keys()) == expected_fields
    assert set(article_b.__dict__.keys()) == expected_fields


def test_source_a_fetch_articles_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """端到端（离线）：列表发现 → 分类轮询 → 详情提取，limit 生效。"""
    monkeypatch.setattr("app.crawlers.source_a.time.sleep", lambda _s: None)
    today = _today_compact()

    def link(prefix: str, n: int) -> str:
        # 31 个 d + 序号 n，凑成 32 位十六进制哈希，符合详情页 URL 正则
        return f'<a href="http://www.news.cn/{prefix}/{today}/{"d" * 31}{n}/c.html">x</a>'

    homepage = (
        f"<html><body>{link('politics', 1)}{link('world', 1)}{link('sports', 1)}"
        f"{link('tech', 1)}{link('fortune', 1)}</body></html>"
    )
    detail = f"""
    <html><head><meta property="og:title" content="轮询稿件-新华网"/></head>
    <body><div class="main-left">
      <span>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</span>
      {_paragraphs_html()}
    </div></body></html>
    """
    monkeypatch.setattr("app.crawlers.source_a.fetch_fresh_text", lambda _u: homepage)
    monkeypatch.setattr("app.crawlers.source_a.fetch_text", lambda _u: detail)

    articles = SourceA(limit=3, request_interval=0.0).fetch_articles()

    assert len(articles) == 3
    assert all(a.source == "新华网" and a.title == "轮询稿件" for a in articles)
    assert {a.category for a in articles} <= set(SIX_CATEGORIES)
    # 各分类轮询取稿：三篇来自三个不同分类
    assert len({a.category for a in articles}) == 3


# ---------- 去重：NewsService SHA-256 ----------


def test_save_article_dedups_by_content_hash(db_session: Session) -> None:
    """相同内容再次入库返回既有记录且 created=False，不产生重复行。"""
    first, created_first = NewsService.save_article(
        db_session, _make_raw("标题甲", "完全相同的正文内容")
    )
    second, created_second = NewsService.save_article(
        db_session, _make_raw("标题乙", "完全相同的正文内容")
    )
    assert created_first is True
    assert created_second is False
    assert first.id == second.id
    assert second.title == "标题甲"  # 返回的是已存在的首条记录


def test_save_article_same_title_different_content_creates_new(
    db_session: Session,
) -> None:
    """SHA-256 按正文判重：标题相同但正文不同视为新文章。"""
    first, created_first = NewsService.save_article(
        db_session, _make_raw("同题", "正文版本一的内容")
    )
    second, created_second = NewsService.save_article(
        db_session, _make_raw("同题", "正文版本二的内容")
    )
    assert created_first and created_second
    assert first.id != second.id


def test_save_article_rejects_invalid_category_and_empty_fields(
    db_session: Session,
) -> None:
    """六类之外的分类、空标题/正文/来源 URL 被校验拒绝。"""
    blank_url = RawArticle(
        title="标题", content="正文", category="国内",
        source="来源", source_url="   ", publish_time=None,
    )
    with pytest.raises(BusinessError):
        NewsService.save_article(db_session, _make_raw("标题", "正文", category="娱乐"))
    with pytest.raises(BusinessError):
        NewsService.save_article(db_session, _make_raw("  ", "正文"))
    with pytest.raises(BusinessError):
        NewsService.save_article(db_session, _make_raw("标题", "  "))
    with pytest.raises(BusinessError):
        NewsService.save_article(db_session, blank_url)


def test_saved_article_lands_as_pending(db_session: Session) -> None:
    """入库记录写入职责字段：初始状态 pending，无摘要信息。"""
    article, created = NewsService.save_article(
        db_session, _make_raw("待摘要", "入库后的初始正文")
    )
    assert created
    row = db_session.get(NewsArticle, article.id)
    assert row is not None
    assert row.summary_status == "pending"
    assert row.summary is None and row.summary_error is None
    assert row.content_hash == NewsService.content_sha256("入库后的初始正文")
