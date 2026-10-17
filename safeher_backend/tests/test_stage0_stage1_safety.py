"""Stage 0/1 tests: AI_AUTO_SOS kill-switch + OTP attempt limits."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.services import otp_service

client = TestClient(app)


def test_settings_ai_auto_sos_defaults_false():
    assert settings.AI_AUTO_SOS_ENABLED is False


def test_otp_max_verify_attempts_locks(monkeypatch):
    otp_service.reset_otp_state_for_tests()
    monkeypatch.setattr(settings, "OTP_MAX_VERIFY_ATTEMPTS", 3)
    phone = f"8{uuid4().int % 10**9:09d}"

    assert otp_service.send_otp(phone) is True
    # Wrong codes until lock
    assert otp_service.verify_otp(phone, "000000") is False
    assert otp_service.verify_otp(phone, "000001") is False
    assert otp_service.verify_otp(phone, "000002") is False
    # Locked — even correct-looking attempts fail
    assert otp_service.verify_otp(phone, "000003") is False
    # Dev shortcut also blocked while locked
    assert otp_service.verify_otp(phone, "123456") is False

    # New send resets attempts
    assert otp_service.send_otp(phone) is True
    assert otp_service.verify_otp(phone, "123456") is True


def _register_verified(phone: str, name: str) -> dict:
    reg = client.post(
        "/api/v1/auth/register",
        json={"phone_number": phone, "name": name, "password": "testpass123"},
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    verify = client.post("/api/v1/auth/verify-otp", json={"phone_number": phone, "otp": "123456"})
    assert verify.status_code == 200, verify.text
    return headers


def test_manual_sos_rejected_without_contacts():
    """Backend refuses SOS when the user has zero emergency contacts."""
    assert settings.AI_AUTO_SOS_ENABLED is False
    phone = f"6{uuid4().int % 10**9:09d}"
    headers = _register_verified(phone, "No Contacts")
    trigger = client.post(
        "/api/v1/alerts/trigger",
        headers=headers,
        json={"trigger_type": "manual", "latitude": 19.07, "longitude": 72.87},
    )
    assert trigger.status_code == 400, trigger.text
    assert "contact" in trigger.json()["detail"].lower()


def test_manual_sos_still_works_with_ai_auto_disabled():
    """Manual /alerts/trigger must not be gated by AI_AUTO_SOS_ENABLED."""
    assert settings.AI_AUTO_SOS_ENABLED is False
    phone = f"7{uuid4().int % 10**9:09d}"
    headers = _register_verified(phone, "Manual SOS")

    contact = client.post(
        "/api/v1/users/contacts",
        headers=headers,
        json={"name": "Dad", "phone_number": "9000111222", "relationship": "Father", "ring_priority": 1},
    )
    assert contact.status_code == 201, contact.text

    trigger = client.post(
        "/api/v1/alerts/trigger",
        headers=headers,
        json={"trigger_type": "manual", "latitude": 19.07, "longitude": 72.87},
    )
    assert trigger.status_code == 201, trigger.text
    body = trigger.json()
    assert body["trigger_type"] == "manual"
    assert body["status"] == "active"
    assert "id" in body

    # Duplicate blocked
    dup = client.post(
        "/api/v1/alerts/trigger",
        headers=headers,
        json={"trigger_type": "manual", "latitude": 19.07, "longitude": 72.87},
    )
    assert dup.status_code == 409, dup.text