"""Shared pytest fixtures for SafeHer backend integration tests."""

import pytest

from app.config import settings
from app.services import redis_service


@pytest.fixture(autouse=True)
def _integration_test_limits(monkeypatch):
    """Avoid auth/alert rate-limit flakes when many users register in one test."""
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PER_MINUTE", 1000)
    monkeypatch.setattr(settings, "RATE_LIMIT_ALERT_PER_MINUTE", 1000)
    redis_service._memory_store.clear()
    yield
    redis_service._memory_store.clear()
