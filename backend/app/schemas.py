"""已冻结的 API 请求和响应数据结构。"""

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataType = TypeVar("DataType")


class ApiResponse(BaseModel, Generic[DataType]):
    """统一 API 响应包装。"""

    code: int = 0
    message: str = "ok"
    data: DataType | None = None


class HealthData(BaseModel):
    """健康检查响应数据。"""

    status: str


class NewsListItem(BaseModel):
    """新闻列表单项，不含正文。"""

    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    summary: str | None
    category: str
    source: str
    publish_time: datetime | None
    summary_status: str


class NewsDetail(BaseModel):
    """新闻详情响应数据。"""

    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    content: str
    summary: str | None
    category: str
    source: str
    source_url: str
    publish_time: datetime | None
    summary_status: str
    summary_time_ms: int | None
    is_favorite: bool
    feedback: bool | None


class PageData(BaseModel, Generic[DataType]):
    """分页响应数据。"""

    items: list[DataType]
    page: int
    page_size: int
    total: int


class FeedbackRequest(BaseModel):
    """摘要评价请求。"""

    helpful: bool


class FeedbackResponse(BaseModel):
    """摘要评价成功响应，对应 docs/API.md §11。"""

    news_id: int
    helpful: bool


class FavoriteResponse(BaseModel):
    """收藏与取消收藏的统一响应数据，对应 docs/API.md §9-10。"""

    news_id: int
    is_favorite: bool


class ModelMetrics(BaseModel):
    """正式模型评价指标。"""

    model_name: str
    model_version: str
    dataset: str
    dataset_split: str
    sample_count: int
    rouge1: float
    rouge2: float
    rougeL: float
    avg_generation_time_ms: int
    p95_generation_time_ms: int


class SummaryStatusData(BaseModel):
    """摘要请求的当前状态。"""

    news_id: int
    summary_status: str
    summary: str | None = None
    generation_time_ms: int | None = Field(default=None)
