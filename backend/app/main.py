"""FastAPI 应用入口。"""

from fastapi import FastAPI

from app.api import favorites, feedback, model, news
from app.schemas import ApiResponse, HealthData

app = FastAPI(title="新闻文章自动摘要系统", version="1.0.0")
app.include_router(news.router, prefix="/api")
app.include_router(favorites.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(model.router, prefix="/api")


@app.get("/api/health", response_model=ApiResponse[HealthData])
def health_check() -> ApiResponse[HealthData]:
    """返回后端进程健康状态，不连接数据库或模型。"""
    return ApiResponse(data=HealthData(status="healthy"))
