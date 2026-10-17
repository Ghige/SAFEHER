"""Stage 2: rate limiting + Redis fail-closed behavior."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.services import redis_service

client = TestClient(app)


def test_check_rate_limit_in_memory_blocks_after_limit(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PER_MINUTE", 1000)
    redis_service._memory_store.clear()
    with patch.object(redis_service, "_get_client", return_value=None):
        assert redis_service.check_rate_limit("stage2:test", limit=2, window_seconds=60) is True
        assert redis_service.check_rate_limit("stage2:test", limit=2, window_seconds=60) is True
        assert redis_service.check_rate_limit("stage2:test", limit=2, window_seconds=60) is False


def test_check_rate_limit_redis_error_fails_closed():
    bad = MagicMock()
    bad.pipeline.side_effect = RuntimeError("redis down")
    with patch.object(redis_service, "_get_client", return_value=bad):
        assert redis_service.check_rate_limit("stage2:redis-fail", limit=100, window_seconds=60) is False


def test_auth_rate_limit_returns_429(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PER_MINUTE", 2)
    redis_service._memory_store.clear()
    # Three rapid login attempts with bad creds still count against IP bucket
    for _ in range(2):
        client.post("/api/v1/auth/login", json={"phone_number": "9876543210", "password": "x"})
    third = client.post("/api/v1/auth/login", json={"phone_number": "9876543210", "password": "x"})
    assert third.status_code == 429, third.text


def test_ready_endpoint_reports_checks():
    response = client.get("/api/v1/ping/ready")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "checks" in body
    assert "database" in body["checks"]
    assert "redis" in body["checks"]


def test_request_id_header_echoed():
    response = client.get("/api/v1/ping/", headers={"X-Request-ID": "stage2-test-id"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "stage2-test-id"
