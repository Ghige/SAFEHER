#!/usr/bin/env python3
"""
P0-3 WhatsApp staging probe — Meta Graph credential check + optional hello_world.

SAFETY (mandatory):
  - Default mode is DRY-RUN: never sends a message.
  - Even with --send-hello-world, only Meta sample template "hello_world" is used.
  - NEVER sends SOS / alert / cancel emergency templates.
  - NEVER sends if STAGING_WHATSAPP_RECIPIENT is unset.
  - Refuses if AI_AUTO_SOS_ENABLED is true in env.

Does NOT claim emergency-alert delivery. Staging hello_world ≠ production SOS E2E.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
OUT_PATH = (
    ROOT.parent
    / "safeher_ai"
    / "data"
    / "training_logs"
    / "p0_whatsapp_staging_probe.json"
)
_META_API = "https://graph.facebook.com/v23.0"
_HELLO = "hello_world"
_HELLO_LANG = "en_US"


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
    # Process env overrides
    for k, v in os.environ.items():
        if k.startswith("META_") or k in {
            "STAGING_WHATSAPP_RECIPIENT",
            "AI_AUTO_SOS_ENABLED",
        }:
            if v.strip():
                vals[k] = v.strip()
    return vals


def main() -> int:
    parser = argparse.ArgumentParser(description="SafeHer WhatsApp staging probe")
    parser.add_argument(
        "--send-hello-world",
        action="store_true",
        help="Actually send Meta hello_world to STAGING_WHATSAPP_RECIPIENT (not an SOS)",
    )
    parser.add_argument(
        "--i-understand-this-sends-a-message",
        action="store_true",
        help="Required together with --send-hello-world",
    )
    args = parser.parse_args()

    env = load_env(ENV_PATH)
    token = env.get("META_ACCESS_TOKEN", "")
    phone_id = env.get("META_PHONE_NUMBER_ID", "")
    recipient = env.get("STAGING_WHATSAPP_RECIPIENT", "").strip()
    ai_flag = (env.get("AI_AUTO_SOS_ENABLED") or "false").strip().lower()

    report: dict = {
        "mode": "SEND_HELLO_WORLD" if args.send_hello_world else "DRY_RUN",
        "AI_AUTO_SOS_ENABLED": ai_flag,
        "token_present": bool(token) and len(token) > 20,
        "phone_number_id_present": bool(phone_id),
        "staging_recipient_configured": bool(recipient),
        "credential_reachability_status": "NOT_VERIFIED",
        "hello_world_send_status": "NOT_ATTEMPTED",
        "emergency_alert_send_status": "REFUSED_BY_DESIGN",
        "notes": [],
    }

    if ai_flag in {"true", "1", "yes"}:
        report["notes"].append("AI_AUTO_SOS_ENABLED must remain false — aborting.")
        OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 10

    if not (report["token_present"] and report["phone_number_id_present"]):
        report["credential_reachability_status"] = "BLOCKED"
        report["notes"].append("Missing META_ACCESS_TOKEN and/or META_PHONE_NUMBER_ID")
        OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    url = f"{_META_API}/{phone_id}"
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"fields": "display_phone_number,verified_name,quality_rating"},
            timeout=30.0,
        )
        report["graph_probe_status"] = response.status_code
        if response.is_success:
            body = response.json()
            report["credential_reachability_status"] = "REACHABLE"
            report["display_phone_number"] = body.get("display_phone_number")
            report["verified_name"] = body.get("verified_name")
            report["notes"].append("GET phone-number-id succeeded. No emergency template sent.")
        else:
            report["credential_reachability_status"] = "BLOCKED"
            err = response.json().get("error", {}) if response.headers.get("content-type", "").startswith("application/json") else {}
            report["graph_error"] = {
                "code": err.get("code"),
                "message": err.get("message"),
            }
            report["notes"].append("Meta Graph GET failed")
    except Exception as exc:
        report["credential_reachability_status"] = "BLOCKED"
        report["notes"].append(f"Probe exception: {type(exc).__name__}")

    if args.send_hello_world:
        if not args.i_understand_this_sends_a_message:
            report["hello_world_send_status"] = "BLOCKED"
            report["notes"].append(
                "Pass --i-understand-this-sends-a-message with --send-hello-world"
            )
        elif not recipient:
            report["hello_world_send_status"] = "BLOCKED"
            report["notes"].append(
                "STAGING_WHATSAPP_RECIPIENT unset — refusing to send to unknown number"
            )
        elif report["credential_reachability_status"] != "REACHABLE":
            report["hello_world_send_status"] = "BLOCKED"
            report["notes"].append("Credentials not reachable — send skipped")
        else:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient.lstrip("+"),
                "type": "template",
                "template": {
                    "name": _HELLO,
                    "language": {"code": _HELLO_LANG},
                },
            }
            send_url = f"{_META_API}/{phone_id}/messages"
            try:
                send_resp = httpx.post(
                    send_url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=30.0,
                )
                report["hello_world_http_status"] = send_resp.status_code
                if send_resp.is_success:
                    mid = send_resp.json().get("messages", [{}])[0].get("id")
                    report["hello_world_send_status"] = "SENT"
                    report["hello_world_message_id"] = mid
                    report["notes"].append(
                        "hello_world sent to staging recipient only — NOT an SOS/alert template"
                    )
                else:
                    report["hello_world_send_status"] = "FAILED"
                    report["notes"].append(f"hello_world send failed: {send_resp.text[:200]}")
            except Exception as exc:
                report["hello_world_send_status"] = "FAILED"
                report["notes"].append(f"Send exception: {type(exc).__name__}")
    else:
        if not recipient:
            report["hello_world_send_status"] = "NOT_VERIFIED"
            report["notes"].append(
                "Dry-run only. Set STAGING_WHATSAPP_RECIPIENT and use "
                "--send-hello-world --i-understand-this-sends-a-message to verify delivery."
            )
        else:
            report["hello_world_send_status"] = "NOT_ATTEMPTED"
            report["notes"].append(
                "Recipient configured but dry-run mode — no message sent."
            )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["credential_reachability_status"] != "REACHABLE":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
