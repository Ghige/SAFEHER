"""
Stage 3 — unified SDE contract tests.

Uses the unified fusion algorithm (same policy as backend).
Does NOT send real SOS. DEMO_MODE / AI_AUTO_SOS stay disabled.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sde.config import load_config
from sde.engine import EngineInput, SafetyDecisionEngine
from sde.unified_engine import UnifiedSignals, decide_unified, load_contract

# Backend mirror
BACKEND = ROOT.parent / "safeher_backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


@pytest.fixture(scope="module")
def contract():
    c = load_contract()
    assert c["DEMO_MODE"] is True
    assert c["AI_AUTO_SOS_ENABLED"] is False
    return c


@pytest.fixture(scope="module")
def demo_engine():
    cfg = load_config()
    assert cfg.demo_mode is True
    return SafetyDecisionEngine(cfg)


def test_contract_file_present(contract):
    assert contract["contract_version"] == "1.0.0"
    assert set(contract["states"]) == {"NORMAL", "SUSPICIOUS", "EMERGENCY"}


def test_normal(demo_engine):
    out = demo_engine.decide(
        EngineInput(audio_score=0.1, speech_emergency_score=0.05, movement_score=0.1, is_night=False)
    )
    assert out.decision == "NORMAL"
    assert out.action == "nothing"
    assert out.alert_creation_allowed is False


def test_audio_only_high_distress_is_emergency(demo_engine):
    out = demo_engine.decide(
        EngineInput(audio_score=0.86, speech_emergency_score=0.0, movement_score=0.1, is_night=False)
    )
    assert out.decision == "EMERGENCY"
    assert out.action == "fire_immediately"
    assert out.alert_creation_allowed is False
    assert "AI_AUTO_SOS" in out.alert_block_reason or "DEMO" in out.alert_block_reason


def test_movement_only_suppressed(demo_engine):
    out = demo_engine.decide(
        EngineInput(audio_score=0.1, speech_emergency_score=0.0, movement_score=0.95, is_night=False)
    )
    assert out.decision == "NORMAL"
    assert out.action in ("nothing", "silent_vibration")
    assert out.action != "fire_immediately"
    assert out.alert_creation_allowed is False


def test_emergency_speech_alone_is_suspicious(demo_engine):
    out = demo_engine.decide(
        EngineInput(
            audio_score=0.1,
            speech_emergency_score=0.92,
            movement_score=0.1,
            detected_phrase="help me",
            confidence=0.95,
            is_night=False,
        )
    )
    assert out.decision == "SUSPICIOUS"
    assert out.action == "confirm_30s"
    assert out.alert_creation_allowed is False


def test_audio_plus_movement_emergency(demo_engine):
    out = demo_engine.decide(
        EngineInput(audio_score=0.84, speech_emergency_score=0.0, movement_score=0.82, is_night=False)
    )
    assert out.decision == "EMERGENCY"
    assert out.action == "fire_immediately"


def test_speech_plus_movement_emergency(demo_engine):
    out = demo_engine.decide(
        EngineInput(
            audio_score=0.2,
            speech_emergency_score=0.9,
            movement_score=0.85,
            detected_phrase="help me",
            is_night=False,
        )
    )
    assert out.decision == "EMERGENCY"
    assert out.action == "fire_immediately"


def test_all_signals_emergency(demo_engine):
    out = demo_engine.decide(
        EngineInput(
            audio_score=0.8,
            speech_emergency_score=0.9,
            movement_score=0.85,
            detected_phrase="i need help",
            is_night=False,
        )
    )
    assert out.decision == "EMERGENCY"
    assert out.multi_signal is True
    assert out.action == "fire_immediately"


def test_cancellation_blocks_alert(demo_engine):
    out = demo_engine.decide_with_confirmation(
        EngineInput(
            audio_score=0.9,
            speech_emergency_score=0.0,
            movement_score=0.1,
            is_night=False,
        ),
        user_choice="CANCEL",
    )
    assert out.countdown_result == "CANCELLED"
    assert out.simulated_action == "NONE"
    assert out.confirmation and out.confirmation["real_sos_attempted"] is False
    assert out.alert_creation_allowed is False
    assert out.alert_block_reason == "USER_CANCELLED"


def test_disabled_ai_auto_sos_never_allows_alert(contract):
    d = decide_unified(
        UnifiedSignals(audio_distress=0.95, speech_emergency=0.95, movement_anomaly=0.95),
        contract=contract,
        demo_mode=True,
        ai_auto_sos_enabled=False,
    )
    assert d.action == "fire_immediately"
    assert d.alert_creation_allowed is False
    assert "AI_AUTO_SOS" in d.alert_block_reason or "DEMO" in d.alert_block_reason


def test_demo_and_backend_agree_on_key_cases():
    from app.ai.safety_decision_engine import (
        AudioModelResult,
        MovementModelResult,
        SpeechModelResult,
        decide,
    )

    cases = [
        # audio, speech, move, expected_state
        (0.1, 0.05, 0.1, "NORMAL"),
        (0.86, 0.0, 0.1, "EMERGENCY"),
        (0.1, 0.0, 0.95, "NORMAL"),
        (0.1, 0.92, 0.1, "SUSPICIOUS"),
        (0.84, 0.0, 0.82, "EMERGENCY"),
        (0.2, 0.9, 0.85, "EMERGENCY"),
        (0.8, 0.9, 0.85, "EMERGENCY"),
    ]
    for audio, speech, move, expected in cases:
        uni = decide_unified(
            UnifiedSignals(
                audio_distress=audio,
                speech_emergency=speech,
                movement_anomaly=move,
            ),
            demo_mode=True,
            ai_auto_sos_enabled=False,
        )
        back = decide(
            audio=AudioModelResult(distress_score=audio),
            speech=SpeechModelResult(phrase_score=speech, phrase_detected=speech >= 0.55),
            movement=MovementModelResult(movement_anomaly_score=move),
            is_night=False,
        )
        back_state = {
            "nothing": "NORMAL",
            "silent_vibration": "NORMAL",
            "confirm_30s": "SUSPICIOUS",
            "fire_immediately": "EMERGENCY",
        }[back.action]
        assert uni.state == expected, f"unified {audio,speech,move} -> {uni.state}"
        assert back_state == expected, f"backend {audio,speech,move} -> {back_state}"
        assert uni.action == back.action


def test_fall_is_emergency_but_alert_blocked():
    d = decide_unified(
        UnifiedSignals(fall_detected=True),
        demo_mode=True,
        ai_auto_sos_enabled=False,
    )
    assert d.state == "EMERGENCY"
    assert d.action == "fire_immediately"
    assert d.alert_creation_allowed is False


def test_duplicate_alerts_rejected_when_active_exists(monkeypatch):
    """Contract: duplicate_active_alert=reject — mirrors alert_service.trigger_alert."""
    from uuid import uuid4
    from unittest.mock import MagicMock

    import pytest as _pytest

    from app.services import alert_service

    assert load_contract()["alert_creation"]["duplicate_active_alert"] == "reject"

    db = MagicMock()
    user = MagicMock()
    user.id = uuid4()
    existing = MagicMock()
    existing.id = "existing-alert-id"
    existing.status = "active"

    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = user
    monkeypatch.setattr(alert_service, "get_active_alert", lambda *_a, **_k: existing)

    with _pytest.raises(ValueError, match="active alert already exists"):
        alert_service.trigger_alert(db, user.id, "ai", 0.0, 0.0)
