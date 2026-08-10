"""
OTP Service — phone number verification.

Provider selection via OTP_PROVIDER in config:
  "mock" — development only; always accepts 123456

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
# Format: { phone_number: (otp_code, expiry_timestamp) }
_mock_store: Dict[str, Tuple[str, float]] = {}


# ── Public API ────────────────────────────────────────────────────────────────

def send_otp(phone_number: str) -> bool:
    """
    Send a 6-digit OTP to the given phone number.
    Returns True if sent successfully, False on failure.
    """
    if settings.OTP_PROVIDER != "mock":
        logger.error("Unsupported OTP_PROVIDER=%s (only 'mock' is configured)", settings.OTP_PROVIDER)
        return False
    return _send_mock(phone_number)


def verify_otp(phone_number: str, otp: str) -> bool:
    """
    Verify the OTP entered by the user.
    Returns True if correct and not expired, False otherwise.
    """
    if settings.OTP_PROVIDER != "mock":
        logger.error("Unsupported OTP_PROVIDER=%s (only 'mock' is configured)", settings.OTP_PROVIDER)
        return False
    return _verify_mock(phone_number, otp)


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
