"""
Multi-signal Safety Decision Engine case tests.

These are logic tests (not claims of real-world model accuracy).
Synthetic scores only — do not use as production performance evidence.
"""

from app.ai.safety_decision_engine import (
    AudioModelResult,
    SpeechModelResult,
    MovementModelResult,
    RiskLevel,
    decide,
)
from app.ai.speech_phrase_detector import detect_emergency_phrase
from app.ai.confidence_scorer import compute_confidence_score


def test_case1_quiet_help_me_high_phrase_low_volume():
    """Quiet 'help me' with high phrase confidence can reach MEDIUM/HIGH."""
    d = decide(
        audio=AudioModelResult(distress_score=0.25, volume_score=0.1),
        speech=SpeechModelResult(phrase_detected=True, phrase_score=0.95, phrase="help me", language="english"),
        movement=MovementModelResult(0.0),
    )
    assert d.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)
    assert "EMERGENCY_PHRASE" in d.reason_codes
    assert d.action in ("confirm_30s", "fire_immediately")


def test_case2_loud_scream_high_distress_no_phrase():
    d = decide(
        audio=AudioModelResult(distress_score=0.92, volume_score=0.9),
        speech=SpeechModelResult(),
        movement=MovementModelResult(0.1),
    )
    assert d.risk_level == RiskLevel.HIGH
    assert "DISTRESS_AUDIO" in d.reason_codes or d.distress_score >= 0.8


def test_case3_loud_normal_conversation_no_sos():
    d = decide(
        audio=AudioModelResult(distress_score=0.15, volume_score=0.95),
        speech=SpeechModelResult(phrase_score=0.0),
        movement=MovementModelResult(0.1),
    )
    assert d.should_trigger_sos is False
    assert d.action in ("nothing", "silent_vibration")
    assert "LOUD_WITHOUT_DISTRESS_SUPPRESSED" in d.reason_codes or d.risk_level == RiskLevel.LOW


def test_case4_phrase_distress_movement_high():
    d = decide(
        audio=AudioModelResult(distress_score=0.8, volume_score=0.4),
        speech=SpeechModelResult(phrase_detected=True, phrase_score=0.9, phrase="bachao", language="hindi"),
        movement=MovementModelResult(0.85),
    )
    assert d.risk_level == RiskLevel.HIGH
    assert d.should_trigger_sos is True
    assert "MULTI_SIGNAL_CONFIRMATION" in d.reason_codes or len(d.reason_codes) >= 2


def test_case5_running_movement_only_no_sos():
    d = decide(
        audio=AudioModelResult(distress_score=0.1, volume_score=0.3),
        speech=SpeechModelResult(),
        movement=MovementModelResult(0.95),
    )
    assert d.should_trigger_sos is False
    assert d.action != "fire_immediately"
    assert "MOVEMENT_ONLY_SUPPRESSED" in d.reason_codes


def test_volume_alone_never_fires():
    d = decide(
        audio=AudioModelResult(distress_score=0.0, volume_score=1.0),
        speech=SpeechModelResult(),
        movement=MovementModelResult(0.0),
    )
    assert d.should_trigger_sos is False
    assert d.risk_level == RiskLevel.LOW


def test_phrase_detector_multilingual():
    en = detect_emergency_phrase("please help me")
    assert en.phrase_detected and en.phrase_score >= 0.9
    hi = detect_emergency_phrase("mujhe bachao")
    assert hi.phrase_detected and hi.language == "hindi"
    mr = detect_emergency_phrase("madat kara")
    assert mr.phrase_detected and mr.language == "marathi"
    normal = detect_emergency_phrase("how was your day")
    assert normal.phrase_score < 0.55


def test_legacy_confidence_compat():
    assert compute_confidence_score(0, 0, is_night=False)["action"] == "nothing"
    assert compute_confidence_score(60, 0, is_night=False)["action"] == "confirm_30s"
    assert compute_confidence_score(80, 70, is_night=False)["action"] == "fire_immediately"
    quiet = compute_confidence_score(
        audio_score=20,
        phrase_score=95,
        volume_score=10,
        detected_phrase="help me",
        is_night=False,
    )
    assert quiet["action"] in ("confirm_30s", "fire_immediately")
    assert quiet.get("risk_level") in ("MEDIUM", "HIGH")
