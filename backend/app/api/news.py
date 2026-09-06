"""新闻与摘要任务 REST 路由。

A1-04 公共层规范：路由只调用 NewsService/SummaryService，错误统一抛 BusinessError，
由 main.py 全局 handler 序列化。POST summary 不在 HTTP 线程运行 Transformer：
按需单篇经 on_demand 队列交给 API 进程内守护线程，复用 Worker 的正式流水线
（模型常驻，见 app/on_demand.py）；批量采集/摘要仍由外部 Worker 进程执行。
X-Client-ID 经 dependencies.parse_client_id 解析。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from app import on_demand
from app.database import get_db
from app.dependencies import parse_client_id
from app.exceptions import not_found
from app.schemas import ApiResponse, NewsDetail, NewsListItem, PageData, SummaryStatusData
from app.services.news_service import NewsService
from app.services.summary_service import COMPLETED, PENDING, SummaryService

router = APIRouter(tags=["新闻"])


@router.get("/categories", response_model=ApiResponse[list[str]])
def get_categories() -> ApiResponse[list[str]]:
    """返回固定六类分类，不随数据库内容动态变化。"""
    return ApiResponse(data=NewsService.list_categories())


@router.get("/news", response_model=ApiResponse[PageData[NewsListItem]])
def list_news(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1, description="页码，最小 1"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量，1~50"),
    category: str | None = Query(None, description="分类，须为六类之一"),
) -> ApiResponse[PageData[NewsListItem]]:
    """分页查询新闻，默认 publish_time DESC 稳定排序，禁止返回 content。"""
    total, items = NewsService.list_news(db, page=page, page_size=page_size, category=category)
    page_data = PageData[NewsListItem](
        items=[NewsListItem(**item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )
    return ApiResponse(data=page_data)


@router.get("/news/{news_id}", response_model=ApiResponse[NewsDetail])
def get_news_detail(
    news_id: Annotated[int, Path(gt=0, description="新闻 id，必须大于 0（非法值 422）")],
    db: Annotated[Session, Depends(get_db)],
    client_id: Annotated[str | None, Depends(parse_client_id)] = None,
) -> ApiResponse[NewsDetail]:
    """新闻详情；用户状态必须经 UserService.get_news_user_state 复用，不在此重写。"""
    detail = NewsService.get_news_detail(db, news_id=news_id, client_id=client_id)
    if detail is None:
        raise not_found("新闻不存在")
    return ApiResponse(data=NewsDetail(**detail))


@router.post(
    "/news/{news_id}/summary",
    response_model=ApiResponse[SummaryStatusData],
)
def trigger_summary(
    news_id: Annotated[int, Path(gt=0, description="新闻 id，必须大于 0（非法值 422）")],
    db: Annotated[Session, Depends(get_db)],
    response: Response,
) -> ApiResponse[SummaryStatusData]:
    """摘要触发/重试；仅调用 SummaryService，completed 返回 200，其余状态返回 202。"""
    result = SummaryService.request_summary(db, news_id=news_id)
    if result is None:
        raise not_found("新闻不存在")
    if result["summary_status"] == PENDING:
        # 按需生成：入队交给 API 进程内守护线程（幂等，重复请求由领取语义去重）。
        # 守护线程复用 Worker 正式流水线且模型常驻：首次点击约 10~30 秒（加载模型），
        # 之后每篇仅推理耗时；不阻塞 HTTP 线程。
        on_demand.request(news_id)
    if result["summary_status"] != COMPLETED:
        response.status_code = 202
    return ApiResponse(data=SummaryStatusData(**result))
