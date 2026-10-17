"""
Stage 0/1 external dependency probe.

Does NOT send WhatsApp messages or SMS.
Does NOT print secrets.
Writes a redacted status report for the Stage 0/1 completion log.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
OUT_PATH = (
    ROOT.parent
    / "safeher_ai"
    / "data"
    / "training_logs"
    / "stage0_stage1_external_probe.json"
)


def load_env(path: Path) -> dict[str, str]:
    vals: dict[str, str] = {}
    if not path.exists():
        return vals
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        vals[key.strip()] = value.strip().strip('"').strip("'")
    return vals


def is_placeholder(value: str) -> bool:
    if not value:
        return True
    lowered = value.lower()
    return lowered.startswith("your_") or lowered in {"change-this", "changeme", "todo"}


def main() -> None:
    env = load_env(ENV_PATH)
    token = env.get("META_ACCESS_TOKEN", "")
    phone_id = env.get("META_PHONE_NUMBER_ID", "")
    waba = env.get("META_WABA_ID", "")
    otp_provider = env.get("OTP_PROVIDER", "mock")
    twilio_sid = env.get("TWILIO_VERIFY_SERVICE_SID", "")
    ai_flag = env.get("AI_AUTO_SOS_ENABLED", "(unset)")
    staging_recipient = env.get("STAGING_WHATSAPP_RECIPIENT", "")

    report: dict = {
        "otp": {
            "provider_configured": otp_provider,
            "real_provider_implemented_in_code": True,
            "implemented_providers": ["mock", "twilio"],
            "twilio_verify_sid_usable": bool(twilio_sid) and not is_placeholder(twilio_sid),
            "staging_e2e_status": "BLOCKED",
            "reason": (
                "Twilio Verify path exists in otp_service.py; "
                "live SMS E2E remains BLOCKED until Twilio creds + phone verification succeed."
                if (otp_provider or "").lower() != "twilio"
                or not (bool(twilio_sid) and not is_placeholder(twilio_sid))
                else "OTP_PROVIDER=twilio configured in .env — live SMS still needs operator E2E."
            ),
        },
        "whatsapp_meta": {
            "token_present": bool(token) and len(token) > 20 and not is_placeholder(token),
            "phone_number_id_present": bool(phone_id) and not is_placeholder(phone_id),
            "waba_id_present": bool(waba) and not is_placeholder(waba),
            "staging_recipient_configured": bool(staging_recipient)
            and not is_placeholder(staging_recipient),
            "graph_probe_status": None,
            "graph_probe_error_code": None,
            "graph_probe_error_message": None,
            "message_send_e2e_status": "NOT_ATTEMPTED",
            "credential_reachability_status": "NOT_VERIFIED",
            "notes": [],
        },
        "kill_switch_env": {
            "AI_AUTO_SOS_ENABLED_in_dotenv": ai_flag,
            "expected": "false or unset (defaults false in Settings)",
        },
    }

    wa = report["whatsapp_meta"]
    if not (wa["token_present"] and wa["phone_number_id_present"]):
        wa["credential_reachability_status"] = "BLOCKED"
        wa["notes"].append("Missing META_ACCESS_TOKEN and/or META_PHONE_NUMBER_ID in .env")
    else:
        url = f"https://graph.facebook.com/v23.0/{phone_id}"
        params = {"fields": "display_phone_number,verified_name,quality_rating"}
        try:
            response = httpx.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                timeout=30.0,
            )
            wa["graph_probe_status"] = response.status_code
            body_text = response.text
            # Never persist raw token
            if token in body_text:
                body_text = body_text.replace(token, "[REDACTED]")
            try:
                body = response.json()
            except Exception:
                body = {"raw": body_text[:300]}

            if response.is_success:
                wa["credential_reachability_status"] = "REACHABLE"
                # Keep only non-sensitive fields
                wa["display_phone_number"] = body.get("display_phone_number")
                wa["verified_name"] = body.get("verified_name")
                wa["notes"].append(
                    "GET phone-number-id succeeded. No WhatsApp message was sent."
                )
            else:
                wa["credential_reachability_status"] = "BLOCKED"
                err = body.get("error", {}) if isinstance(body, dict) else {}
                wa["graph_probe_error_code"] = err.get("code")
                wa["graph_probe_error_message"] = err.get("message")
                wa["notes"].append(
                    "Meta Graph GET failed — token/permissions/id invalid or expired."
                )
        except Exception as exc:
            wa["credential_reachability_status"] = "BLOCKED"
            wa["graph_probe_error_message"] = type(exc).__name__
            wa["notes"].append(f"Network/probe exception: {type(exc).__name__}")

    if wa["credential_reachability_status"] == "REACHABLE":
        if not wa["staging_recipient_configured"]:
            wa["message_send_e2e_status"] = "NOT_VERIFIED"
            wa["notes"].append(
                "No STAGING_WHATSAPP_RECIPIENT in .env — refusing to send a live "
                "template message to an unknown number."
            )
        else:
            wa["message_send_e2e_status"] = "NOT_ATTEMPTED"
            wa["notes"].append(
                "Staging recipient is set, but this probe intentionally does not send messages."
            )
    else:
        wa["message_send_e2e_status"] = "BLOCKED"

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
