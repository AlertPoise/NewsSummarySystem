"""收藏相关 REST 路由。

A1-04 公共层规范：仅冻结路径、依赖与响应结构；阶段 3 由 A 实现幂等收藏逻辑。
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import require_client_id
from app.schemas import ApiResponse, FavoriteResponse, NewsListItem

router = APIRouter(tags=["收藏"])


@router.get("/favorites", response_model=ApiResponse[list[NewsListItem]])
def list_favorites(
    client_id: Annotated[str, Depends(require_client_id)],
) -> ApiResponse[list[NewsListItem]]:
    """TODO(A3-03)：调用 UserService.list_favorites，仅返回该客户端的收藏记录。"""

    raise NotImplementedError("Phase 3 实现：UserService.list_favorites")


@router.post(
    "/favorites/{news_id}",
    response_model=ApiResponse[FavoriteResponse],
)
def add_favorite(
    news_id: int,
    client_id: Annotated[str, Depends(require_client_id)],
) -> ApiResponse[FavoriteResponse]:
    """TODO(A3-01)：幂等收藏；重复 POST 仍返回 is_favorite=true，记录不增加。"""

    raise NotImplementedError("Phase 3 实现：UserService.add_favorite")


@router.delete(
    "/favorites/{news_id}",
    response_model=ApiResponse[FavoriteResponse],
)
def remove_favorite(
    news_id: int,
    client_id: Annotated[str, Depends(require_client_id)],
) -> ApiResponse[FavoriteResponse]:
    """TODO(A3-02)：幂等取消；无记录时仍返回 is_favorite=false。"""

    raise NotImplementedError("Phase 3 实现：UserService.remove_favorite")
