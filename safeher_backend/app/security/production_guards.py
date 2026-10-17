"""
Stage 9 — production configuration guards.

Call validate_runtime_config() at process start. Raises RuntimeError when
production (or staging-strict) settings would be unsafe.

Never enables AI_AUTO_SOS. Never sends alerts.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

_INSECURE_SECRET_MARKERS = (
    "change-this",
    "changeme",
    "dev-secret",
    "test-secret",
    "password",
)


def is_production_like(settings: "Settings") -> bool:
    env = (settings.ENVIRONMENT or "").strip().lower()
    return env in {"production", "prod", "staging"}


def validate_runtime_config(settings: "Settings") -> list[str]:
    """
    Validate settings. Returns warning strings for non-fatal issues.
    Raises RuntimeError for fatal production misconfigurations.
    """
    warnings: list[str] = []
    fatal: list[str] = []
    prod = is_production_like(settings)

    # Always enforce: AI auto SOS must stay off for Stage 9 / current gates
    if settings.AI_AUTO_SOS_ENABLED:
        fatal.append(
            "AI_AUTO_SOS_ENABLED=true is forbidden until product sign-off "
            "(Stage 9 keeps confirm-first; auto SOS must remain false)."
        )

    if prod:
        if settings.DEBUG:
            fatal.append("DEBUG must be false when ENVIRONMENT is production/staging.")

        sk = (settings.SECRET_KEY or "").strip()
        if len(sk) < 32:
            fatal.append("SECRET_KEY must be at least 32 characters in production/staging.")
        low = sk.lower()
        if any(m in low for m in _INSECURE_SECRET_MARKERS) or sk == "change-this-to-a-random-secret-key":
            fatal.append("SECRET_KEY looks like a default/insecure value.")

        otp = (settings.OTP_PROVIDER or "").strip().lower()
        if otp == "mock":
            fatal.append(
                "OTP_PROVIDER=mock is forbidden in production/staging "
                "(includes the 123456 shortcut)."
            )
        elif otp == "twilio":
            if not (
                (getattr(settings, "TWILIO_ACCOUNT_SID", "") or "").strip()
                and (getattr(settings, "TWILIO_AUTH_TOKEN", "") or "").strip()
                and (getattr(settings, "TWILIO_VERIFY_SERVICE_SID", "") or "").strip()
            ):
                fatal.append(
                    "OTP_PROVIDER=twilio requires TWILIO_ACCOUNT_SID, "
                    "TWILIO_AUTH_TOKEN, and TWILIO_VERIFY_SERVICE_SID."
                )
        elif otp:
            fatal.append(
                f"OTP_PROVIDER={otp} is not implemented "
                "(supported production provider: twilio)."
            )
        else:
            fatal.append("OTP_PROVIDER must be set (use twilio in production/staging).")

        if getattr(settings, "OTP_ALLOW_DEV_SHORTCUT", False):
            fatal.append("OTP_ALLOW_DEV_SHORTCUT must be false in production/staging.")

        if "postgres:password@" in (settings.DATABASE_URL or ""):
            fatal.append("DATABASE_URL still uses the default postgres:password credentials.")

        if settings.ACCESS_TOKEN_EXPIRE_MINUTES > 120:
            warnings.append(
                "ACCESS_TOKEN_EXPIRE_MINUTES > 120 — prefer shorter JWT lifetime in production."
            )

        if not (settings.META_ACCESS_TOKEN or "").strip():
            warnings.append(
                "META_ACCESS_TOKEN empty — manual WhatsApp SOS will fail until configured "
                "(AI auto SOS remains off)."
            )

        if settings.REQUIRE_REDIS_IN_PRODUCTION and not _redis_ping_ok(settings):
            fatal.append(
                "Redis is required in production/staging (REQUIRE_REDIS_IN_PRODUCTION=true) "
                "but REDIS_URL is unreachable."
            )

    else:
        if (settings.OTP_PROVIDER or "").lower() == "mock":
            warnings.append("OTP_PROVIDER=mock (dev only) — never deploy with this.")
        if settings.AI_AUTO_SOS_ENABLED:
            fatal.append("AI_AUTO_SOS_ENABLED must remain false.")

    for w in warnings:
        logger.warning("CONFIG_WARNING: %s", w)

    if fatal:
        msg = "Unsafe configuration blocked startup:\n- " + "\n- ".join(fatal)
        logger.error(msg)
        raise RuntimeError(msg)

    logger.info(
        "Runtime config OK env=%s debug=%s ai_auto_sos=%s otp_provider=%s",
        settings.ENVIRONMENT,
        settings.DEBUG,
        settings.AI_AUTO_SOS_ENABLED,
        settings.OTP_PROVIDER,
    )
    return warnings


def _redis_ping_ok(settings: "Settings") -> bool:
    try:
        import redis

        client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
        client.ping()
        client.close()
        return True
    except Exception as exc:
        logger.error("Redis ping failed: %s", exc)
        return False
