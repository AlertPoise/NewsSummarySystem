"""摘要反馈 REST 路由（阶段 3 A3-04 实现）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_client_id
from app.schemas import ApiResponse, FeedbackRequest, FeedbackResponse
from app.services.user_service import UserService

router = APIRouter(tags=["反馈"])


@router.post(
    "/news/{news_id}/feedback",
    response_model=ApiResponse[FeedbackResponse],
)
def submit_feedback(
    news_id: Annotated[int, Path(gt=0, description="新闻 id，必须大于 0（非法值 422）")],
    body: FeedbackRequest,
    client_id: Annotated[str, Depends(require_client_id)],
    db: Annotated[Session, Depends(get_db)],
) -> ApiResponse[FeedbackResponse]:
    """A3-04 同一 (client_id, news_id) 首次 INSERT、后续 UPDATE；返回当前最新评价。"""

    result = UserService.upsert_feedback(
        db,
        client_id=client_id,
        news_id=news_id,
        helpful=body.helpful,
    )
    return ApiResponse(data=result)