"""Account deletion — Play Store requirement."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import engine
from app.models.ai_feedback import AiFeedbackEvent
from app.services.ai_feedback_service import CONSENT_VERSION

client = TestClient(app)


@pytest.fixture(autouse=True)
def _ensure_feedback_table():
    AiFeedbackEvent.__table__.create(bind=engine, checkfirst=True)


def _register() -> tuple[dict, str]:
    phone = f"9{uuid4().int % 10**9:09d}"
    reg = client.post(
        "/api/v1/auth/register",
        json={"phone_number": phone, "name": "Delete Me", "password": "testpass123", "city": "Delhi"},
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    verify = client.post("/api/v1/auth/verify-otp", json={"phone_number": phone, "otp": "123456"})
    assert verify.status_code == 200, verify.text
    return headers, phone


def test_delete_account_removes_profile_and_contacts():
    headers, _phone = _register()
    add = client.post(
        "/api/v1/users/contacts",
        headers=headers,
        json={"name": "Mom", "phone_number": "9111222333", "relationship": "Mother", "ring_priority": 1},
    )
    assert add.status_code == 201, add.text

    fb = client.post(
        "/api/v1/ai/feedback",
        headers=headers,
        json={
            "event_id": str(uuid4()),
            "session_id": str(uuid4()),
            "model_version": "v1.0",
            "signal_type": "audio",
            "prediction_state": "SUSPICIOUS",
            "confidence": 70.0,
            "user_feedback": "CANCELLED",
            "outcome": "NO_ALERT",
            "consent_granted": True,
            "consent_version": CONSENT_VERSION,
        },
    )
    assert fb.status_code == 200, fb.text

    deleted = client.delete("/api/v1/users/me", headers=headers)
    assert deleted.status_code == 204, deleted.text

    after = client.get("/api/v1/users/profile", headers=headers)
    assert after.status_code in {401, 404}

    relogin = client.post(
        "/api/v1/auth/login",
        json={"phone_number": _phone, "password": "testpass123"},
    )
    assert relogin.status_code in {401, 404, 400}
