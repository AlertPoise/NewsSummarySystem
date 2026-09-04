"""摘要反馈 REST 路由骨架。"""

from fastapi import APIRouter

router = APIRouter(tags=["反馈"])

# TODO(A-阶段3)：注册 /news/{news_id}/feedback 路由；输入为必填 X-Client-ID、news_id 和 FeedbackRequest，输出为统一 ApiResponse，必须调用 UserService 的新增或更新反馈业务并遵守 docs/API.md。
