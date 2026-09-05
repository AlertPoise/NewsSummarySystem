"""模型指标 REST 路由（阶段 3 A3-06 实现）。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ApiResponse, ModelMetrics
from app.services.model_service import ModelService

router = APIRouter(tags=["模型"])


@router.get("/model/metrics", response_model=ApiResponse[ModelMetrics])
def get_metrics(db: Annotated[Session, Depends(get_db)]) -> ApiResponse[ModelMetrics]:
    """A3-06 返回最新一条 model_evaluations（dataset=CNewSum, dataset_split=test）；无记录返回 404/1002。"""

    result = ModelService.get_latest_metrics(db)
    return ApiResponse(data=result)