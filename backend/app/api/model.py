"""模型指标 REST 路由骨架。"""

from fastapi import APIRouter

router = APIRouter(tags=["模型"])

# TODO(A-阶段3)：注册 /model/metrics 路由；输入为无请求体的指标查询，输出为最新正式 CNewSum 模型的 ModelMetrics，必须调用 ModelService 并遵守 docs/API.md。
