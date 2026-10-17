"""Stage 2: validation, duplicate contact, JWT auth edge cases."""

from uuid import uuid4

from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.config import settings

client = TestClient(app)


def _register(phone: str, name: str = "Stage2") -> dict:
    reg = client.post(
        "/api/v1/auth/register",
        json={"phone_number": phone, "name": name, "password": "testpass123"},
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    verify = client.post(
        "/api/v1/auth/verify-otp",
        json={"phone_number": phone, "otp": "123456"},
    )
    assert verify.status_code == 200, verify.text
    return headers


def test_send_otp_rejects_invalid_phone():
    response = client.post("/api/v1/auth/send-otp", json={"phone_number": "abc"})
    assert response.status_code == 422


def test_login_rejects_invalid_phone():
    response = client.post(
        "/api/v1/auth/login",
        json={"phone_number": "12", "password": "testpass123"},
    )
    assert response.status_code == 422


def test_malformed_jwt_sub_returns_401():
    token = jwt.encode(
        {"sub": "not-a-uuid", "exp": 9999999999},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    response = client.get(
        "/api/v1/users/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_duplicate_contact_rejected():
    phone = f"5{uuid4().int % 10**9:09d}"
    headers = _register(phone)
    payload = {
        "name": "Mom",
        "phone_number": "9000111222",
        "relationship": "Mother",
        "ring_priority": 1,
    }
    first = client.post("/api/v1/users/contacts", headers=headers, json=payload)
    assert first.status_code == 201, first.text
    second = client.post("/api/v1/users/contacts", headers=headers, json=payload)
    assert second.status_code == 400, second.text
    assert "already" in second.json()["detail"].lower()


def test_contact_empty_name_rejected():
    phone = f"4{uuid4().int % 10**9:09d}"
    headers = _register(phone)
    response = client.post(
        "/api/v1/users/contacts",
        headers=headers,
        json={"name": "   ", "phone_number": "9000111333", "ring_priority": 1},
    )
    assert response.status_code == 422
