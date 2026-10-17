#!/usr/bin/env python3
"""
Validate production-like settings without starting the API server (P0-2).

Loads app.config.settings + production_guards.validate_runtime_config.
Does NOT enable AI SOS. Does NOT connect to WhatsApp send APIs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from app.config import settings
    from app.security.production_guards import validate_runtime_config

    report = {
        "ENVIRONMENT": settings.ENVIRONMENT,
        "DEBUG": settings.DEBUG,
        "OTP_PROVIDER": settings.OTP_PROVIDER,
        "AI_AUTO_SOS_ENABLED": settings.AI_AUTO_SOS_ENABLED,
        "REQUIRE_REDIS_IN_PRODUCTION": settings.REQUIRE_REDIS_IN_PRODUCTION,
        "ACCESS_TOKEN_EXPIRE_MINUTES": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        "meta_token_set": bool((settings.META_ACCESS_TOKEN or "").strip()),
        "twilio_sid_set": bool((settings.TWILIO_ACCOUNT_SID or "").strip()),
        "twilio_verify_sid_set": bool((settings.TWILIO_VERIFY_SERVICE_SID or "").strip()),
        "status": None,
        "warnings": [],
        "error": None,
    }

    if settings.AI_AUTO_SOS_ENABLED:
        report["status"] = "BLOCKED"
        report["error"] = "AI_AUTO_SOS_ENABLED must remain false"
        print(json.dumps(report, indent=2))
        return 10

    try:
        report["warnings"] = validate_runtime_config(settings)
        report["status"] = "OK"
        code = 0
    except RuntimeError as exc:
        report["status"] = "BLOCKED"
        report["error"] = str(exc)
        code = 1

    out = (
        ROOT.parent
        / "safeher_ai"
        / "data"
        / "training_logs"
        / "p0_production_config_validate.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
