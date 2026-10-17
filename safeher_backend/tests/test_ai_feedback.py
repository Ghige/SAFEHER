"""AI feedback pipeline — metadata only, never gold, never auto-SOS."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import engine
from app.models.ai_feedback import AiFeedbackEvent
from app.services.ai_feedback_service import CONSENT_VERSION, classify_feedback, sanitize_features

client = TestClient(app)


@pytest.fixture(autouse=True)
def _ensure_feedback_table():
    AiFeedbackEvent.__table__.create(bind=engine, checkfirst=True)


def _register_verified() -> dict:
    phone = f"9{uuid4().int % 10**9:09d}"
    reg = client.post(
        "/api/v1/auth/register",
        json={"phone_number": phone, "name": "FB Test", "password": "testpass123", "city": "Pune"},
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    verify = client.post("/api/v1/auth/verify-otp", json={"phone_number": phone, "otp": "123456"})
    assert verify.status_code == 200, verify.text
    return headers


def _payload(**overrides):
    body = {
        "event_id": str(uuid4()),
        "session_id": str(uuid4()),
        "model_version": "v1.0",
        "signal_type": "audio",
        "prediction_state": "EMERGENCY",
        "confidence": 91.5,
        "user_feedback": "CANCELLED",
        "outcome": "NO_ALERT",
        "consent_granted": True,
        "consent_version": CONSENT_VERSION,
        "features": {"rms": 0.12, "pitch_hz": 400.0},
    }
    body.update(overrides)
    return body


def test_classify_cancel_is_hard_negative_candidate():
    cat, status = classify_feedback(user_feedback="CANCELLED", prediction_state="EMERGENCY")
    assert cat == "AI_FALSE_POSITIVE_CANDIDATE"
    assert status == "HARD_NEGATIVE_CANDIDATE"


def test_classify_confirm_is_distress_candidate():
    cat, status = classify_feedback(
        user_feedback="CONFIRMED_EMERGENCY", prediction_state="EMERGENCY"
    )
    assert cat == "USER_CONFIRMED_DISTRESS"
    assert status == "DISTRESS_CANDIDATE"


def test_sanitize_rejects_location_and_transcript():
    with pytest.raises(ValueError):
        sanitize_features({"latitude": 19.07, "rms": 0.1})
    with pytest.raises(ValueError):
        sanitize_features({"transcript": "help"})


def test_wav_queue_retired():
    headers = _register_verified()
    resp = client.post(
        "/api/v1/ai/datasets/queue",
        headers=headers,
        files={"audio": ("clip.wav", b"RIFF" + (b"\x00" * 40), "audio/wav")},
        data={"model_version": "v1.0"},
    )
    assert resp.status_code == 410


def test_feedback_requires_consent():
    headers = _register_verified()
    resp = client.post(
        "/api/v1/ai/feedback",
        headers=headers,
        json=_payload(consent_granted=False),
    )
    assert resp.status_code == 403


def test_feedback_cancel_is_not_gold():
    headers = _register_verified()
    resp = client.post("/api/v1/ai/feedback", headers=headers, json=_payload())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidate_category"] == "AI_FALSE_POSITIVE_CANDIDATE"
    assert body["fp_fn_status"] == "HARD_NEGATIVE_CANDIDATE"
    assert body["review_status"] == "UNREVIEWED"
    assert body["gold_eligible"] is False


def test_feedback_confirm_distress_not_gold():
    headers = _register_verified()
    resp = client.post(
        "/api/v1/ai/feedback",
        headers=headers,
        json=_payload(user_feedback="CONFIRMED_EMERGENCY", outcome="MANUAL_SOS_OPENED"),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidate_category"] == "USER_CONFIRMED_DISTRESS"
    assert body["gold_eligible"] is False


def test_feedback_idempotent_event_id():
    headers = _register_verified()
    payload = _payload()
    first = client.post("/api/v1/ai/feedback", headers=headers, json=payload)
    second = client.post("/api/v1/ai/feedback", headers=headers, json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["event_id"] == second.json()["event_id"]


def test_feedback_rejects_phone_feature():
    headers = _register_verified()
    resp = client.post(
        "/api/v1/ai/feedback",
        headers=headers,
        json=_payload(features={"phone": "9876543210", "rms": 0.1}),
    )
    assert resp.status_code == 400
