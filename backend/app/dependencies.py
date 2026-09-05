"""FastAPI 共享依赖。

A1-04 公共层规范：
- X-Client-ID Header 必须为 UUID v4；
- 必填与可选端点使用不同入口，避免每个路由重复实现。
"""

from __future__ import annotations

import uuid

from fastapi import Header


def parse_client_id(
    x_client_id: str | None = Header(default=None, alias="X-Client-ID", description="UUID v4 客户端标识"),
) -> str | None:
    """解析 X-Client-ID；当允许省略时（新闻详情）使用此依赖。

    返回合法 UUID v4 字符串或 None。格式错误时抛出 BusinessError(1001)。
    """

    if x_client_id is None:
        return None
    try:
        parsed = uuid.UUID(x_client_id)
    except ValueError as exc:
        from app.exceptions import invalid_request

        raise invalid_request("X-Client-ID 格式错误，必须为 UUID v4") from exc
    if parsed.version != 4:
        from app.exceptions import invalid_request

        raise invalid_request("X-Client-ID 格式错误，必须为 UUID v4")
    return str(parsed)


def require_client_id(
    x_client_id: str | None = Header(default=None, alias="X-Client-ID", description="UUID v4 客户端标识，必填"),
) -> str:
    """必填校验入口：用于收藏/反馈等强制要求 client_id 的端点。

    缺失或非 UUID v4 一律抛出 BusinessError(400/1001)。
    """

    if x_client_id is None:
        from app.exceptions import invalid_request

        raise invalid_request("缺少 X-Client-ID Header")
    result = parse_client_id(x_client_id)
    if result is None:
        # parse_client_id 在失败时已抛错；此处仅作类型守卫。
        from app.exceptions import invalid_request

        raise invalid_request("X-Client-ID 格式错误，必须为 UUID v4")
    return result
