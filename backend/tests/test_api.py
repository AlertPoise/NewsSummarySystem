"""API 契约测试（角色 A 部分：A3-01~06 路由层验证）。

覆盖范围：
- 健康检查（阶段1 已存在）
- 5 条 A 路由（favorites GET/POST/DELETE、feedback POST、model metrics GET）
- 错误码 1001/1002/1005 触发的统一响应格式（API.md §1）
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ModelEvaluation


# ---------- 阶段1 既有 ----------


def test_health_check(client: TestClient) -> None:
    """健康检查路径 /api/health 返回 200 + 统一响应。"""

    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"code": 0, "message": "ok", "data": {"status": "healthy"}}


# ---------- A3-01 收藏：POST /api/favorites/{news_id} ----------


def test_add_favorite_success(client: TestClient, valid_uuid: str, sample_news) -> None:  # noqa: ANN001
    """首次收藏：200 + is_favorite=true，favorites 表新增一行。"""

    response = client.post(
        f"/api/favorites/{sample_news.id}",
        headers={"X-Client-ID": valid_uuid},
    )
    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "ok",
        "data": {"news_id": sample_news.id, "is_favorite": True},
    }


def test_add_favorite_idempotent(
    client: TestClient, db_session: Session, valid_uuid: str, sample_news
) -> None:  # noqa: ANN001
    """幂等：重复 POST 仍 200 + is_favorite=true，favorites 行数 = 1。"""

    client.post(f"/api/favorites/{sample_news.id}", headers={"X-Client-ID": valid_uuid})
    response = client.post(f"/api/favorites/{sample_news.id}", headers={"X-Client-ID": valid_uuid})

    assert response.status_code == 200
    assert response.json()["data"] == {"news_id": sample_news.id, "is_favorite": True}
    # 行数校验：唯一约束不失效
    from sqlalchemy import func, select

    from app.models import Favorite

    count = db_session.scalar(select(func.count()).select_from(Favorite))
    assert count == 1


def test_add_favorite_missing_client_id_returns_1001(client: TestClient, sample_news) -> None:  # noqa: ANN001
    """缺失 X-Client-ID Header → 400 + 1001。"""

    response = client.post(f"/api/favorites/{sample_news.id}")
    assert response.status_code == 400
    assert response.json()["code"] == 1001


def test_add_favorite_invalid_uuid_returns_1001(client: TestClient, sample_news) -> None:  # noqa: ANN001
    """非法 UUID v4 → 400 + 1001。"""

    response = client.post(
        f"/api/favorites/{sample_news.id}",
        headers={"X-Client-ID": "not-a-uuid"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == 1001


def test_add_favorite_news_not_found_returns_1002(client: TestClient, valid_uuid: str) -> None:
    """新闻不存在 → 404 + 1002（DATABASE.md §6 FK 兜底）。"""

    response = client.post(
        "/api/favorites/9999",
        headers={"X-Client-ID": valid_uuid},
    )
    assert response.status_code == 404
    assert response.json()["code"] == 1002


def test_user_routes_reject_non_positive_news_id_with_422(client: TestClient, valid_uuid: str) -> None:
    """Path 校验错误为 HTTP 422：收藏/反馈路由的 news_id 必须 > 0（API.md §8 冻结契约）。"""

    headers = {"X-Client-ID": valid_uuid}
    assert client.post("/api/favorites/0", headers=headers).status_code == 422
    assert client.post("/api/favorites/-1", headers=headers).status_code == 422
    assert client.delete("/api/favorites/0", headers=headers).status_code == 422
    assert (
        client.post("/api/news/0/feedback", headers=headers, json={"helpful": True}).status_code
        == 422
    )


# ---------- A3-02 取消收藏：DELETE /api/favorites/{news_id} ----------


def test_remove_favorite_success(
    client: TestClient, valid_uuid: str, sample_news
) -> None:  # noqa: ANN001
    """已收藏再取消：200 + is_favorite=false。"""

    client.post(f"/api/favorites/{sample_news.id}", headers={"X-Client-ID": valid_uuid})
    response = client.delete(
        f"/api/favorites/{sample_news.id}",
        headers={"X-Client-ID": valid_uuid},
    )
    assert response.status_code == 200
    assert response.json()["data"] == {"news_id": sample_news.id, "is_favorite": False}


def test_remove_favorite_idempotent_when_no_record(
    client: TestClient, valid_uuid: str, sample_news
) -> None:  # noqa: ANN001
    """幂等：无记录时 DELETE 仍 200 + is_favorite=false。"""

    response = client.delete(
        f"/api/favorites/{sample_news.id}",
        headers={"X-Client-ID": valid_uuid},
    )
    assert response.status_code == 200
    assert response.json()["data"] == {"news_id": sample_news.id, "is_favorite": False}


# ---------- A3-03 收藏列表：GET /api/favorites ----------


def test_list_favorites_returns_only_owned(
    client: TestClient, db_session: Session, valid_uuid: str, sample_news
) -> None:  # noqa: ANN001
    """列表只返回该 client_id 的收藏，不含 content。"""

    # 另一 client 不应出现在结果里
    from app.models import Favorite

    fixed_time = datetime(2026, 9, 5, 10, 0, 0)
    db_session.add(
        Favorite(
            client_id="another-client",
            news_id=sample_news.id,
            created_at=fixed_time,
        )
    )
    db_session.commit()

    # 当前 client 收藏
    client.post(f"/api/favorites/{sample_news.id}", headers={"X-Client-ID": valid_uuid})

    response = client.get("/api/favorites", headers={"X-Client-ID": valid_uuid})
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert len(payload["data"]) == 1
    item = payload["data"][0]
    assert item["id"] == sample_news.id
    assert item["title"] == sample_news.title
    # API.md §8 绝不含 content
    assert "content" not in item


def test_list_favorites_missing_client_id_returns_1001(client: TestClient) -> None:
    """GET /api/favorites 缺失 Header → 400 + 1001。"""

    response = client.get("/api/favorites")
    assert response.status_code == 400
    assert response.json()["code"] == 1001


# ---------- A3-04 摘要反馈：POST /api/news/{news_id}/feedback ----------


def test_submit_feedback_insert_then_update(
    client: TestClient, db_session: Session, valid_uuid: str, sample_news
) -> None:  # noqa: ANN001
    """首次 INSERT、后续 UPDATE（helpful 翻转），created_at 不变。"""

    from sqlalchemy import select

    from app.models import Feedback

    # 第一次：INSERT
    response = client.post(
        f"/api/news/{sample_news.id}/feedback",
        headers={"X-Client-ID": valid_uuid},
        json={"helpful": True},
    )
    assert response.status_code == 200
    assert response.json()["data"] == {"news_id": sample_news.id, "helpful": True}

    row = db_session.scalar(
        select(Feedback).where(
            Feedback.client_id == valid_uuid,
            Feedback.news_id == sample_news.id,
        )
    )
    assert row is not None
    first_created_at = row.created_at
    first_updated_at = row.updated_at
    assert row.helpful is True

    # 第二次：UPDATE（helpful 翻转为 false，created_at 不变）
    response = client.post(
        f"/api/news/{sample_news.id}/feedback",
        headers={"X-Client-ID": valid_uuid},
        json={"helpful": False},
    )
    assert response.status_code == 200
    assert response.json()["data"] == {"news_id": sample_news.id, "helpful": False}

    db_session.expire_all()
    row = db_session.scalar(
        select(Feedback).where(
            Feedback.client_id == valid_uuid,
            Feedback.news_id == sample_news.id,
        )
    )
    assert row is not None
    assert row.helpful is False
    # 硬性要求（DATABASE.md §3）：created_at 不变
    assert row.created_at == first_created_at
    assert row.updated_at >= first_updated_at


def test_submit_feedback_news_not_found_returns_1002(client: TestClient, valid_uuid: str) -> None:
    """新闻不存在 → 404 + 1002。"""

    response = client.post(
        "/api/news/9999/feedback",
        headers={"X-Client-ID": valid_uuid},
        json={"helpful": True},
    )
    assert response.status_code == 404
    assert response.json()["code"] == 1002


def test_submit_feedback_invalid_body_returns_422(client: TestClient, valid_uuid: str, sample_news) -> None:  # noqa: ANN001
    """缺 helpful 字段 → 422（FastAPI Pydantic 校验）。"""

    response = client.post(
        f"/api/news/{sample_news.id}/feedback",
        headers={"X-Client-ID": valid_uuid},
        json={},
    )
    assert response.status_code == 422


# ---------- A3-06 模型指标：GET /api/model/metrics ----------


def test_get_model_metrics_success(
    client: TestClient, db_session: Session, sample_news
) -> None:  # noqa: ANN001
    """塞一条 model_evaluations → 返回该条指标。"""

    fixed_time = datetime(2026, 9, 5, 12, 0, 0)
    db_session.add(
        ModelEvaluation(
            model_version="v1.0.0",
            model_name="news_summarizer_v1",
            dataset="CNewSum",
            dataset_split="test",
            sample_count=1000,
            rouge1=0.500000,
            rouge2=0.300000,
            rougeL=0.450000,
            avg_generation_time_ms=900,
            p95_generation_time_ms=1400,
            created_at=fixed_time,
        )
    )
    db_session.commit()

    response = client.get("/api/model/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["model_name"] == "news_summarizer_v1"
    assert payload["data"]["dataset"] == "CNewSum"
    assert payload["data"]["dataset_split"] == "test"
    assert payload["data"]["rougeL"] == pytest.approx(0.45)


def test_get_model_metrics_no_record_returns_1002(client: TestClient) -> None:
    """无 model_evaluations 记录 → 404 + 1002。"""

    response = client.get("/api/model/metrics")
    assert response.status_code == 404
    assert response.json()["code"] == 1002


def test_get_model_metrics_returns_latest_only(
    client: TestClient, db_session: Session, sample_news
) -> None:  # noqa: ANN001
    """多条评价记录时，只返回 created_at 最新一条（DATABASE.md §9.5）。"""

    old_time = datetime(2026, 9, 4, 12, 0, 0)
    new_time = datetime(2026, 9, 5, 12, 0, 0)
    db_session.add_all(
        [
            ModelEvaluation(
                model_version="v0.9.0",
                model_name="old_model",
                dataset="CNewSum",
                dataset_split="test",
                sample_count=500,
                rouge1=0.400000,
                rouge2=0.250000,
                rougeL=0.350000,
                avg_generation_time_ms=1000,
                p95_generation_time_ms=1500,
                created_at=old_time,
            ),
            ModelEvaluation(
                model_version="v1.0.0",
                model_name="new_model",
                dataset="CNewSum",
                dataset_split="test",
                sample_count=1000,
                rouge1=0.500000,
                rouge2=0.300000,
                rougeL=0.450000,
                avg_generation_time_ms=900,
                p95_generation_time_ms=1400,
                created_at=new_time,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/model/metrics")
    assert response.status_code == 200
    assert response.json()["data"]["model_version"] == "v1.0.0"

# ---------- D3-10/D3-13 新闻详情与摘要触发（D 维护） ----------


def test_news_detail_returns_full_fields(client: TestClient, sample_news) -> None:  # noqa: ANN001
    """详情返回正文与来源字段，用户状态经 UserService 复用（无 header 时默认值）。"""
    response = client.get(f"/api/news/{sample_news.id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == sample_news.id
    assert data["title"] == sample_news.title
    assert data["content"] == sample_news.content
    assert data["summary_status"] == "pending"
    assert data["is_favorite"] is False
    assert data["feedback"] is None


def test_news_detail_not_found_returns_404_code_1002(client: TestClient) -> None:
    """不存在的 news_id 返回 HTTP 404 / 业务码 1002（API.md §6）。"""
    response = client.get("/api/news/999999")
    assert response.status_code == 404
    assert response.json()["code"] == 1002


def test_news_path_params_reject_non_positive_with_422(client: TestClient) -> None:
    """Path 校验错误为 HTTP 422：news_id 必须 > 0（API.md §6 冻结契约）。"""
    assert client.get("/api/news/-1").status_code == 422
    assert client.get("/api/news/0").status_code == 422
    assert client.post("/api/news/-1/summary").status_code == 422
    assert client.post("/api/news/0/summary").status_code == 422


def test_summary_trigger_returns_202_for_pending(client: TestClient, sample_news) -> None:  # noqa: ANN001
    """pending 新闻的摘要触发返回 202 且状态保持 pending，不创建推理工作。"""
    response = client.post(f"/api/news/{sample_news.id}/summary")
    assert response.status_code == 202
    assert response.json()["data"]["summary_status"] == "pending"
