"""新闻与摘要任务 REST 路由。

A1-04 公共层规范：D 独享所有新闻路由；本阶段只冻结路径与依赖，阶段 3 由 D 填充。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import parse_client_id
from app.schemas import ApiResponse, NewsDetail, NewsListItem, PageData, SummaryStatusData

router = APIRouter(tags=["新闻"])


@router.get("/categories", response_model=ApiResponse[list[str]])
def get_categories() -> ApiResponse[list[str]]:
    """TODO(D3-08)：固定六类（科技、财经、社会、体育、国内、国际），按稳定顺序返回。"""

    raise NotImplementedError("D-Phase 3 实现")


@router.get("/news", response_model=ApiResponse[PageData[NewsListItem]])
def list_news(
    db: Annotated[Session, Depends(get_db)],
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
) -> ApiResponse[PageData[NewsListItem]]:
    """TODO(D3-09)：page>=1、page_size 范围 1~50、category∈六类；publish_time DESC 稳定排序，禁止返回 content。"""

    raise NotImplementedError("D-Phase 3 实现")


@router.get("/news/{news_id}", response_model=ApiResponse[NewsDetail])
def get_news_detail(
    news_id: int,
    db: Annotated[Session, Depends(get_db)],
    client_id: Annotated[str | None, Depends(parse_client_id)] = None,
) -> ApiResponse[NewsDetail]:
    """TODO(D3-10 + A3-07)：详情字段；用户状态必须通过 UserService.get_news_user_state 复用。"""

    raise NotImplementedError("D+A-Phase 3 实现")


@router.post(
    "/news/{news_id}/summary",
    response_model=ApiResponse[SummaryStatusData],
)
def trigger_summary(
    news_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> ApiResponse[SummaryStatusData]:
    """TODO(D3-13)：仅调用 SummaryService；不得在 HTTP 线程运行 Transformer；Worker 是唯一 AI 调用者。"""

    raise NotImplementedError("D-Phase 3 实现")
