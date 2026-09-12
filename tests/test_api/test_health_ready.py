"""Readiness phải phân biệt được 'backend chết' với 'DB đang ngủ'.

Bối cảnh: Supabase free tier tự pause project khi không hoạt động, và direct host của nó
là IPv6-only — cả hai đều làm DB biến mất trong khi process backend vẫn sống. Không có
readiness thì frontend không có cách nào biết để bật banner bảo trì.
"""

import pytest
from sqlalchemy.exc import OperationalError


@pytest.mark.asyncio
async def test_ready_returns_ok_when_database_reachable(client):
    response = await client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["dependency"] == "database"


@pytest.mark.asyncio
async def test_ready_returns_503_when_database_unreachable(client, monkeypatch):
    def _boom(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("could not translate host name"))

    monkeypatch.setattr("src.main.engine.connect", _boom)

    response = await client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["dependency"] == "database"
    # Có tên nguyên nhân để chẩn đoán, không nuốt lỗi thành 503 trống trơn.
    assert body["reason"] == "OperationalError"


@pytest.mark.asyncio
async def test_liveness_stays_untouched_when_database_is_down(client, monkeypatch):
    """/health là liveness: deploy.yml, Caddyfile, vercel.json, compose healthcheck và
    deploy_vm_local.sh đều dựa vào nó. DB chết vẫn phải trả 200, nếu không container bị
    giết và deploy fail dù backend còn khoẻ."""

    def _boom(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("db down"))

    monkeypatch.setattr("src.main.engine.connect", _boom)

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
