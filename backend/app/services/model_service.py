"""模型评价结果查询业务（阶段 3 A3-06 实现）。

本模块负责对外暴露最新正式模型的离线评价和性能指标。遵循：
- docs/DATABASE.md §4 model_evaluations 字段语义；
- docs/DATABASE.md §9.5 取数规则：ORDER BY created_at DESC LIMIT 1；
- docs/API.md §12 dataset 固定 CNewSum、dataset_split 固定 test；
- ARCHITECTURE.md §7 模型指标字段固定（model_name、model_version、dataset、
  dataset_split、sample_count、rouge1/2/L、avg/p95_generation_time_ms）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import not_found
from app.models import ModelEvaluation


class ModelService:
    """查询最新正式模型的离线评价和性能指标。"""

    @staticmethod
    def get_latest_metrics(db: Session) -> dict[str, Any]:
        """A3-06 取 model_evaluations 最新一条；无记录返回 404/1002。

        表数据量小（DATABASE.md §9.5 注释），不另加索引；LIMIT 1 + 主键降序
        即可保证稳定的"最新"语义。DECIMAL(7,6) 列通过 float() 转为 Python float，
        以匹配 ModelMetrics Pydantic schema 的 float 字段。
        """

        row = db.scalar(
            select(ModelEvaluation)
            .order_by(ModelEvaluation.created_at.desc(), ModelEvaluation.id.desc())
            .limit(1)
        )
        if row is None:
            raise not_found("暂无正式模型评价数据")

        return {
            "model_name": row.model_name,
            "model_version": row.model_version,
            "dataset": row.dataset,
            "dataset_split": row.dataset_split,
            "sample_count": row.sample_count,
            "rouge1": float(row.rouge1),
            "rouge2": float(row.rouge2),
            "rougeL": float(row.rougeL),
            "avg_generation_time_ms": row.avg_generation_time_ms,
            "p95_generation_time_ms": row.p95_generation_time_ms,
        }