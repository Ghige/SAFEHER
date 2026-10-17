from uuid import uuid4

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _unique_phone() -> str:
    return f"9{uuid4().int % 10**9:09d}"


def test_register():
    phone = _unique_phone()
    response = client.post("/api/v1/auth/register", json={
        "phone_number": phone,
        "name": "Test User",
        "password": "testpass123",
        "city": "Mumbai"
    })
    assert response.status_code == 201, response.text
    assert "access_token" in response.json()


def test_login():
    phone = _unique_phone()
    client.post("/api/v1/auth/register", json={
        "phone_number": phone,
        "name": "Login Test",
        "password": "password123"
    })
    response = client.post("/api/v1/auth/login", json={
        "phone_number": phone,
        "password": "password123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password():
    phone = _unique_phone()
    client.post("/api/v1/auth/register", json={
        "phone_number": phone,
        "name": "Wrong Pass",
        "password": "password123"
    })
    response = client.post("/api/v1/auth/login", json={
        "phone_number": phone,
        "password": "wrongpassword"
    })
    assert response.status_code == 401
