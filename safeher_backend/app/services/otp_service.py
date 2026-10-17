"""
OTP Service — phone number verification.

Providers (OTP_PROVIDER):
  "mock"   — development only; stored code OR 123456 when OTP_ALLOW_DEV_SHORTCUT
  "twilio" — Twilio Verify SMS (requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
             TWILIO_VERIFY_SERVICE_SID)

Production/staging refuse mock (production_guards). Real SMS E2E still needs
live Twilio credentials + a phone — do not claim delivery without that evidence.
"""

from __future__ import annotations

import logging
import random
import string
import time
from typing import Dict, Tuple

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

IMPLEMENTED_OTP_PROVIDERS = frozenset({"mock", "twilio"})

# Format: { phone_number: (otp_code, expiry_timestamp) } — mock only
_mock_store: Dict[str, Tuple[str, float]] = {}
_verify_attempts: Dict[str, int] = {}


def reset_otp_state_for_tests() -> None:
    """Clear in-memory OTP state (unit/integration tests only)."""
    _mock_store.clear()
    _verify_attempts.clear()


def _provider() -> str:
    return (settings.OTP_PROVIDER or "mock").strip().lower()


def _phone_suffix(phone_number: str) -> str:
    return phone_number[-4:] if len(phone_number) >= 4 else "****"


def _to_e164(phone_number: str) -> str:
    """Normalize to E.164 with leading + for Twilio Verify."""
    phone = phone_number.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        return phone
    phone = phone.lstrip("0")
    cc = (settings.PHONE_COUNTRY_CODE or "91").strip()
    if phone.startswith(cc) and len(phone) > len(cc):
        return f"+{phone}"
    return f"+{cc}{phone}"


def send_otp(phone_number: str) -> bool:
    """
    Send a 6-digit OTP to the given phone number.
    Returns True if sent successfully, False on failure.
    """
    from app.security.production_guards import is_production_like

    provider = _provider()
    if is_production_like(settings) and provider == "mock":
        logger.error("Refusing mock OTP send in production/staging")
        return False
    if provider not in IMPLEMENTED_OTP_PROVIDERS:
        logger.error(
            "Unsupported OTP_PROVIDER=%s (implemented: %s)",
            provider,
            ", ".join(sorted(IMPLEMENTED_OTP_PROVIDERS)),
        )
        return False
    if provider == "twilio":
        return _send_twilio(phone_number)
    return _send_mock(phone_number)


def verify_otp(phone_number: str, otp: str) -> bool:
    """
    Verify the OTP entered by the user.
    Returns True if correct and not expired, False otherwise.
    """
    from app.security.production_guards import is_production_like

    provider = _provider()
    if is_production_like(settings) and provider == "mock":
        logger.error("Refusing mock OTP verify in production/staging")
        return False
    if provider not in IMPLEMENTED_OTP_PROVIDERS:
        logger.error(
            "Unsupported OTP_PROVIDER=%s (implemented: %s)",
            provider,
            ", ".join(sorted(IMPLEMENTED_OTP_PROVIDERS)),
        )
        return False
    if provider == "twilio":
        return _verify_twilio(phone_number, otp)
    return _verify_mock(phone_number, otp)


def _twilio_configured() -> bool:
    return bool(
        (settings.TWILIO_ACCOUNT_SID or "").strip()
        and (settings.TWILIO_AUTH_TOKEN or "").strip()
        and (settings.TWILIO_VERIFY_SERVICE_SID or "").strip()
    )


def _send_twilio(phone_number: str) -> bool:
    if not _twilio_configured():
        logger.error(
            "Twilio Verify not configured: set TWILIO_ACCOUNT_SID, "
            "TWILIO_AUTH_TOKEN, TWILIO_VERIFY_SERVICE_SID"
        )
        return False

    to = _to_e164(phone_number)
    sid = settings.TWILIO_VERIFY_SERVICE_SID.strip()
    url = f"https://verify.twilio.com/v2/Services/{sid}/Verifications"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                url,
                data={"To": to, "Channel": "sms"},
                auth=(
                    settings.TWILIO_ACCOUNT_SID.strip(),
                    settings.TWILIO_AUTH_TOKEN.strip(),
                ),
            )
    except Exception as exc:
        logger.error("Twilio Verify send network error: %s", type(exc).__name__)
        return False

    if response.is_success:
        _verify_attempts[phone_number] = 0
        logger.info(
            "Twilio Verify SMS requested phone_suffix=%s status=%s",
            _phone_suffix(phone_number),
            response.status_code,
        )
        return True

    logger.error(
        "Twilio Verify send failed phone_suffix=%s status=%s body=%s",
        _phone_suffix(phone_number),
        response.status_code,
        response.text[:300],
    )
    return False


