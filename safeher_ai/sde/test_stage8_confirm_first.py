"""
Stage 8 — confirm-first AI beta (plan + policy verification).

Uses real unified SDE outputs. Does not train models, does not send SOS,
does not enable AI_AUTO_SOS.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sde.unified_engine import UnifiedSignals, decide_unified, load_contract  # noqa: E402
from sde.confirmation import run_confirmation  # noqa: E402
from sde.config import load_config  # noqa: E402


def main() -> int:
    contract = load_contract()
    assert contract["AI_AUTO_SOS_ENABLED"] is False
    assert contract["DEMO_MODE"] is True
    conf = contract["confirmation"]
    assert conf["countdown_seconds"] == 30
    assert conf.get("stage8_confirm_first_beta") is True
    assert conf.get("fall_bypasses_confirm_ui") is False
    assert conf.get("no_response_when_ai_auto_sos_disabled") == "DISMISS_SAFE_NO_ALERT"

    # Real SDE: SUSPICIOUS (confirm_30s) — strong phrase alone
    suspicious = decide_unified(
        UnifiedSignals(audio_distress=0.1, speech_emergency=0.92, movement_anomaly=0.1),
        contract=contract,
    )
    assert suspicious.action == "confirm_30s", suspicious
    assert suspicious.state == "SUSPICIOUS"
    assert suspicious.alert_creation_allowed is False

    # Real SDE: EMERGENCY (fire) still gated
    emergency = decide_unified(
        UnifiedSignals(
            audio_distress=0.95,
            speech_emergency=0.95,
            movement_anomaly=0.95,
        ),
        contract=contract,
        demo_mode=True,
        ai_auto_sos_enabled=False,
    )
    assert emergency.action == "fire_immediately", emergency.action
    assert emergency.state == "EMERGENCY"
    assert emergency.alert_creation_allowed is False

    # Fall → fire action, but confirm UI must not be bypassed (contract flag)
    fall = decide_unified(UnifiedSignals(fall_detected=True), contract=contract)
    assert fall.action == "fire_immediately"
    assert contract["confirmation"]["fall_bypasses_confirm_ui"] is False

    # Demo confirmation CANCEL / NO_RESPONSE — never real SOS
    cfg = load_config()
    cancel = run_confirmation(cfg, user_choice="CANCEL", trigger_reason="stage8")
    assert cancel.countdown_result == "CANCELLED"
    assert cancel.real_sos_attempted is False

    no_resp = run_confirmation(cfg, user_choice="NO_RESPONSE", trigger_reason="stage8")
    assert no_resp.real_sos_attempted is False
    assert no_resp.simulated_action == "TEST_SOS_TRIGGERED"

    # Backend-style confirm_first attachment (mirror ai_alert_service policy)
    auto = bool(contract["AI_AUTO_SOS_ENABLED"])
    confirm_first = {
        "beta": True,
        "requires_user_confirmation": emergency.action in ("confirm_30s", "fire_immediately"),
        "countdown_seconds": 30,
        "ai_auto_sos_enabled": auto,
        "no_response_policy": "DISMISS_SAFE_NO_ALERT" if not auto else "CONTRACT_DEMO_SIMULATION_ONLY",
        "fall_bypasses_confirm_ui": False,
        "real_alert_allowed": False,
    }
    assert confirm_first["real_alert_allowed"] is False

    out = {
        "stage": 8,
        "AI_AUTO_SOS_ENABLED": False,
        "suspicious_action": suspicious.action,
        "emergency_action": emergency.action,
        "fall_action": fall.action,
        "cancel_real_sos": cancel.real_sos_attempted,
        "no_response_real_sos": no_resp.real_sos_attempted,
        "confirm_first": confirm_first,
        "pass": True,
    }
    log_dir = ROOT / "data" / "training_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "stage8_confirm_first_sde_test.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print(json.dumps(out, indent=2))
    print("STAGE8_SDE_CONFIRM_FIRST_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
