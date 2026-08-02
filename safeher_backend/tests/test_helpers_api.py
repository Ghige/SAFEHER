"""Integration tests for /api/v1/helpers endpoints."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.alert import Alert

client = TestClient(app)


def _register(phone: str | None = None, city: str = "Mumbai", name: str = "User") -> tuple[str, dict]:
    phone = phone or f"8{uuid4().int % 10**9:09d}"
    reg = client.post(
        "/api/v1/auth/register",
        json={"phone_number": phone, "name": name, "password": "testpass123", "city": city},
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    verify = client.post("/api/v1/auth/verify-otp", json={"phone_number": phone, "otp": "123456"})
    assert verify.status_code == 200, verify.text
    return phone, headers


def _add_contact(headers: dict) -> None:
    resp = client.post(
        "/api/v1/users/contacts",
        headers=headers,
        json={"name": "Mom", "phone_number": "9111222333", "relationship": "Mother", "ring_priority": 1},
    )
    assert resp.status_code == 201, resp.text


def _trigger_sos(headers: dict) -> str:
    resp = client.post(
        "/api/v1/alerts/trigger",
        headers=headers,
        json={"trigger_type": "manual", "latitude": 19.076, "longitude": 72.8777},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _escalate_alert(alert_id: str) -> None:
    db = SessionLocal()
    try:
        alert = db.query(Alert).filter(Alert.id == UUID(alert_id)).first()
        assert alert is not None
        alert.status = "escalated"
        db.commit()
    finally:
        db.close()


def _sos_with_helper(city: str | None = None) -> tuple[dict, dict, str, str]:
    """Return victim headers, helper headers, alert_id, helper record id."""
    city = city or f"TestCity{uuid4().hex[:8]}"
    _, helper_headers = _register(name="Helper", city=city)
    _, victim_headers = _register(name="Victim", city=city)
    _add_contact(victim_headers)
    alert_id = _trigger_sos(victim_headers)

    nearby = client.get(f"/api/v1/helpers/nearby?alert_id={alert_id}", headers=victim_headers)
    assert nearby.status_code == 200, nearby.text
    helpers = nearby.json()
    assert len(helpers) >= 1
    return victim_headers, helper_headers, alert_id, helpers[0]["id"]


def test_helper_respond_on_escalated_alert():
    """H-01: helpers can respond while alert is escalated (dead switch)."""
    city = f"TestCity{uuid4().hex[:8]}"
    _, helper_headers = _register(name="Helper", city=city)

    _, victim_headers = _register(name="Victim", city=city)
    _add_contact(victim_headers)
    alert_id = _trigger_sos(victim_headers)

    _escalate_alert(alert_id)

    resp = client.post(f"/api/v1/helpers/respond/{alert_id}", headers=helper_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "responding"


def test_nearby_helpers_alert_owner_only():
    victim_headers, helper_headers, alert_id, _ = _sos_with_helper()
    resp = client.get(f"/api/v1/helpers/nearby?alert_id={alert_id}", headers=helper_headers)
    assert resp.status_code == 404


def test_nearby_helpers_lists_notified():
    victim_headers, _, alert_id, _ = _sos_with_helper()
    resp = client.get(f"/api/v1/helpers/nearby?alert_id={alert_id}", headers=victim_headers)
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "notified"
    assert resp.json()[0]["identity_revealed"] is False
    assert resp.json()[0]["name"] is None


def test_no_helpers_when_different_city():
    city = f"TestCity{uuid4().hex[:8]}"
    _, victim_headers = _register(name="Victim", city=city)
    _add_contact(victim_headers)
    _register(name="Helper", city=f"Other{uuid4().hex[:8]}")
    alert_id = _trigger_sos(victim_headers)
    resp = client.get(f"/api/v1/helpers/nearby?alert_id={alert_id}", headers=victim_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_helper_respond_and_approve():
    victim_headers, helper_headers, alert_id, helper_id = _sos_with_helper()
    resp = client.post(f"/api/v1/helpers/respond/{alert_id}", headers=helper_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "responding"

    approve = client.post(f"/api/v1/helpers/approve/{helper_id}", headers=victim_headers)
    assert approve.status_code == 200
    assert approve.json()["identity_revealed"] is True
    assert approve.json()["name"] == "Helper"


def test_duplicate_helper_respond_rejected():
    victim_headers, helper_headers, alert_id, _ = _sos_with_helper()
    first = client.post(f"/api/v1/helpers/respond/{alert_id}", headers=helper_headers)
    assert first.status_code == 200
    second = client.post(f"/api/v1/helpers/respond/{alert_id}", headers=helper_headers)
    assert second.status_code == 404


def test_unauthorized_helper_respond():
    victim_headers, _, alert_id, _ = _sos_with_helper()
    _, stranger_headers = _register(name="Stranger", city=f"Other{uuid4().hex[:8]}")
    resp = client.post(f"/api/v1/helpers/respond/{alert_id}", headers=stranger_headers)
    assert resp.status_code == 404


def test_alert_owner_cannot_respond():
    victim_headers, _, alert_id, _ = _sos_with_helper()
    resp = client.post(f"/api/v1/helpers/respond/{alert_id}", headers=victim_headers)
    assert resp.status_code == 403


def test_block_helper_unauthorized():
    victim_headers, helper_headers, alert_id, helper_id = _sos_with_helper()
    resp = client.post(f"/api/v1/helpers/block/{helper_id}", headers=helper_headers)
    assert resp.status_code == 403


def test_block_helper_by_owner():
    victim_headers, _, alert_id, helper_id = _sos_with_helper()
    resp = client.post(f"/api/v1/helpers/block/{helper_id}", headers=victim_headers)
    assert resp.status_code == 204


def test_respond_rejected_after_cancel():
    victim_headers, helper_headers, alert_id, _ = _sos_with_helper()
    cancel = client.post(f"/api/v1/alerts/cancel/{alert_id}", headers=victim_headers)
    assert cancel.status_code == 200
    resp = client.post(f"/api/v1/helpers/respond/{alert_id}", headers=helper_headers)
    assert resp.status_code == 404


def test_approve_rejected_after_cancel():
    victim_headers, helper_headers, alert_id, helper_id = _sos_with_helper()
    client.post(f"/api/v1/helpers/respond/{alert_id}", headers=helper_headers)
    client.post(f"/api/v1/alerts/cancel/{alert_id}", headers=victim_headers)
    resp = client.post(f"/api/v1/helpers/approve/{helper_id}", headers=victim_headers)
    assert resp.status_code == 404


def test_helper_mutations_require_verified_user():
    city = f"TestCity{uuid4().hex[:8]}"
    phone = f"5{uuid4().int % 10**9:09d}"
    reg = client.post(
        "/api/v1/auth/register",
        json={"phone_number": phone, "name": "Unverified", "password": "testpass123", "city": city},
    )
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    resp = client.post(f"/api/v1/helpers/respond/{uuid4()}", headers=headers)
    assert resp.status_code == 403


def test_blocklist_crud():
    _, headers = _register()
    add = client.post("/api/v1/helpers/blocklist", headers=headers, json={"blocked_phone": "9999888777"})
    assert add.status_code == 201
    entry_id = add.json()["id"]

    listing = client.get("/api/v1/helpers/blocklist", headers=headers)
    assert listing.status_code == 200
    assert any(e["id"] == entry_id for e in listing.json())

    delete = client.delete(f"/api/v1/helpers/blocklist/{entry_id}", headers=headers)
    assert delete.status_code == 204
