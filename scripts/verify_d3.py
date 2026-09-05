"""D3-01～D3-10 阶段验收脚本（D 维护，对应 docs/DEVELOPMENT_PLAN.md 阶段3 D 任务）。

覆盖范围：
- D3-01/02  新华网/光明网真实新闻源采集 -> RawArticle（真实网络请求）
- D3-03/04  网页正文提取与网页级清洗（离线构造页面断言）
- D3-05     来源分类到系统六类的严格映射
- D3-06     SHA-256 内容去重（重复入库幂等）
- D3-07     新闻入库（pending 状态与职责字段写入）
- D3-08/09/10  分类查询/分页查询/详情查询（Service + REST API 契约）

用法（仓库根目录）：
    backend\\.venv\\Scripts\\python.exe scripts\\verify_d3.py [--limit 3] [--skip-crawl] [--skip-db] [--mysqld 路径]

前置条件：
- backend/.env 已由 scripts/init_database.ps1 生成
- MySQL 未运行时脚本会尝试自动启动（先试 Windows 服务，再在常见目录搜索 mysqld.exe；
  也可用 --mysqld 显式指定本机 mysqld.exe 路径）；搜索不到时给出修复提示
- 本机可访问 www.news.cn 与 www.gmw.cn

规则：入库只使用真实采集到的新闻，不虚构新闻；重复执行幂等（SHA-256 去重兜底）。
退出码：0 = 无 FAIL（SKIP 视为通过）；1 = 存在 FAIL。
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import socket
import string
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

# 让脚本可以直接引用 backend/app 包（无需安装为依赖）
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

try:  # Windows 控制台中文输出保障
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.crawlers.base import RawArticle  # noqa: E402
from app.crawlers.html_cleaner import (  # noqa: E402
    clean_web_text,
    count_chinese,
    extract_paragraphs,
    extract_title,
)
from app.crawlers.source_a import SourceA, _PREFIX_CATEGORY  # noqa: E402
from app.crawlers.source_b import SourceB, _HOST_CATEGORY  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.exceptions import BusinessError  # noqa: E402
from app.models import NewsArticle  # noqa: E402
from app.news_categories import SIX_CATEGORIES  # noqa: E402
from app.services.news_service import NewsService  # noqa: E402

# API 契约字段（docs/API.md §5/§6）：列表禁止返回 content
_LIST_FIELDS = {"id", "title", "summary", "category", "source", "publish_time", "summary_status"}
_DETAIL_FIELDS = {
    "id", "title", "content", "summary", "category", "source", "source_url",
    "publish_time", "summary_status", "summary_time_ms", "is_favorite", "feedback",
}

# 正文残留 HTML 标签特征（新闻正文允许出现“<”数学符号，故只匹配常见标签）
_TAG_PATTERN = re.compile(r"</?(?:p|div|span|a|img|script|style|br|table|tbody|h[1-6])\b", re.IGNORECASE)

_TASK_NAMES = {
    "D3-01": "新华网真实新闻源采集",
    "D3-02": "光明网真实新闻源采集",
    "D3-03": "网页正文提取",
    "D3-04": "网页级清洗",
    "D3-05": "严格六分类映射",
    "D3-06": "SHA-256 内容去重",
    "D3-07": "新闻入库",
    "D3-08": "固定六分类查询",
    "D3-09": "新闻分页查询",
    "D3-10": "新闻详情查询",
}

# 阶段3 D 任务的执行顺序（用于汇总表）
_TASK_ORDER = [f"D3-{i:02d}" for i in range(1, 11)]


class Results:
    """记录各检查项结果并支持按任务号汇总。"""

    def __init__(self) -> None:
        self.entries: list[tuple[str, str, str]] = []  # (任务号, 状态, 说明)

    def add(self, task: str, status: str, message: str) -> None:
        self.entries.append((task, status, message))
        print(f"[{status}] {task} {message}", flush=True)

    def pass_(self, task: str, message: str) -> None:
        self.add(task, "PASS", message)

    def fail(self, task: str, message: str) -> None:
        self.add(task, "FAIL", message)

    def skip(self, task: str, message: str) -> None:
        self.add(task, "SKIP", message)

    def task_status(self, task: str) -> str:
        states = [s for t, s, _ in self.entries if t == task]
        if not states:
            return "SKIP"
        if "FAIL" in states:
            return "FAIL"
        if "PASS" in states:
            return "PASS"
        return "SKIP"


def check(message_ok: str, task: str, ok: bool, fail_message: str, results: Results) -> bool:
    """断言辅助：成功/失败各打印一行，返回布尔值便于串联。"""
    if ok:
        results.pass_(task, message_ok)
    else:
        results.fail(task, fail_message)
    return ok


# ---------------------------------------------------------------------------
# 阶段 1：D3-03/04 网页正文提取与网页级清洗（离线构造页面，不依赖网络/数据库）
# ---------------------------------------------------------------------------

_SAMPLE_HTML = """<html><head>
<title>测试新闻页面标题-新华网</title>
<meta property="og:title" content="全国科技创新大会在京开幕-新华网">
<script>var SCRIPT_NOISE = 1;</script>
<style>.STYLE_NOISE { color: red; }</style>
</head><body>
<nav>网站导航 首页 要闻 国际</nav>
<div class="main-left">
  <h1>页面H1标题</h1>
  <p>全国科技创新大会今日在北京隆重开幕，来自各领域的上千名代表齐聚一堂，共同探讨人工智能时代的发展机遇与挑战。</p>
  <p>点击进入专题</p>
  <p>与会代表在会场外合影留念。新华社发</p>
  <p>图为发射现场。记者李明摄</p>
  <p>《光明日报》（2026年09月05日 09版）</p>
  <p>全国科技创新大会今日在北京隆重开幕，来自各领域的上千名代表齐聚一堂，共同探讨人工智能时代的发展机遇与挑战。</p>
  <p>大会发布了年度科技进展报告，多位院士围绕基础研究与产业转化作了主题报告，现场交流气氛热烈。</p>
