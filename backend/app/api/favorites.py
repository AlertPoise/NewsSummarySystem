"""收藏相关 REST 路由骨架。"""

from fastapi import APIRouter

router = APIRouter(tags=["收藏"])

# TODO(A-阶段3)：注册 /favorites 和 /favorites/{news_id} 路由；输入为必填 X-Client-ID 与冻结的 Path 参数，输出为 docs/API.md 规定的 ApiResponse，必须调用 UserService 并遵守收藏幂等接口。
