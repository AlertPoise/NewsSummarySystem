"""API 测试骨架。"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_check() -> None:
    """验证阶段1健康检查响应。"""
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"code": 0, "message": "ok", "data": {"status": "healthy"}}


# TODO(A-阶段3)：补充统一错误响应、收藏、反馈和模型指标 API 测试；输入为测试数据库及冻结请求，输出为 HTTP 状态码和 ApiResponse 断言，必须遵守 docs/API.md。
# TODO(D-阶段3)：补充分类、新闻分页、详情和摘要请求 API 测试；输入为测试数据库与新闻记录，输出为冻结 JSON 字段断言，必须遵守 docs/API.md。