</div>
<footer>ICP备案号 FOOTER_NOISE</footer>
</body></html>"""

# 两个真实正文段落是页面里仅应保留的内容
_EXPECTED_PARAGRAPHS = [
    "全国科技创新大会今日在北京隆重开幕，来自各领域的上千名代表齐聚一堂，共同探讨人工智能时代的发展机遇与挑战。",
    "大会发布了年度科技进展报告，多位院士围绕基础研究与产业转化作了主题报告，现场交流气氛热烈。",
]


def stage_cleaner(results: Results) -> None:
    """D3-03/04：正文容器提取、噪声剔除、图注/报纸来源行过滤、去重与标题提取。"""
    try:
        paragraphs = extract_paragraphs(_SAMPLE_HTML, container_selectors=["div.main-left"])

        check(
            "正文提取：噪声块剔除、短碎过滤、图注与报纸来源行过滤、整段去重",
            "D3-03",
            paragraphs == _EXPECTED_PARAGRAPHS,
            f"段落提取结果不符：实际={paragraphs}",
            results,
        )

        title = extract_title(_SAMPLE_HTML, site_suffix="-新华网")
        check(
            "标题提取：og:title 优先并剥离站点后缀",
            "D3-03",
            title == "全国科技创新大会在京开幕",
            f"标题提取结果不符：实际={title!r}",
            results,
        )

        text = clean_web_text("　全息\xa0 报道　")
        text2 = clean_web_text("·今日要点· ")
        check(
            "网页清洗：全角/不间断空白折叠与首尾残留标点剔除",
            "D3-04",
            text == "全息 报道" and text2 == "今日要点",
            f"clean_web_text 结果不符：实际={text!r}, {text2!r}",
            results,
        )

        check(
            "网页清洗：汉字计数（count_chinese）",
            "D3-04",
            count_chinese("你好世界") == 4 and count_chinese("abc123") == 0,
            "count_chinese 计数错误",
            results,
        )

        joined = "\n".join(paragraphs)
        noise_free = all(
            marker not in joined and marker not in title
            for marker in ("SCRIPT_NOISE", "STYLE_NOISE", "网站导航", "FOOTER_NOISE", "<p", "</")
        )
        check(
            "网页清洗：脚本/样式/导航/页脚噪声不进入正文",
            "D3-04",
            noise_free,
            "正文混入了脚本/样式/导航/页脚噪声",
            results,
        )
    except Exception:
        results.fail("D3-03", f"执行异常：{traceback.format_exc(limit=3)}")
        results.fail("D3-04", "同上，见 D3-03 异常")


# ---------------------------------------------------------------------------
# 阶段 2：D3-01/02 真实新闻源采集
# ---------------------------------------------------------------------------

def _same_site(url: str, domain: str) -> bool:
    """判断 URL 主机是否属于指定域名（允许 www 等子域）。"""
    host = urlsplit(url).netloc.lower().split(":")[0]
    return host == domain or host.endswith("." + domain)


def _validate_articles(
    task: str, source_name: str, domain: str, articles: list[RawArticle], results: Results
) -> None:
    """按 RawArticle 契约与入库约束逐篇校验采集结果，失败信息定位到具体 URL。"""
    if not articles:
        results.fail(task, f"{source_name}未采集到任何文章（网络异常或站点改版，可重试）")
        return
    results.pass_(task, f"采集到 {len(articles)} 篇真实文章")

    problems: list[str] = []
    now = datetime.now()
    for art in articles:
        url = art.source_url
        if not art.title.strip():
            problems.append(f"{url}: 标题为空")
        if len(art.title) > 255:
            problems.append(f"{url}: 标题超长（{len(art.title)} > 255，超出数据库列宽）")
        if len(art.source_url) > 1024:
            problems.append(f"{url}: source_url 超长（{len(art.source_url)} > 1024）")
        if count_chinese(art.content) < 60:
            problems.append(f"{url}: 正文过短（汉字 {count_chinese(art.content)} < 60）")
        if _TAG_PATTERN.search(art.content):
            problems.append(f"{url}: 正文残留 HTML 标签")
        if art.category not in SIX_CATEGORIES:
            problems.append(f"{url}: 分类 {art.category!r} 不在系统六类内")
        if art.source != source_name:
            problems.append(f"{url}: 来源标识 {art.source!r} != {source_name!r}")
        if not _same_site(url, domain):
            problems.append(f"{url}: 非本站 URL")
        if art.publish_time is not None and not (
            now - timedelta(days=4) <= art.publish_time <= now + timedelta(days=1)
        ):
            problems.append(f"{url}: 发布时间异常 {art.publish_time}")
    if problems:
        results.fail(task, f"{len(problems)} 项字段校验失败：" + "；".join(problems[:3]))
    else:
        results.pass_(task, f"{len(articles)} 篇文章标题/正文/分类/来源/时间字段全部合规")

    urls = [a.source_url for a in articles]
    check(
        f"{source_name}：同批采集结果 URL 无重复",
        task,
        len(urls) == len(set(urls)),
        "同批采集出现重复 URL",
        results,
    )


def stage_crawl(results: Results, limit: int, interval: float) -> list[RawArticle]:
    """D3-01/02：真实网络采集两个新闻源，返回用于后续入库校验的样本。"""
    articles: list[RawArticle] = []
    for task, source_name, cls, domain in (
        ("D3-01", "新华网", SourceA, "news.cn"),
        ("D3-02", "光明网", SourceB, "gmw.cn"),
    ):
        try:
            print(f"[....] {task} 正在真实采集{source_name}（limit={limit}，约需 20~60 秒）...", flush=True)
            started = time.perf_counter()
            fetched = cls(limit=limit, request_interval=interval).fetch_articles()
            elapsed = time.perf_counter() - started
            articles.extend(fetched)
            results.pass_(task, f"采集完成：{len(fetched)} 篇，耗时 {elapsed:.1f} 秒")
            _validate_articles(task, source_name, domain, fetched, results)
        except Exception:
            results.fail(task, f"执行异常：{traceback.format_exc(limit=3)}")
    return articles


# ---------------------------------------------------------------------------
# 阶段 3：D3-05 分类映射
# ---------------------------------------------------------------------------

def stage_mapping(results: Results, articles: list[RawArticle]) -> None:
    """D3-05：映射表只指向系统六类；真实采集样本的分类全部合法。"""
    try:
        check(
            "系统六类常量恰好 6 类且无重复",
            "D3-05",
            len(SIX_CATEGORIES) == 6 and len(set(SIX_CATEGORIES)) == 6,
            f"SIX_CATEGORIES 定义异常：{SIX_CATEGORIES}",
            results,
        )
        mapping_ok = set(_PREFIX_CATEGORY.values()) <= set(SIX_CATEGORIES) and set(
            _HOST_CATEGORY.values()
        ) <= set(SIX_CATEGORIES)
        check(
            "来源分类映射表（新华网前缀/光明网子域）仅指向系统六类",
            "D3-05",
            mapping_ok,
            f"映射表存在六类之外取值："
            f"{set(_PREFIX_CATEGORY.values()) | set(_HOST_CATEGORY.values()) - set(SIX_CATEGORIES)}",
            results,
        )
        if articles:
            bad = [a.source_url for a in articles if a.category not in SIX_CATEGORIES]
            check(
                f"真实采集样本（{len(articles)} 篇）分类全部为系统六类",
                "D3-05",
                not bad,
                f"存在非法分类样本：{bad[:3]}",
                results,
            )
        else:
            results.skip("D3-05", "无采集样本，跳过真实样本分类校验")
    except Exception:
        results.fail("D3-05", f"执行异常：{traceback.format_exc(limit=3)}")


# ---------------------------------------------------------------------------
# MySQL 预检与自动启动（可移植：不硬编码任何机器的安装路径）
# ---------------------------------------------------------------------------

_SERVICE_WAIT_SECONDS = 20   # 启动 Windows 服务后等待端口就绪的时间
_MYSQLD_WAIT_SECONDS = 40    # 直接启动 mysqld 后等待端口就绪的时间


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """探测 host:port 能否建立 TCP 连接，用于判断 MySQL 是否已在运行。"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _wait_port(host: str, port: int, seconds: int) -> bool:
    """在 seconds 内轮询等待端口就绪。"""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if _port_open(host, port, timeout=0.8):
            return True
        time.sleep(1.0)
    return False


