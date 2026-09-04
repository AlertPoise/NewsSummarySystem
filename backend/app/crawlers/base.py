"""新闻来源抽象接口。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RawArticle:
    """采集后、入库前的标准新闻数据。"""

    title: str
    content: str
    category: str
    source: str
    source_url: str
    publish_time: datetime | None


class NewsSource(ABC):
    """所有真实新闻来源必须实现的采集协议。"""

    @abstractmethod
    def fetch_articles(self) -> list[RawArticle]:
        """获取并返回来源中的真实新闻文章。"""
        raise NotImplementedError
