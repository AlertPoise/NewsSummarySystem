"""FastAPI 应用入口。"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import favorites, feedback, model, news
from app.exceptions import BusinessError
from app.schemas import ApiResponse, HealthData

app = FastAPI(title="新闻文章自动摘要系统", version="1.0.0")

# A1-04 公共层规范：HarmonyOS 客户端在开发/调试态需要 CORS；
# 生产部署单一来源时收紧 allow_origins 至具体域名。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


@app.exception_handler(BusinessError)
async def business_error_handler(_request: Request, exc: BusinessError) -> JSONResponse:
    """业务异常 → docs/API.md §1 规定的统一响应结构。"""

    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": exc.message, "data": None},
    )


@app.exception_handler(NotImplementedError)
async def not_implemented_handler(_request: Request, _exc: NotImplementedError) -> JSONResponse:
    """阶段占位路由 → HTTP 501 + 统一响应，避免裸文本 500 误导联调方。

    阶段 3 业务实现完成后此 handler 自然不再命中，可保留兜底。
    """

    return JSONResponse(
        status_code=501,
        content={
            "code": 1005,
            "message": "该接口尚未实现（当前处于阶段 1 骨架冻结期）",
            "data": None,
        },
    )


@app.get("/api/health", response_model=ApiResponse[HealthData])
def health_check() -> ApiResponse[HealthData]:
    """返回后端进程健康状态，不连接数据库或模型。"""

    return ApiResponse(data=HealthData(status="healthy"))


# 路由挂载：news.py 由 D 维护；favorites/feedback/model 由 A 维护。
app.include_router(news.router, prefix="/api")
app.include_router(favorites.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(model.router, prefix="/api")
