"""
SafeHer Unified Safety Decision Engine (Stage 3).

Single post-model fusion contract for Audio + Speech + Movement.
Authoritative algorithm matches production backend policy.
DEMO_MODE / AI_AUTO_SOS gates never create real alerts from this module.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

CONTRACT_PATH = Path(__file__).resolve().parent / "decision_contract.json"


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _to01(v: float) -> float:
    v = float(v or 0.0)
    return _clamp01(v / 100.0) if v > 1.0 else _clamp01(v)


def load_contract(path: Optional[Path] = None) -> dict[str, Any]:
    p = path or CONTRACT_PATH
    return json.loads(p.read_text(encoding="utf-8"))


@dataclass
class UnifiedSignals:
    audio_distress: float = 0.0
    speech_emergency: float = 0.0
    movement_anomaly: float = 0.0
    volume: float = 0.0
    fall_detected: bool = False
    detected_phrase: Optional[str] = None
    phrase_language: Optional[str] = None
    is_night: Optional[bool] = None
    is_isolated: bool = False
    heart_rate_spike: bool = False


@dataclass
class UnifiedDecision:
    """Canonical Stage-3 decision payload."""

    state: str  # NORMAL | SUSPICIOUS | EMERGENCY
    action: str  # nothing | silent_vibration | confirm_30s | fire_immediately
    risk_level: str  # LOW | MEDIUM | HIGH
    risk_score: float
    reason: str
    reason_codes: list[str] = field(default_factory=list)
    should_confirm: bool = False
    should_trigger_sos: bool = False
    activate_gps_stream: bool = False
    audio_score: float = 0.0
    speech_score: float = 0.0
    movement_score: float = 0.0
    volume_score: float = 0.0
    detected_phrase: Optional[str] = None
    phrase_language: Optional[str] = None
    individual_model_decisions: dict[str, str] = field(default_factory=dict)
    active_signals: list[str] = field(default_factory=list)
    multi_signal: bool = False
    demo_mode: bool = True
    ai_auto_sos_enabled: bool = False
    alert_creation_allowed: bool = False
    alert_block_reason: str = ""
    contract_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_backend_fusion_dict(
        self,
        *,
        audio_score_0_100: float,
        movement_score_0_100: float,
        heart_rate_spike: bool,
        is_night: bool,
        is_isolated: bool,
    ) -> dict[str, Any]:
        return {
            "total_score": round(self.risk_score * 100.0, 1),
            "action": self.action,
            "state": self.state,
            "activate_gps_stream": self.activate_gps_stream,
            "audio_score": audio_score_0_100,
            "movement_score": movement_score_0_100,
            "heart_rate_spike": heart_rate_spike,
            "is_night": is_night,
            "is_isolated": is_isolated,
            "risk_level": self.risk_level,
            "risk_score": round(self.risk_score, 3),
            "reason_codes": list(self.reason_codes),
            "should_confirm": self.should_confirm,
            "should_trigger_sos": self.should_trigger_sos,
            "phrase_score": round(self.speech_score, 3),
            "detected_phrase": self.detected_phrase,
            "phrase_language": self.phrase_language,
            "alert_creation_allowed": self.alert_creation_allowed,
            "alert_block_reason": self.alert_block_reason,
            "contract_version": self.contract_version,
        }


def decide_unified(
    signals: UnifiedSignals,
    *,
    contract: Optional[dict[str, Any]] = None,
    demo_mode: Optional[bool] = None,
    ai_auto_sos_enabled: Optional[bool] = None,
) -> UnifiedDecision:
    """
    Single fusion entry point used by demo SDE and mirrored by backend/Android.
    Does not send alerts. alert_creation_allowed is informational only.
    """
    c = contract or load_contract()
    gates = c["gates"]
    weights = c["weights"]
    bands = c["risk_bands"]
    policy = c["policy"]
    alert_pol = c["alert_creation"]
    state_map = c["state_from_action"]

    demo = c.get("DEMO_MODE", True) if demo_mode is None else bool(demo_mode)
    auto = (
        bool(c.get("AI_AUTO_SOS_ENABLED", False))
        if ai_auto_sos_enabled is None
        else bool(ai_auto_sos_enabled)
    )

    distress = _to01(signals.audio_distress)
    phrase = _to01(signals.speech_emergency)
    move = _to01(signals.movement_anomaly)
    volume = _to01(signals.volume)

    is_night = signals.is_night
    if is_night is None:
        hour = datetime.now().hour
        is_night = hour >= 22 or hour <= 5

    reasons: list[str] = []
    score = 0.0

    individual = {
        "audio": "DISTRESS" if distress >= gates["distress_medium"] else "NORMAL",
        "speech": "EMERGENCY" if phrase >= gates["phrase_medium"] else "NORMAL",
        "movement": "ABNORMAL" if move >= gates["movement_medium"] else "NORMAL",
    }
    if signals.fall_detected:
        individual["movement"] = "FALL"

    active: list[str] = []
    if distress >= gates["distress_medium"]:
        active.append("audio_distress")
    if phrase >= gates["phrase_medium"]:
        active.append("emergency_speech")
    if move >= gates["movement_medium"] or signals.fall_detected:
        active.append("abnormal_movement")

    # Fall → fire path
    if signals.fall_detected and policy.get("fall_is_fire_immediately", True):
        action = "fire_immediately"
        decision = UnifiedDecision(
            state=state_map[action],
            action=action,
            risk_level="HIGH",
            risk_score=1.0,
            reason="Fall detected",
            reason_codes=["FALL_DETECTED"],
            should_confirm=False,
            should_trigger_sos=True,
            activate_gps_stream=True,
            audio_score=distress,
            speech_score=phrase,
            movement_score=move,
            volume_score=volume,
            detected_phrase=signals.detected_phrase,
            phrase_language=signals.phrase_language,
            individual_model_decisions=individual,
            active_signals=active or ["abnormal_movement"],
            multi_signal=len(active) >= 2,
            demo_mode=demo,
            ai_auto_sos_enabled=auto,
            contract_version=str(c.get("contract_version", "1.0.0")),
        )
        return _apply_alert_gate(decision, demo, auto, alert_pol)

    if distress >= gates["distress_medium"]:
        score += weights["distress"] * distress
        reasons.append("DISTRESS_AUDIO")
    if phrase >= gates["phrase_medium"]:
        score += weights["phrase"] * phrase
        reasons.append("EMERGENCY_PHRASE")
    if move >= gates["movement_medium"]:
        score += weights["movement"] * move
        reasons.append("ABNORMAL_MOVEMENT")

    if volume >= gates["volume_loud"] and distress >= gates["distress_medium"]:
        score += weights["volume_feature"] * volume
        reasons.append("VOLUME_FEATURE")
    elif volume >= gates["volume_loud"] and distress < gates["distress_medium"] and phrase < gates["phrase_medium"]:
        reasons.append("LOUD_WITHOUT_DISTRESS_SUPPRESSED")

    strong = 0
    if distress >= gates["distress_high"]:
        strong += 1
    if phrase >= gates["phrase_high"]:
        strong += 1
    if move >= gates["movement_high"]:
        strong += 1
    if policy.get("multi_strong_signals_bonus", True) and strong >= 2:
        score += float(weights["multi_strong_bonus"])
        reasons.append("MULTI_SIGNAL_CONFIRMATION")

    if is_night:
        score += float(weights["context_night_bonus"])
        reasons.append("CONTEXT_NIGHT")
    if signals.is_isolated:
        score += float(weights["context_isolated_bonus"])
        reasons.append("CONTEXT_ISOLATED")
    if signals.heart_rate_spike:
        score += float(weights["heart_rate_spike_bonus"])

    distress_or_phrase = (
        distress >= gates["distress_medium"] or phrase >= gates["phrase_medium"]
    )
    if (
        move >= gates["movement_medium"]
        and not distress_or_phrase
        and not policy.get("movement_alone_can_sos", False)
    ):
        score = min(score, bands["medium"] - 0.01)
        reasons.append("MOVEMENT_ONLY_SUPPRESSED")

    if phrase >= gates["phrase_high"] and distress < gates["distress_medium"] and move < gates["movement_medium"]:
        if policy.get("phrase_alone_can_reach_high", False):
            score = max(score, bands["high"])
        elif policy.get("phrase_alone_can_reach_medium", True):
            score = max(score, bands["medium"])

    if phrase >= gates["phrase_high"] and distress >= gates["distress_medium"]:
        score = max(score, bands["high"])

    if distress >= gates["distress_high"] and phrase < gates["phrase_medium"]:
        score = max(score, bands["high"] * 0.95)

    if policy.get("audio_alone_can_reach_high_via_distress_floor", True):
        if distress >= gates["distress_floor_high"]:
            score = max(score, bands["high"])
        elif distress >= gates["distress_floor_medium"]:
            score = max(score, bands["medium"])

    if not policy.get("volume_alone_can_sos", False):
        if volume >= gates["volume_loud"] and distress < gates["distress_medium"] and phrase < gates["phrase_medium"]:
            score = min(score, bands["medium"] - 0.05)

    score = _clamp01(score)

    if score >= bands["high"]:
        risk_level = "HIGH"
        action = "fire_immediately"
        should_confirm = True
        should_trigger = True
        gps = True
        reason = "High multi-signal / distress risk"
    elif score >= bands["medium"]:
        risk_level = "MEDIUM"
        action = "confirm_30s"
        should_confirm = True
        should_trigger = False
        gps = False
        reason = "Elevated risk — confirmation required"
    elif score >= bands["silent"]:
        risk_level = "LOW"
        action = "silent_vibration"
        should_confirm = False
        should_trigger = False
        gps = False
        reason = "Low elevated signal"
    else:
        risk_level = "LOW"
        action = "nothing"
        should_confirm = False
        should_trigger = False
        gps = False
        reason = "No emergency speech and movement/audio signals below thresholds"

    # Prefer specific reason from codes when available
    if "FALL_DETECTED" in reasons:
        reason = "Fall detected"
    elif "MULTI_SIGNAL_CONFIRMATION" in reasons:
        reason = "Multiple strong emergency signals confirmed"
    elif "EMERGENCY_PHRASE" in reasons and "DISTRESS_AUDIO" not in reasons and "ABNORMAL_MOVEMENT" not in reasons:
        reason = "Emergency phrase detected — confirmation required"
    elif "DISTRESS_AUDIO" in reasons and "EMERGENCY_PHRASE" not in reasons and "ABNORMAL_MOVEMENT" not in reasons:
        reason = "Audio distress elevated"
    elif "MOVEMENT_ONLY_SUPPRESSED" in reasons:
        reason = "Abnormal movement alone suppressed (no audio/speech confirmation)"

    seen: set[str] = set()
    uniq: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)

    decision = UnifiedDecision(
        state=state_map[action],
        action=action,
        risk_level=risk_level,
        risk_score=round(score, 3),
        reason=reason,
        reason_codes=uniq,
        should_confirm=should_confirm,
        should_trigger_sos=should_trigger,
        activate_gps_stream=gps,
        audio_score=round(distress, 3),
        speech_score=round(phrase, 3),
        movement_score=round(move, 3),
        volume_score=round(volume, 3),
        detected_phrase=signals.detected_phrase,
        phrase_language=signals.phrase_language,
        individual_model_decisions=individual,
        active_signals=active,
        multi_signal=len(active) >= 2,
        demo_mode=demo,
        ai_auto_sos_enabled=auto,
        contract_version=str(c.get("contract_version", "1.0.0")),
    )
    return _apply_alert_gate(decision, demo, auto, alert_pol)


def _apply_alert_gate(
    decision: UnifiedDecision,
    demo: bool,
    auto: bool,
    alert_pol: dict[str, Any],
) -> UnifiedDecision:
    allowed = True
    block = ""
    if alert_pol.get("blocked_when_demo_mode", True) and demo:
        allowed = False
        block = "DEMO_MODE"
    if alert_pol.get("requires_AI_AUTO_SOS_ENABLED", True) and not auto:
        allowed = False
        block = "AI_AUTO_SOS_DISABLED" if not block else f"{block}+AI_AUTO_SOS_DISABLED"
    if alert_pol.get("requires_action_fire_immediately", True) and decision.action != "fire_immediately":
        allowed = False
        if not block:
            block = "ACTION_NOT_FIRE"
    decision.alert_creation_allowed = allowed
    decision.alert_block_reason = block
    return decision