def _mysql_service_names() -> list[str]:
    """枚举 Windows 系统服务中名称含 mysql 的服务（服务名因机器而异，动态发现）。"""
    if os.name != "nt":
        return []
    try:
        proc = subprocess.run(["sc", "query", "state=", "all"], capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return []
    names: list[str] = []
    for line in proc.stdout.decode("utf-8", errors="ignore").splitlines():
        line = line.strip()
        # 服务名本身是 ASCII，中文系统下其余字节可能乱码但不影响解析
        if line.upper().startswith("SERVICE_NAME:") and "mysql" in line.lower():
            names.append(line.split(":", 1)[1].strip())
    return names


def _try_start_service(name: str) -> bool:
    """尝试 net start 启动一个 Windows 服务；无权限等失败时由调用方继续兜底。"""
    try:
        proc = subprocess.run(["net", "start", name], capture_output=True, timeout=90)
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _candidate_mysqld() -> list[Path]:
    """在各盘符的常见安装布局中搜索 mysqld.exe（不硬编码特定机器路径）。

    覆盖 PATH 中的 mysqld、各盘 mysql* 便携版目录、Program Files/MySQL、
    xampp 等常见位置；返回去重后的候选列表，顺序即尝试顺序。
    """
    cands: list[Path] = []
    found = shutil.which("mysqld")
    if found:
        cands.append(Path(found))
    drives = [Path(f"{letter}:/") for letter in string.ascii_uppercase if Path(f"{letter}:/").exists()]
    patterns = [
        "mysql*/bin/mysqld.exe",
        "mysql*/mysql*/bin/mysqld.exe",
        "Program Files/MySQL/*/bin/mysqld.exe",
        "Program Files (x86)/MySQL/*/bin/mysqld.exe",
        "xampp/mysql/bin/mysqld.exe",
    ]
    for drive in drives:
        for pattern in patterns:
            try:
                cands.extend(drive.glob(pattern))
            except OSError:
                continue
    unique: list[Path] = []
    for cand in cands:
        try:
            resolved = cand.resolve()
        except OSError:
            continue
        if resolved not in unique:
            unique.append(resolved)
    return unique


def _find_defaults_file(mysqld: Path) -> Path | None:
    """从 mysqld.exe 所在目录向上逐层查找 my.ini/my.cnf（便携版与安装版通用）。"""
    bases = [mysqld.parent, mysqld.parent.parent, mysqld.parent.parent.parent]
    for base in bases:
        for name in ("my.ini", "my.cnf"):
            candidate = base / name
            if candidate.exists():
                return candidate
    return None


def _launch_mysqld(mysqld: Path, defaults_file: Path | None) -> int | None:
    """以分离进程启动 mysqld（脚本退出后继续运行），返回 PID；启动失败返回 None。

    mysqld 的控制台输出重定向到 runtime/logs/mysqld_autostart.log 便于排查。
    """
    log_dir = REPO_ROOT / "runtime" / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    cmd = [str(mysqld)]
    if defaults_file is not None:
        cmd.append(f"--defaults-file={defaults_file}")
    cmd.append("--console")
    creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
    )
    try:
        with open(log_dir / "mysqld_autostart.log", "ab") as log:
            proc = subprocess.Popen(
                cmd,
                stdout=log,
                stderr=log,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags,
                start_new_session=(os.name != "nt"),
                cwd=str(defaults_file.parent) if defaults_file is not None else None,
            )
        return proc.pid
    except OSError:
        return None


