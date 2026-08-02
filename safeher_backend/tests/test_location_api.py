"""Integration tests for /api/v1/location endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.location import create_track_token
from app.main import app

client = TestClient(app)


def _register_verify_contact_and_alert() -> tuple[dict, str]:
    phone = f"8{uuid4().int % 10**9:09d}"
    reg = client.post(
        "/api/v1/auth/register",
        json={"phone_number": phone, "name": "Loc Test", "password": "testpass123", "city": "Mumbai"},
    )
    assert reg.status_code == 201
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    client.post("/api/v1/auth/verify-otp", json={"phone_number": phone, "otp": "123456"})
    client.post(
        "/api/v1/users/contacts",
        headers=headers,
        json={"name": "Mom", "phone_number": "9111222333", "relationship": "Mother", "ring_priority": 1},
    )
    alert = client.post(
        "/api/v1/alerts/trigger",
        headers=headers,
        json={"trigger_type": "manual", "latitude": 19.076, "longitude": 72.8777},
    )
    assert alert.status_code == 201
    return headers, alert.json()["id"]


def test_location_update_during_active_alert():
    headers, alert_id = _register_verify_contact_and_alert()
    resp = client.post(
        "/api/v1/location/update",
        headers=headers,
        json={"alert_id": alert_id, "latitude": 19.08, "longitude": 72.88},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "location updated"

    active = client.get("/api/v1/alerts/active", headers=headers)
    assert active.json()["latitude"] == pytest.approx(19.08)


def test_location_update_rejects_invalid_coordinates():
    headers, alert_id = _register_verify_contact_and_alert()
    resp = client.post(
        "/api/v1/location/update",
        headers=headers,
        json={"alert_id": alert_id, "latitude": 999, "longitude": 72.88},
    )
    assert resp.status_code == 422


def test_location_update_requires_active_alert():
    phone = f"7{uuid4().int % 10**9:09d}"
    reg = client.post(
        "/api/v1/auth/register",
        json={"phone_number": phone, "name": "No Alert", "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    client.post("/api/v1/auth/verify-otp", json={"phone_number": phone, "otp": "123456"})
    resp = client.post(
        "/api/v1/location/update",
        headers=headers,
        json={"alert_id": str(uuid4()), "latitude": 19.0, "longitude": 72.0},
    )
    assert resp.status_code == 404


def test_location_update_rejects_other_users_alert():
    headers_a, alert_id = _register_verify_contact_and_alert()
    phone_b = f"6{uuid4().int % 10**9:09d}"
    reg_b = client.post(
        "/api/v1/auth/register",
        json={"phone_number": phone_b, "name": "B", "password": "testpass123"},
    )
    headers_b = {"Authorization": f"Bearer {reg_b.json()['access_token']}"}
    client.post("/api/v1/auth/verify-otp", json={"phone_number": phone_b, "otp": "123456"})
    resp = client.post(
        "/api/v1/location/update",
        headers=headers_b,
        json={"alert_id": alert_id, "latitude": 19.0, "longitude": 72.0},
    )
    assert resp.status_code == 404


def test_track_link_and_live_view():
    headers, alert_id = _register_verify_contact_and_alert()
    link = client.get(f"/api/v1/location/track-link/{alert_id}", headers=headers)
    assert link.status_code == 200
    assert "track_url" in link.json()

    token = create_track_token(alert_id)
    live = client.get(f"/api/v1/location/live?token={token}")
    assert live.status_code == 200
    body = live.json()
    assert body["status"] == "active"
    assert body["latitude"] is not None


def test_live_hides_coords_after_cancel():
    headers, alert_id = _register_verify_contact_and_alert()
    token = create_track_token(alert_id)
    client.post(f"/api/v1/alerts/cancel/{alert_id}", headers=headers)
    live = client.get(f"/api/v1/location/live?token={token}")
    assert live.status_code == 200
    body = live.json()
    assert body["status"] == "cancelled"
    assert body["latitude"] is None
    assert body["longitude"] is None


def test_track_link_not_available_after_cancel():
    headers, alert_id = _register_verify_contact_and_alert()
    client.post(f"/api/v1/alerts/cancel/{alert_id}", headers=headers)
    link = client.get(f"/api/v1/location/track-link/{alert_id}", headers=headers)
    assert link.status_code == 404
