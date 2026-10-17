"""Integration tests for /api/v1/alerts endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _register_and_verify(phone: str | None = None, password: str = "testpass123") -> tuple[str, dict]:
    phone = phone or f"8{uuid4().int % 10**9:09d}"
    reg = client.post(
        "/api/v1/auth/register",
        json={"phone_number": phone, "name": "Alert Test", "password": password, "city": "Mumbai"},
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    verify = client.post("/api/v1/auth/verify-otp", json={"phone_number": phone, "otp": "123456"})
    assert verify.status_code == 200, verify.text
    return phone, headers


def _add_contact(headers: dict, phone: str = "9111222333") -> None:
    resp = client.post(
        "/api/v1/users/contacts",
        headers=headers,
        json={"name": "Mom", "phone_number": phone, "relationship": "Mother", "ring_priority": 1},
    )
    assert resp.status_code == 201, resp.text


def test_trigger_requires_verified_user():
    phone = f"7{uuid4().int % 10**9:09d}"
    reg = client.post(
        "/api/v1/auth/register",
        json={"phone_number": phone, "name": "Unverified", "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    resp = client.post(
        "/api/v1/alerts/trigger",
        headers=headers,
        json={"trigger_type": "manual", "latitude": 19.0, "longitude": 72.0},
    )
    assert resp.status_code == 403


def test_trigger_requires_emergency_contact():
    _, headers = _register_and_verify()
    resp = client.post(
        "/api/v1/alerts/trigger",
        headers=headers,
        json={"trigger_type": "manual", "latitude": 19.0, "longitude": 72.0},
    )
    assert resp.status_code == 400
    assert "emergency contact" in resp.json()["detail"].lower()


def test_trigger_cancel_active_history_flow():
    _, headers = _register_and_verify()
    _add_contact(headers)

    trigger = client.post(
        "/api/v1/alerts/trigger",
        headers=headers,
        json={"trigger_type": "manual", "latitude": 19.076, "longitude": 72.8777},
    )
    assert trigger.status_code == 201, trigger.text
    alert_id = trigger.json()["id"]
    assert trigger.json()["status"] == "active"
    assert trigger.json()["latitude"] == pytest.approx(19.076)
    assert "whatsapp_sent_count" in trigger.json()
    assert "whatsapp_all_delivered" in trigger.json()

    active = client.get("/api/v1/alerts/active", headers=headers)
    assert active.status_code == 200
    assert active.json()["id"] == alert_id

    dup = client.post(
        "/api/v1/alerts/trigger",
        headers=headers,
        json={"trigger_type": "manual", "latitude": 19.0, "longitude": 72.0},
    )
    assert dup.status_code == 409

    ping = client.post(f"/api/v1/alerts/ping/{alert_id}", headers=headers)
    assert ping.status_code == 200

    cancel = client.post(f"/api/v1/alerts/cancel/{alert_id}", headers=headers)
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    no_active = client.get("/api/v1/alerts/active", headers=headers)
    assert no_active.status_code == 404

    history = client.get("/api/v1/alerts/history", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) >= 1


def test_invalid_trigger_type_rejected():
    _, headers = _register_and_verify()
    _add_contact(headers)
    resp = client.post(
        "/api/v1/alerts/trigger",
        headers=headers,
        json={"trigger_type": "invalid_type", "latitude": 19.0, "longitude": 72.0},
    )
    assert resp.status_code == 422


def test_add_contact_invalid_phone_rejected():
    _, headers = _register_and_verify()
    resp = client.post(
        "/api/v1/users/contacts",
        headers=headers,
        json={"name": "Mom", "phone_number": "not-a-phone", "relationship": "Mother", "ring_priority": 1},
    )
    assert resp.status_code == 422
