import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_register():
    response = client.post("/api/v1/auth/register", json={
        "phone_number": "9999999999",
        "name": "Test User",
        "password": "testpass123",
        "city": "Mumbai"
    })
    assert response.status_code == 201
    assert "access_token" in response.json()


def test_login():
    # Register first
    client.post("/api/v1/auth/register", json={
        "phone_number": "8888888888",
        "name": "Login Test",
        "password": "password123"
    })
    response = client.post("/api/v1/auth/login", json={
        "phone_number": "8888888888",
        "password": "password123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password():
    response = client.post("/api/v1/auth/login", json={
        "phone_number": "8888888888",
        "password": "wrongpassword"
    })
    assert response.status_code == 401
