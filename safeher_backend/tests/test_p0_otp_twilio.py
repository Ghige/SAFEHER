"""
Stage P0 — OTP provider unit tests (mocked HTTP). No live SMS. No AI SOS.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.security.production_guards import validate_runtime_config
from app.services import otp_service
from app.services.otp_service import reset_otp_state_for_tests, send_otp, verify_otp


def _prod_base(**overrides):
    base = {
        "ENVIRONMENT": "production",
        "DEBUG": False,
        "SECRET_KEY": "a" * 40 + "-prod-key-9f3c",
        "DATABASE_URL": "postgresql://safeher_app:complexPass99@db.internal:5432/safeher",
        "OTP_PROVIDER": "twilio",
        "OTP_ALLOW_DEV_SHORTCUT": False,
        "AI_AUTO_SOS_ENABLED": False,
        "ACCESS_TOKEN_EXPIRE_MINUTES": 60,
        "META_ACCESS_TOKEN": "meta-token",
        "REQUIRE_REDIS_IN_PRODUCTION": False,
        "REDIS_URL": "redis://localhost:6379",
        "TWILIO_ACCOUNT_SID": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "TWILIO_AUTH_TOKEN": "auth-token-value",
        "TWILIO_VERIFY_SERVICE_SID": "VAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_production_accepts_twilio_when_creds_present():
    warnings = validate_runtime_config(_prod_base())
    assert isinstance(warnings, list)


def test_production_rejects_twilio_without_creds():
    with pytest.raises(RuntimeError, match="TWILIO"):
        validate_runtime_config(
            _prod_base(
                TWILIO_ACCOUNT_SID="",
                TWILIO_AUTH_TOKEN="",
                TWILIO_VERIFY_SERVICE_SID="",
            )
        )


def test_production_rejects_unimplemented_otp_provider():
    with pytest.raises(RuntimeError, match="not implemented"):
        validate_runtime_config(_prod_base(OTP_PROVIDER="msg91"))


def test_production_rejects_dev_shortcut_flag():
    with pytest.raises(RuntimeError, match="OTP_ALLOW_DEV_SHORTCUT"):
        validate_runtime_config(_prod_base(OTP_ALLOW_DEV_SHORTCUT=True))


def test_twilio_send_verify_success(monkeypatch):
    reset_otp_state_for_tests()
    monkeypatch.setattr(
        otp_service,
        "settings",
        SimpleNamespace(
            OTP_PROVIDER="twilio",
            OTP_MAX_VERIFY_ATTEMPTS=5,
            OTP_EXPIRY_MINUTES=10,
            OTP_ALLOW_DEV_SHORTCUT=False,
            PHONE_COUNTRY_CODE="91",
            DEBUG=False,
            ENVIRONMENT="development",
            TWILIO_ACCOUNT_SID="ACtest",
            TWILIO_AUTH_TOKEN="token",
            TWILIO_VERIFY_SERVICE_SID="VAtest",
        ),
    )

    send_resp = MagicMock()
    send_resp.is_success = True
    send_resp.status_code = 201
    send_resp.text = "{}"

    check_resp = MagicMock()
    check_resp.is_success = True
    check_resp.status_code = 200
    check_resp.json.return_value = {"status": "approved"}
    check_resp.text = '{"status":"approved"}'

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.side_effect = [send_resp, check_resp]

    with patch("app.services.otp_service.httpx.Client", return_value=mock_client):
        assert send_otp("+919876543210") is True
        assert verify_otp("+919876543210", "654321") is True

    assert mock_client.post.call_count == 2


def test_twilio_send_fails_without_config(monkeypatch):
    reset_otp_state_for_tests()
    monkeypatch.setattr(
        otp_service,
        "settings",
        SimpleNamespace(
            OTP_PROVIDER="twilio",
            OTP_MAX_VERIFY_ATTEMPTS=5,
            PHONE_COUNTRY_CODE="91",
            DEBUG=False,
            ENVIRONMENT="development",
            TWILIO_ACCOUNT_SID="",
            TWILIO_AUTH_TOKEN="",
            TWILIO_VERIFY_SERVICE_SID="",
        ),
    )
    assert send_otp("+919876543210") is False
