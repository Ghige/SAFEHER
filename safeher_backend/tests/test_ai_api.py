"""Integration tests for /api/v1/ai endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

client = TestClient(app)

FIRE_SCORES = {
    "audio_score": 95.0,
    "movement_score": 95.0,
    "latitude": 19.076,
    "longitude": 72.8777,
    "is_night": True,
    "is_isolated": True,
}


@pytest.fixture
def enable_ai_auto_sos(monkeypatch):
    """Opt-in only for tests that intentionally exercise AI auto-fire."""
    monkeypatch.setattr(settings, "AI_AUTO_SOS_ENABLED", True)


def _register_verified(city: str = "Mumbai") -> dict:
    phone = f"9{uuid4().int % 10**9:09d}"
    reg = client.post(
        "/api/v1/auth/register",
        json={"phone_number": phone, "name": "AI Test", "password": "testpass123", "city": city},
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    verify = client.post("/api/v1/auth/verify-otp", json={"phone_number": phone, "otp": "123456"})
    assert verify.status_code == 200, verify.text
    return headers


def _add_contact(headers: dict) -> None:
    resp = client.post(
        "/api/v1/users/contacts",
        headers=headers,
        json={"name": "Mom", "phone_number": "9111222333", "relationship": "Mother", "ring_priority": 1},
    )
    assert resp.status_code == 201, resp.text


def test_ai_auto_sos_disabled_by_default():
    assert settings.AI_AUTO_SOS_ENABLED is False


def test_audio_sos_blocked_when_ai_auto_sos_disabled():
    """Stage 0: high scores must NOT create a real alert while flag is false."""
    assert settings.AI_AUTO_SOS_ENABLED is False
    headers = _register_verified()
    _add_contact(headers)
    resp = client.post("/api/v1/ai/audio-sos", headers=headers, json=FIRE_SCORES)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fusion"]["action"] == "fire_immediately"
    assert body["alert"] is None
    assert body.get("ai_auto_sos_blocked") is True
    assert body.get("reason") == "ai_auto_sos_disabled"

    active = client.get("/api/v1/alerts/active", headers=headers)
    assert active.status_code == 404


def test_movement_sos_fall_blocked_when_ai_auto_sos_disabled():
    assert settings.AI_AUTO_SOS_ENABLED is False
    headers = _register_verified()
    _add_contact(headers)
    resp = client.post(
        "/api/v1/ai/movement-sos",
        headers=headers,
        json={
            "movement_score": 10.0,
            "fall_detected": True,
            "latitude": 19.076,
            "longitude": 72.8777,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["alert"] is None
    assert body.get("ai_auto_sos_blocked") is True
    assert body.get("reason") == "ai_auto_sos_disabled"


def test_audio_sos_fires_alert_when_enabled(enable_ai_auto_sos):
    headers = _register_verified()
    _add_contact(headers)
    resp = client.post("/api/v1/ai/audio-sos", headers=headers, json=FIRE_SCORES)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fusion"]["action"] == "fire_immediately"
    assert body["alert"] is not None

    active = client.get("/api/v1/alerts/active", headers=headers)
    assert active.status_code == 200
    assert active.json()["trigger_type"] == "ai_audio"


def test_movement_sos_fall_fires_immediately_when_enabled(enable_ai_auto_sos):
    headers = _register_verified()
    _add_contact(headers)
    resp = client.post(
        "/api/v1/ai/movement-sos",
        headers=headers,
        json={
            "movement_score": 10.0,
            "fall_detected": True,
            "latitude": 19.076,
            "longitude": 72.8777,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reason"] == "fall_confirmed"
    assert body["alert"] is not None


def test_movement_sos_fusion_fires_alert_when_enabled(enable_ai_auto_sos):
    headers = _register_verified()
    _add_contact(headers)
    resp = client.post(
        "/api/v1/ai/movement-sos",
        headers=headers,
        json={**FIRE_SCORES, "fall_detected": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fusion"]["action"] == "fire_immediately"
    assert body["alert"] is not None


def test_audio_sos_low_score_no_alert():
    headers = _register_verified()
    _add_contact(headers)
    resp = client.post(
        "/api/v1/ai/audio-sos",
        headers=headers,
        json={"audio_score": 50.0, "movement_score": 0.0},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fusion"]["action"] == "nothing"
    assert body["alert"] is None


def test_audio_sos_confirm_window_no_alert():
    headers = _register_verified()
    _add_contact(headers)
    resp = client.post(
        "/api/v1/ai/audio-sos",
        headers=headers,
        json={"audio_score": 75.0, "movement_score": 65.0, "is_night": False, "is_isolated": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fusion"]["action"] == "confirm_30s"
    assert body["alert"] is None


def test_ai_invalid_score_rejected():
    headers = _register_verified()
    resp = client.post(
        "/api/v1/ai/audio-sos",
        headers=headers,
        json={"audio_score": 150.0, "movement_score": 0.0},
    )
    assert resp.status_code == 422


def test_ai_unpaired_coordinates_rejected():
    headers = _register_verified()
    resp = client.post(
        "/api/v1/ai/audio-sos",
        headers=headers,
        json={"audio_score": 80.0, "latitude": 19.0},
    )
    assert resp.status_code == 422


def test_ai_sos_requires_verified_user():
    phone = f"4{uuid4().int % 10**9:09d}"
    reg = client.post(
        "/api/v1/auth/register",
        json={"phone_number": phone, "name": "Unverified", "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    resp = client.post("/api/v1/ai/audio-sos", headers=headers, json=FIRE_SCORES)
    assert resp.status_code == 403


def test_duplicate_ai_sos_returns_trigger_error(enable_ai_auto_sos):
    headers = _register_verified()
    _add_contact(headers)
    first = client.post("/api/v1/ai/audio-sos", headers=headers, json=FIRE_SCORES)
    assert first.status_code == 200
    assert first.json()["alert"] is not None

    second = client.post("/api/v1/ai/audio-sos", headers=headers, json=FIRE_SCORES)
    assert second.status_code == 200
    body = second.json()
    assert body["alert"] is None
    assert "active alert" in body["trigger_error"].lower()


def test_ai_sos_without_contacts_returns_trigger_error(enable_ai_auto_sos):
    headers = _register_verified()
    resp = client.post("/api/v1/ai/audio-sos", headers=headers, json=FIRE_SCORES)
    assert resp.status_code == 200
    body = resp.json()
    assert body["alert"] is None
    assert "emergency contact" in body["trigger_error"].lower()


def test_confidence_query():
    headers = _register_verified()
    resp = client.post(
        "/api/v1/ai/confidence",
        headers=headers,
        json={"audio_score": 80.0, "movement_score": 70.0, "is_night": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Current DecisionContract (unchanged): 80 audio + 70 movement is fire_immediately.
    assert body["action"] == "fire_immediately"
    assert body["total_score"] >= 65

    fire = client.post(
        "/api/v1/ai/confidence",
        headers=headers,
        json={"audio_score": 95.0, "movement_score": 95.0, "is_night": True, "is_isolated": True},
    )
    assert fire.json()["action"] == "fire_immediately"
    assert fire.json()["activate_gps_stream"] is True


def test_latest_model_version():
    headers = _register_verified()
    resp = client.get("/api/v1/ai/models/latest?model_type=audio", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["model_type"] == "audio"
    assert body["version"] == "v1.0"
    assert body["status"] == "active"


def test_queue_dataset_sample_retired():
    headers = _register_verified()
    wav_bytes = b"RIFF" + (b"\x00" * 40)
    resp = client.post(
        "/api/v1/ai/datasets/queue",
        headers=headers,
        files={"audio": ("clip.wav", wav_bytes, "audio/wav")},
        data={
            "model_version": "v1.0",
            "ai_confidence": "87.5",
            "user_confirmation": "false",
            "label": "false_positive",
            "duration_seconds": "6.0",
            "features_json": '{"rms":0.12,"pitch_hz":400}',
        },
    )
    assert resp.status_code == 410