def ensure_mysql(results: Results, host: str, port: int, mysqld_hint: str | None) -> None:
    """数据库检查前的 MySQL 预检：未运行时按「系统服务 -> mysqld.exe」顺序自动启动。

    - 已在运行则直接跳过；
    - 远程数据库（host 非本机）不做自动启动；
    - 自动启动失败只打印提示，由后续数据库检查给出 FAIL 详情。
    """
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"[信息] 数据库为远程实例（{host}:{port}），不做本机自动启动。", flush=True)
        return
    if _port_open(host, port):
        print(f"[信息] MySQL 已在运行（{host}:{port}）。", flush=True)
        return

    print(f"[信息] MySQL（{host}:{port}）未运行，尝试自动启动...", flush=True)

    # 1) Windows 服务（安装版最常见；无管理员权限时 net start 会失败，继续兜底）
    for name in _mysql_service_names():
        print(f"[信息] 尝试启动 Windows 服务 {name} ...", flush=True)
        if _try_start_service(name) and _wait_port(host, port, _SERVICE_WAIT_SECONDS):
            print(f"[信息] MySQL 服务 {name} 已启动并就绪。", flush=True)
            return

    # 2) mysqld.exe：--mysqld 显式指定优先（允许无 my.ini，责任在调用者），其次自动搜索
    explicit = Path(mysqld_hint) if mysqld_hint else None
    attempts: list[tuple[Path, bool]] = []
    if explicit is not None:
        attempts.append((explicit, True))
    attempts.extend((cand, False) for cand in _candidate_mysqld())

    tried: list[str] = []
    for mysqld, allow_missing_ini in attempts[:4]:
        defaults = _find_defaults_file(mysqld)
        if defaults is None and not allow_missing_ini:
            tried.append(f"{mysqld}（未找到 my.ini，跳过）")
            continue
        tried.append(f"{mysqld}（配置 {defaults.name if defaults else '无，按默认配置'}）")
        print(f"[信息] 启动 mysqld：{mysqld} ...", flush=True)
        pid = _launch_mysqld(mysqld, defaults)
        if pid is not None and _wait_port(host, port, _MYSQLD_WAIT_SECONDS):
            print(
                f"[信息] MySQL 已自动启动（pid={pid}），"
                "控制台日志见 runtime/logs/mysqld_autostart.log；如需停止可用 mysqladmin shutdown。",
                flush=True,
            )
            return

    print("[信息] 自动启动未成功。已尝试：" + ("；".join(tried) if tried else "（未发现 MySQL 服务或 mysqld.exe）"), flush=True)
    print("[信息] 请手动启动 MySQL 后重跑，或用 --mysqld 指定 mysqld.exe 完整路径；"
          "服务方式启动失败时通常需要以管理员身份运行终端。", flush=True)


