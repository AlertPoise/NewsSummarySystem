"""收藏相关 REST 路由（阶段 3 A3-01~03 实现）。

路由层只做：依赖注入 → 调 Service → 包成 ApiResponse。
不允许在路由层写 SQL、调 AI、复制用户查询（DATABASE.md §6 + ARCHITECTURE.md §2）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_client_id
from app.schemas import ApiResponse, FavoriteResponse, NewsListItem
from app.services.user_service import UserService

router = APIRouter(tags=["收藏"])


@router.get("/favorites", response_model=ApiResponse[list[NewsListItem]])
def list_favorites(
    client_id: Annotated[str, Depends(require_client_id)],
    db: Annotated[Session, Depends(get_db)],
) -> ApiResponse[list[NewsListItem]]:
    """A3-03 仅返回该 client_id 的收藏；不返回 content（API.md §8）。"""

    items = UserService.list_favorites(db, client_id=client_id)
    return ApiResponse(data=items)


@router.post(
    "/favorites/{news_id}",
    response_model=ApiResponse[FavoriteResponse],
)
def add_favorite(
    news_id: Annotated[int, Path(gt=0, description="新闻 id，必须大于 0（非法值 422）")],
    client_id: Annotated[str, Depends(require_client_id)],
    db: Annotated[Session, Depends(get_db)],
) -> ApiResponse[FavoriteResponse]:
    """A3-01 幂等收藏：重复 POST 仍 200 + is_favorite=True，记录不增加。"""

    result = UserService.add_favorite(db, client_id=client_id, news_id=news_id)
    return ApiResponse(data=result)


@router.delete(
    "/favorites/{news_id}",
    response_model=ApiResponse[FavoriteResponse],
)
def remove_favorite(
    news_id: Annotated[int, Path(gt=0, description="新闻 id，必须大于 0（非法值 422）")],
    client_id: Annotated[str, Depends(require_client_id)],
    db: Annotated[Session, Depends(get_db)],
) -> ApiResponse[FavoriteResponse]:
    """A3-02 幂等取消：无记录时仍 200 + is_favorite=False。"""

    result = UserService.remove_favorite(db, client_id=client_id, news_id=news_id)
    return ApiResponse(data=result)