"""新闻相关 REST 路由骨架。"""

from fastapi import APIRouter

router = APIRouter(tags=["新闻"])

# TODO(D-阶段3)：注册 /categories、/news、/news/{news_id} 与 /news/{news_id}/summary 路由；输入为 docs/API.md 冻结的 Query、Path、Header 和 Body，输出为 schemas.py 定义的 ApiResponse，必须调用 NewsService 或 SummaryService，不得在路由中直接访问 SQLAlchemy 或 AI 模型。
