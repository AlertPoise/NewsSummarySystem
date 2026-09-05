"""统一业务异常与错误码定义。

A1-04 公共层规范：业务异常必须经 BusinessError 抛出，由 main.py 全局 handler 序列化为
docs/API.md §1 规定的统一响应 `{"code": <非0>, "message": <描述>, "data": null}`。
"""

from __future__ import annotations

from fastapi import HTTPException


# ---------- 业务错误码（docs/API.md §1） ----------

ERR_INVALID_REQUEST = 1001  # 输入/请求头非法
ERR_NOT_FOUND = 1002        # 资源不存在
ERR_STATE_CONFLICT = 1003   # 状态冲突
ERR_AI_UNAVAILABLE = 1004   # 正式 AI 不可用
ERR_INTERNAL = 1005         # 内部错误


class BusinessError(HTTPException):
    """统一业务异常。Service 层 raise 此异常，由 FastAPI 全局 handler 捕获并返回统一响应。"""

    def __init__(self, *, code: int, message: str, http_status: int) -> None:
        super().__init__(status_code=http_status, detail=message)
        self.code = code
        self.message = message
        # status_code 由 HTTPException 自身管理；此处统一别名避免外部误用
        self.http_status = http_status


# ---------- 工厂方法（按文档错误码） ----------


def invalid_request(message: str = "请求参数非法") -> BusinessError:
    """HTTP 400 / 错误码 1001：输入或 Header 非法。"""

    return BusinessError(code=ERR_INVALID_REQUEST, message=message, http_status=400)


def not_found(message: str = "资源不存在") -> BusinessError:
    """HTTP 404 / 错误码 1002：资源不存在。"""

    return BusinessError(code=ERR_NOT_FOUND, message=message, http_status=404)


def state_conflict(message: str = "状态冲突") -> BusinessError:
    """HTTP 409 / 错误码 1003：状态冲突（如摘要任务并发）。"""

    return BusinessError(code=ERR_STATE_CONFLICT, message=message, http_status=409)


def ai_unavailable(message: str = "正式 AI 系统不可用") -> BusinessError:
    """HTTP 503 / 错误码 1004：正式 AI 不可用（如 Pipeline 未 load）。"""

    return BusinessError(code=ERR_AI_UNAVAILABLE, message=message, http_status=503)


def internal_error(message: str = "内部错误") -> BusinessError:
    """HTTP 500 / 错误码 1005：内部业务失败。"""

    return BusinessError(code=ERR_INTERNAL, message=message, http_status=500)