# ---------------------------------------------------------------------------
# 阶段 4：D3-06/07 SHA-256 去重与入库
# ---------------------------------------------------------------------------

def _pick_sample(articles: list[RawArticle], db: Session) -> RawArticle | None:
    """优先使用本次真实采集样本；--skip-crawl 时回退为库内最新一条真实新闻。"""
    for art in articles:
        if len(art.title) <= 255:
            return art
    row = db.scalar(select(NewsArticle).order_by(NewsArticle.id.desc()).limit(1))
    if row is None:
        return None
    return RawArticle(
        title=row.title,
        content=row.content,
        category=row.category,
        source=row.source,
        source_url=row.source_url,
        publish_time=row.publish_time,
    )


def _open_db() -> tuple[Session | None, str | None]:
    """打开数据库会话并探测连通性；失败时返回修复提示。"""
    try:
        db = SessionLocal()
        db.scalar(select(func.count()).select_from(NewsArticle))
        return db, None
    except Exception as exc:
        hint = (
            "MySQL 不可用或 news_summary 库未初始化 —— 启动前自动拉起未成功（见上方 [信息] 行），"
            "请手动启动 MySQL 并确认已执行 scripts/init_database.ps1 建库；详细信息："
            f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}"
        )
        return None, hint


def stage_database(results: Results, articles: list[RawArticle], use_db: bool) -> tuple[Session | None, str | None]:
    """D3-06/07：哈希算法一致性、重复入库幂等、入库字段与六类校验拒绝。

    返回 (数据库会话或 None, 失败提示或 None)；会话为 None 且提示为 None 表示用户主动跳过。
    """
    if use_db:
        db, error = _open_db()
    else:
        db, error = None, "按要求跳过数据库检查（--skip-db）"
    if db is None:
        for task in ("D3-06", "D3-07"):
            if use_db:
                results.fail(task, error or "数据库不可用")
            else:
                results.skip(task, error or "数据库不可用")
        return None, error

    try:
        sample = _pick_sample(articles, db)
        if sample is None:
            results.skip("D3-06", "无可用真实新闻样本（未采集且库为空），跳过去重校验")
            results.skip("D3-07", "无可用真实新闻样本（未采集且库为空），跳过入库校验")
            return db, None

        # D3-06：与 hashlib 直接对照，保证去重键算法正确
        expected_hash = hashlib.sha256(sample.content.encode("utf-8")).hexdigest()
        check(
            "content_sha256 与标准 hashlib SHA-256 一致",
            "D3-06",
            NewsService.content_sha256(sample.content) == expected_hash,
            "NewsService.content_sha256 与 hashlib 结果不一致",
            results,
        )

        # D3-07：首次入库（或此前运行已入库时按幂等返回已有记录）
        first, created = NewsService.save_article(db, sample)
        results.pass_(
            "D3-07",
            f"入库成功：id={first.id}（{'新写入' if created else '此前运行已入库，幂等返回已有记录'}）",
        )

        # D3-06：同一内容重复入库必须返回同一条记录且不产生重复行
        second, created_again = NewsService.save_article(db, sample)
        hash_count = (
            db.scalar(
                select(func.count()).select_from(NewsArticle).where(
                    NewsArticle.content_hash == expected_hash
                )
            )
            or 0
        )
        check(
            "重复入库幂等：同内容两次保存返回同一 id，库内该哈希仅 1 行",
            "D3-06",
            second.id == first.id and created_again is False and hash_count == 1,
            f"去重失败：first_id={first.id}, second_id={second.id}, "
            f"再次created={created_again}, 该哈希行数={hash_count}",
            results,
        )

        # D3-07：落库字段与职责要求（内容字段全部落库；pending/空摘要仅约束本次新写入）
        row = db.get(NewsArticle, first.id)
        if row is None:
            results.fail("D3-07", f"入库记录读回失败：id={first.id}")
            return db, None
        structural_ok = (
            row.title == sample.title
            and row.content == sample.content
            and row.category == sample.category
            and row.source == sample.source
            and row.source_url == sample.source_url
            and row.content_hash == expected_hash
            and row.publish_time == sample.publish_time
            and row.crawl_time is not None
            and row.created_at is not None
            and row.updated_at is not None
        )
        check(
            "入库字段完整：标题/正文/分类/来源/URL/哈希/发布与采集时间全部落库",
            "D3-07",
            structural_ok,
            f"落库字段不符：id={first.id}",
            results,
        )
        if created:
            # 本次新写入：必须处于状态机初始态，摘要职责字段为空（摘要由 Worker 阶段负责）
            duty_ok = (
                row.summary_status == "pending"
                and row.summary is None
                and row.summary_error is None
                and row.summary_time_ms is None
                and row.model_version is None
            )
            check(
                "入库职责字段：新写入记录 summary_status=pending 且摘要相关字段为空",
                "D3-07",
                duty_ok,
                f"入库状态不符：summary_status={row.summary_status}, summary={row.summary!r}",
                results,
            )
        else:
            # 此前运行已入库、可能已被 Worker 处理：仅要求状态机取值合法
            check(
                "入库职责字段：已有记录 summary_status 处于状态机合法取值",
                "D3-07",
                row.summary_status in {"pending", "processing", "completed", "failed"},
                f"入库状态非法：summary_status={row.summary_status}",
                results,
            )

        # D3-05：六类校验兜底 —— 非法分类必须在写入前被拒绝（校验样本不会入库）
        reject = RawArticle(
            title="验收脚本-六类校验样本（预期被拒绝，不入库）",
            content="该样本仅用于触发 NewsService 六类校验，禁止写入数据库。",
            category="娱乐",
            source="验收脚本",
            source_url="https://verify.invalid/no-such-page",
            publish_time=None,
        )
        rejected = False
        try:
            NewsService.save_article(db, reject)
        except BusinessError:
            rejected = True
        reject_hash = hashlib.sha256(reject.content.encode("utf-8")).hexdigest()
        not_written = (
            db.scalar(
                select(func.count()).select_from(NewsArticle).where(
                    NewsArticle.content_hash == reject_hash
                )
            )
            or 0
        ) == 0
        check(
            "六类校验：非法分类入库被拒绝且未写库",
            "D3-05",
            rejected and not_written,
            f"非法分类未被正确拒绝（rejected={rejected}, 写库={not not_written}）",
            results,
        )
        return db, None
    except Exception:
        results.fail("D3-06", f"执行异常：{traceback.format_exc(limit=3)}")
        results.fail("D3-07", "同上，见 D3-06 异常")
        return db, None
    return db, None


