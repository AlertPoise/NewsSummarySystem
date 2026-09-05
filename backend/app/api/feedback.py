"""摘要反馈 REST 路由。

A1-04 公共层规范：仅冻结路径、依赖与响应结构；阶段 3 由 A 实现首次 INSERT / 后续 UPDATE。
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import require_client_id
from app.schemas import ApiResponse, FeedbackRequest, FeedbackResponse

router = APIRouter(tags=["反馈"])


@router.post(
    "/news/{news_id}/feedback",
    response_model=ApiResponse[FeedbackResponse],
)
def submit_feedback(
    news_id: int,
    body: FeedbackRequest,
    client_id: Annotated[str, Depends(require_client_id)],
) -> ApiResponse[FeedbackResponse]:
    """TODO(A3-04)：同一 client/news 首次 INSERT、后续 UPDATE；返回当前最新评价。"""

    raise NotImplementedError("Phase 3 实现：UserService.upsert_feedback")
