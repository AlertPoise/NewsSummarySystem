"""模型指标 REST 路由。

A1-04 公共层规范：仅冻结路径与响应结构；阶段 3 由 A 实现最新 CNewSum/test 指标查询。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ApiResponse, ModelMetrics

router = APIRouter(tags=["模型"])


@router.get("/model/metrics", response_model=ApiResponse[ModelMetrics])
def get_metrics(db: Annotated[Session, Depends(get_db)]) -> ApiResponse[ModelMetrics]:
    """TODO(A3-06)：返回最新一条 model_evaluations；dataset=CNewSum 且 dataset_split=test；无记录返回 404/1002。"""

    raise NotImplementedError("Phase 3 实现：ModelService.get_latest_metrics")