# ---------------------------------------------------------------------------
# 阶段 5：D3-08/09/10 Service 与 REST API 契约
# ---------------------------------------------------------------------------

def stage_api(
    results: Results, db: Session | None, sample_row_id: int | None, db_error: str | None
) -> None:
    """D3-08/09/10：TestClient 走完整 FastAPI 路由校验 API 契约。"""
    if db is None:
        for task in ("D3-08", "D3-09", "D3-10"):
            if db_error:
                results.fail(task, f"依赖数据库，无法执行 —— {db_error}")
            else:
                results.skip(task, "数据库检查已跳过（--skip-db），API 查询检查依赖数据库")
        return

    try:
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)

        # D3-08：固定六类，Service 与 API 两层一致且不随库内数据变化
        service_categories = NewsService.list_categories()
        resp = client.get("/api/categories")
        body = resp.json()
        check(
            "固定六分类：Service 与 GET /api/categories 均返回系统六类",
            "D3-08",
            resp.status_code == 200
            and service_categories == SIX_CATEGORIES
            and body.get("code") == 0
            and body.get("data") == SIX_CATEGORIES,
            f"分类查询不符：http={resp.status_code}, service={service_categories}, api={body}",
            results,
        )

        # D3-09：分页结构、字段契约（无 content）与默认时间倒序
        resp = client.get("/api/news", params={"page": 1, "page_size": 5})
        body = resp.json()
        data = body.get("data") or {}
        items = data.get("items") or []
        structure_ok = (
            resp.status_code == 200
            and body.get("code") == 0
            and data.get("page") == 1
            and data.get("page_size") == 5
            and isinstance(data.get("total"), int)
            and isinstance(items, list)
            and len(items) <= 5
        )
        check(
            "分页结构：GET /api/news 返回 items/page/page_size/total 且单页不超限",
            "D3-09",
            structure_ok,
            f"分页结构不符：http={resp.status_code}, body={str(body)[:200]}",
            results,
        )

        fields_ok = bool(items) and all(
            set(item.keys()) == _LIST_FIELDS and "content" not in item for item in items
        )
        check(
            "列表字段契约：仅返回 7 个契约字段，绝不返回 content",
            "D3-09",
            fields_ok,
            f"列表字段不符：实际字段={sorted(items[0].keys()) if items else '空列表'}",
            results,
        )

        resp50 = client.get("/api/news", params={"page": 1, "page_size": 50})
        items50 = (resp50.json().get("data") or {}).get("items") or []
        times = [item.get("publish_time") for item in items50]
        non_null = [t for t in times if t is not None]
        first_null = times.index(None) if None in times else len(times)
        ordered = all(
            non_null[i] >= non_null[i + 1] for i in range(len(non_null) - 1)
        ) and all(t is None for t in times[first_null:])
        check(
            "默认排序：publish_time DESC，空值排在最后",
            "D3-09",
            ordered,
            f"排序不符：publish_time 序列={times[:10]}",
            results,
        )

        if sample_row_id is not None:
            sample_row = db.get(NewsArticle, sample_row_id)
            if sample_row is not None:
                resp_c = client.get("/api/news", params={"page": 1, "page_size": 50, "category": sample_row.category})
                body_c = resp_c.json()
                data_c = body_c.get("data") or {}
                db_total = (
                    db.scalar(
                        select(func.count()).select_from(NewsArticle).where(
                            NewsArticle.category == sample_row.category
                        )
                    )
                    or 0
                )
                check(
                    f"分类过滤：category={sample_row.category} 只返回该类且 total 与库一致",
                    "D3-09",
                    resp_c.status_code == 200
                    and data_c.get("total") == db_total
                    and all(
                        item.get("category") == sample_row.category
                        for item in data_c.get("items") or []
                    ),
                    f"分类过滤不符：http={resp_c.status_code}, total={data_c.get('total')}, 库内={db_total}",
                    results,
                )

        # 参数越界为 FastAPI 校验 422；非法分类为业务错误 400/1001
        resp_range = client.get("/api/news", params={"page": 0, "page_size": 51})
        resp_cat = client.get("/api/news", params={"page": 1, "category": "娱乐"})
        body_cat = resp_cat.json()
        check(
            "分页参数约束：page<1 或 page_size>50 → 422；非法分类 → 400/1001",
            "D3-09",
            resp_range.status_code == 422
            and resp_cat.status_code == 400
            and body_cat.get("code") == 1001,
            f"错误处理不符：page0/page_size51 → {resp_range.status_code}（应422），"
            f"非法分类 → {resp_cat.status_code}/{body_cat.get('code')}（应400/1001）",
            results,
        )

        # D3-10：详情字段完整，正文与入库内容一致，无 client_id 时用户状态固定
        if sample_row_id is not None:
            resp_d = client.get(f"/api/news/{sample_row_id}")
            body_d = resp_d.json()
            data_d = body_d.get("data") or {}
            sample_row = db.get(NewsArticle, sample_row_id)
            detail_ok = (
                resp_d.status_code == 200
                and body_d.get("code") == 0
                and set(data_d.keys()) == _DETAIL_FIELDS
                and data_d.get("content") == (sample_row.content if sample_row else None)
                and data_d.get("source_url") == (sample_row.source_url if sample_row else None)
                and data_d.get("is_favorite") is False
                and data_d.get("feedback") is None
                and data_d.get("summary_status") in {"pending", "processing", "completed", "failed"}
            )
            check(
                "详情契约：12 个字段完整，正文一致，无 X-Client-ID 时 is_favorite=false/feedback=null",
                "D3-10",
                detail_ok,
                f"详情不符：http={resp_d.status_code}, 字段={sorted(data_d.keys()) if data_d else '空'}",
                results,
            )
        else:
            results.skip("D3-10", "无样本记录，跳过详情正例校验（404 反例仍执行）")

        resp_404 = client.get("/api/news/999999999")
        body_404 = resp_404.json()
        check(
            "详情 404：不存在的 news_id → 404/1002",
            "D3-10",
            resp_404.status_code == 404 and body_404.get("code") == 1002,
            f"404 处理不符：http={resp_404.status_code}, code={body_404.get('code')}",
            results,
        )
    except Exception:
        results.fail("D3-08", f"执行异常：{traceback.format_exc(limit=3)}")
        results.fail("D3-09", "同上，见 D3-08 异常")
        results.fail("D3-10", "同上，见 D3-08 异常")


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------

