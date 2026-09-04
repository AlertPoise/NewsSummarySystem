"""第二个真实新闻来源的采集器骨架。"""

from app.crawlers.base import NewsSource, RawArticle


class SourceB(NewsSource):
    """阶段3确定的第二个真实新闻来源。"""

    def fetch_articles(self) -> list[RawArticle]:
        """获取第二个来源的真实新闻，不生成虚构数据。"""
        # TODO(D-阶段3)：确定并接入第二个真实新闻来源；输入为该来源公开页面或合规接口，输出为完整 RawArticle 列表，必须清除网页噪声、映射六类分类并遵守 crawlers/base.py。
        raise NotImplementedError("阶段3由D接入真实新闻来源")
