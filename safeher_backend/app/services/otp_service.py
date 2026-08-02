"""
OTP Service — phone number verification.

Provider selection via OTP_PROVIDER in config:
  "twilio_verify" — production (Twilio Verify API)
  "mock"          — development only; always accepts 123456

Usage:
    send_otp("9876543210")          → True/False
    verify_otp("9876543210", "123456") → True/False
"""

import logging
import random
import string
import time
from typing import Dict, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

# ── In-memory OTP store (dev/mock only) ──────────────────────────────────────
# In production, Twilio Verify manages state server-side.
# This dict is only used by the mock provider.
# Format: { phone_number: (otp_code, expiry_timestamp) }
_mock_store: Dict[str, Tuple[str, float]] = {}


# ── Public API ────────────────────────────────────────────────────────────────

def send_otp(phone_number: str) -> bool:
    """
    Send a 6-digit OTP to the given phone number.
    Returns True if sent successfully, False on failure.
    """
    if settings.OTP_PROVIDER == "twilio_verify":
        return _send_via_twilio_verify(phone_number)
    else:
        return _send_mock(phone_number)


def verify_otp(phone_number: str, otp: str) -> bool:
    """
    Verify the OTP entered by the user.
    Returns True if correct and not expired, False otherwise.
    """
    if settings.OTP_PROVIDER == "twilio_verify":
        return _verify_via_twilio_verify(phone_number, otp)
    else:
        return _verify_mock(phone_number, otp)


# ── Twilio Verify ─────────────────────────────────────────────────────────────

def _send_via_twilio_verify(phone_number: str) -> bool:
    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        # Normalise to E.164
        e164 = _to_e164(phone_number)
        client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID) \
            .verifications.create(to=e164, channel="sms")
        logger.info(f"OTP sent via Twilio Verify to {phone_number}")
        return True
    except Exception as e:
        logger.error(f"Twilio Verify send failed: {e}")
        return False


def _verify_via_twilio_verify(phone_number: str, otp: str) -> bool:
    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        e164 = _to_e164(phone_number)
        result = client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID) \
            .verification_checks.create(to=e164, code=otp)
        return result.status == "approved"
    except Exception as e:
        logger.error(f"Twilio Verify check failed: {e}")
        return False


# ── Mock (development) ────────────────────────────────────────────────────────

def _send_mock(phone_number: str) -> bool:
    code = "".join(random.choices(string.digits, k=6))
    expiry = time.time() + (settings.OTP_EXPIRY_MINUTES * 60)
    _mock_store[phone_number] = (code, expiry)
    # In dev, log the OTP so developers can test without SMS
    logger.warning(f"[MOCK OTP] {phone_number} → {code}  (never log this in production)")
    return True


def _verify_mock(phone_number: str, otp: str) -> bool:
    # Dev shortcut: always accept 123456
    if otp == "123456":
        _mock_store.pop(phone_number, None)
        return True
    entry = _mock_store.get(phone_number)
    if not entry:
        return False
    code, expiry = entry
    if time.time() > expiry:
        _mock_store.pop(phone_number, None)
        logger.debug(f"OTP expired for {phone_number}")
        return False
    if otp == code:
        _mock_store.pop(phone_number, None)
        return True
    return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_e164(phone_number: str) -> str:
    """Normalise phone to E.164, using the configured country code as fallback."""
    phone = phone_number.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        return phone
    # Strip leading zeros
    phone = phone.lstrip("0")
    return f"+{settings.PHONE_COUNTRY_CODE}{phone}"