def print_summary(results: Results) -> int:
    """按任务号汇总验收结论，返回进程退出码。"""
    statuses = {task: results.task_status(task) for task in _TASK_ORDER}
    passed = sum(1 for s in statuses.values() if s == "PASS")
    failed = sum(1 for s in statuses.values() if s == "FAIL")
    skipped = sum(1 for s in statuses.values() if s == "SKIP")

    print()
    print("=" * 62)
    print("D3-01 ~ D3-10 阶段验收汇总")
    print("=" * 62)
    for task in _TASK_ORDER:
        mark = {"PASS": "通过", "FAIL": "失败", "SKIP": "跳过"}[statuses[task]]
        print(f"  {task}  {mark}  {_TASK_NAMES[task]}")
    print("-" * 62)
    print(f"  结果：{passed} 通过 / {failed} 失败 / {skipped} 跳过")
    if failed:
        print("  存在失败项：请查看上方 [FAIL] 行定位问题。")
    if skipped:
        print("  提示：跳过项通常为 MySQL 未启动或使用 --skip-crawl/--skip-db。")
    print("=" * 62)
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="D3-01～D3-10 阶段验收脚本")
    parser.add_argument("--limit", type=int, default=3, help="每个新闻源最多采集条数（默认 3）")
    parser.add_argument("--interval", type=float, default=1.0, help="详情页请求间隔秒数（默认 1.0）")
    parser.add_argument("--skip-crawl", action="store_true", help="跳过真实采集，改用库内最新新闻作样本")
    parser.add_argument("--skip-db", action="store_true", help="跳过所有需要数据库的检查")
    parser.add_argument(
        "--mysqld", type=str, default=None,
        help="mysqld.exe 完整路径（可选；自动启动时优先使用，默认自动搜索服务与常见目录）",
    )
    args = parser.parse_args()

    print("=" * 62)
    print("D3 阶段验收（D3-01 ~ D3-10）：采集 / 清洗 / 入库 / 查询")
    print("=" * 62)

    results = Results()

    stage_cleaner(results)
    articles = [] if args.skip_crawl else stage_crawl(results, args.limit, args.interval)
    if args.skip_crawl:
        results.skip("D3-01", "按要求跳过真实采集（--skip-crawl）")
        results.skip("D3-02", "按要求跳过真实采集（--skip-crawl）")
    stage_mapping(results, articles)
    if not args.skip_db:
        from app.config import get_settings

        db_settings = get_settings()
        ensure_mysql(results, db_settings.db_host, db_settings.db_port, args.mysqld)
    db, db_error = stage_database(results, articles, use_db=not args.skip_db)
    sample_row_id = None
    if db is not None:
        row = db.scalar(select(NewsArticle.id).order_by(NewsArticle.id.desc()).limit(1))
        sample_row_id = int(row) if row is not None else None
    stage_api(results, db, sample_row_id, db_error)
    if db is not None:
        db.close()

    return print_summary(results)


if __name__ == "__main__":
    sys.exit(main())