def _verify_twilio(phone_number: str, otp: str) -> bool:
    attempts = _verify_attempts.get(phone_number, 0)
    max_attempts = int(settings.OTP_MAX_VERIFY_ATTEMPTS)
    if attempts >= max_attempts:
        logger.warning("OTP verify locked after %s failed attempts", attempts)
        return False

    if not _twilio_configured():
        logger.error("Twilio Verify not configured for verify")
        return False

    to = _to_e164(phone_number)
    sid = settings.TWILIO_VERIFY_SERVICE_SID.strip()
    url = f"https://verify.twilio.com/v2/Services/{sid}/VerificationCheck"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                url,
                data={"To": to, "Code": otp},
                auth=(
                    settings.TWILIO_ACCOUNT_SID.strip(),
                    settings.TWILIO_AUTH_TOKEN.strip(),
                ),
            )
    except Exception as exc:
        logger.error("Twilio Verify check network error: %s", type(exc).__name__)
        _verify_attempts[phone_number] = attempts + 1
        return False

    if not response.is_success:
        _verify_attempts[phone_number] = attempts + 1
        logger.info(
            "Twilio Verify check rejected phone_suffix=%s status=%s",
            _phone_suffix(phone_number),
            response.status_code,
        )
        return False

    try:
        payload = response.json()
    except Exception:
        _verify_attempts[phone_number] = attempts + 1
        return False

    status = (payload.get("status") or "").lower()
    if status == "approved":
        _verify_attempts.pop(phone_number, None)
        logger.info("Twilio Verify approved phone_suffix=%s", _phone_suffix(phone_number))
        return True

    _verify_attempts[phone_number] = attempts + 1
    return False


def _send_mock(phone_number: str) -> bool:
    code = "".join(random.choices(string.digits, k=6))
    expiry = time.time() + (settings.OTP_EXPIRY_MINUTES * 60)
    _mock_store[phone_number] = (code, expiry)
    _verify_attempts[phone_number] = 0
    from app.security.production_guards import is_production_like

    if settings.DEBUG and not is_production_like(settings):
        logger.warning(
            "[MOCK OTP] phone_suffix=%s code=%s (dev only)",
            _phone_suffix(phone_number),
            code,
        )
    else:
        logger.info("[MOCK OTP] issued code_length=%s (code not logged)", len(code))
    return True


def _verify_mock(phone_number: str, otp: str) -> bool:
    attempts = _verify_attempts.get(phone_number, 0)
    max_attempts = int(settings.OTP_MAX_VERIFY_ATTEMPTS)
    if attempts >= max_attempts:
        logger.warning("OTP verify locked after %s failed attempts", attempts)
        return False

    from app.security.production_guards import is_production_like

    if (
        otp == "123456"
        and settings.OTP_ALLOW_DEV_SHORTCUT
        and not is_production_like(settings)
    ):
        _mock_store.pop(phone_number, None)
        _verify_attempts.pop(phone_number, None)
        return True

    entry = _mock_store.get(phone_number)
    if not entry:
        _verify_attempts[phone_number] = attempts + 1
        return False

    code, expiry = entry
    if time.time() > expiry:
        _mock_store.pop(phone_number, None)
        _verify_attempts[phone_number] = attempts + 1
        logger.debug("OTP expired for phone_suffix=%s", _phone_suffix(phone_number))
        return False

    if otp == code:
        _mock_store.pop(phone_number, None)
        _verify_attempts.pop(phone_number, None)
        return True

    _verify_attempts[phone_number] = attempts + 1
    return False
