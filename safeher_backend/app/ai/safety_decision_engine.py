"""
SafeHer — Safety Decision Engine (multi-signal)

Combines distress audio, emergency-phrase, and movement signals into:
  risk_level: LOW | MEDIUM | HIGH
  risk_score: 0.0–1.0
  should_confirm / should_trigger_sos
  reason_codes

Gates/weights/policy load from shared decision_contract.json (Stage 3).
Volume may contribute weakly as an acoustic feature but MUST NOT alone
cause HIGH risk or SOS.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

_CONTRACT_CANDIDATES = (
    Path(__file__).resolve().parent / "decision_contract.json",
    Path(__file__).resolve().parents[3] / "safeher_ai" / "sde" / "decision_contract.json",
)


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ReasonCode(str, Enum):
    DISTRESS_AUDIO = "DISTRESS_AUDIO"
    EMERGENCY_PHRASE = "EMERGENCY_PHRASE"
    ABNORMAL_MOVEMENT = "ABNORMAL_MOVEMENT"
    MULTI_SIGNAL_CONFIRMATION = "MULTI_SIGNAL_CONFIRMATION"
    VOLUME_FEATURE = "VOLUME_FEATURE"
    FALL_DETECTED = "FALL_DETECTED"
    CONTEXT_NIGHT = "CONTEXT_NIGHT"
    CONTEXT_ISOLATED = "CONTEXT_ISOLATED"
    MOVEMENT_ONLY_SUPPRESSED = "MOVEMENT_ONLY_SUPPRESSED"
    LOUD_WITHOUT_DISTRESS_SUPPRESSED = "LOUD_WITHOUT_DISTRESS_SUPPRESSED"


@dataclass
class AudioModelResult:
    """Distress / scream model output (0–1). volume_score is a feature only."""

    distress_score: float = 0.0
    audio_confidence: float = 0.0
    volume_score: float = 0.0


@dataclass
class SpeechModelResult:
    phrase_detected: bool = False
    phrase_score: float = 0.0
    language: Optional[str] = None
    phrase: Optional[str] = None


@dataclass
class MovementModelResult:
    movement_anomaly_score: float = 0.0
    fall_detected: bool = False


@dataclass
class SafetyDecisionConfig:
    """Fusion config — values come from decision_contract.json when loaded."""

    weight_distress: float = 0.40
    weight_phrase: float = 0.40
    weight_movement: float = 0.20
    weight_volume_feature: float = 0.05
    multi_strong_bonus: float = 0.12
    heart_rate_spike_bonus: float = 0.10

    distress_medium: float = 0.55
    distress_high: float = 0.70
    phrase_medium: float = 0.55
    phrase_high: float = 0.75
    movement_medium: float = 0.60
    movement_high: float = 0.80
    volume_loud: float = 0.70
    distress_floor_medium: float = 0.60
    distress_floor_high: float = 0.80

    risk_silent: float = 0.20
    risk_medium: float = 0.40
    risk_high: float = 0.65

    allow_movement_only_sos: bool = False
    allow_volume_only_sos: bool = False
    phrase_alone_can_reach_medium: bool = True
    phrase_alone_can_reach_high: bool = False
    audio_alone_can_reach_high_via_distress_floor: bool = True
    multi_strong_signals_bonus: bool = True
    context_night_bonus: float = 0.05
    context_isolated_bonus: float = 0.05

    confirm_action_name: str = "confirm_30s"
    confirm_countdown_seconds: int = 30
    contract_version: str = "1.0.0"

    @classmethod
    def from_contract(cls, contract: dict[str, Any]) -> "SafetyDecisionConfig":
        gates = contract["gates"]
        weights = contract["weights"]
        bands = contract["risk_bands"]
        policy = contract["policy"]
        conf = contract.get("confirmation", {})
        return cls(
            weight_distress=float(weights["distress"]),
            weight_phrase=float(weights["phrase"]),
            weight_movement=float(weights["movement"]),
            weight_volume_feature=float(weights["volume_feature"]),
            multi_strong_bonus=float(weights["multi_strong_bonus"]),
            heart_rate_spike_bonus=float(weights["heart_rate_spike_bonus"]),
            distress_medium=float(gates["distress_medium"]),
            distress_high=float(gates["distress_high"]),
            phrase_medium=float(gates["phrase_medium"]),
            phrase_high=float(gates["phrase_high"]),
            movement_medium=float(gates["movement_medium"]),
            movement_high=float(gates["movement_high"]),
            volume_loud=float(gates["volume_loud"]),
            distress_floor_medium=float(gates["distress_floor_medium"]),
            distress_floor_high=float(gates["distress_floor_high"]),
            risk_silent=float(bands["silent"]),
            risk_medium=float(bands["medium"]),
            risk_high=float(bands["high"]),
            allow_movement_only_sos=bool(policy.get("movement_alone_can_sos", False)),
            allow_volume_only_sos=bool(policy.get("volume_alone_can_sos", False)),
            phrase_alone_can_reach_medium=bool(policy.get("phrase_alone_can_reach_medium", True)),
            phrase_alone_can_reach_high=bool(policy.get("phrase_alone_can_reach_high", False)),
            audio_alone_can_reach_high_via_distress_floor=bool(
                policy.get("audio_alone_can_reach_high_via_distress_floor", True)
            ),
            multi_strong_signals_bonus=bool(policy.get("multi_strong_signals_bonus", True)),
            context_night_bonus=float(weights["context_night_bonus"]),
            context_isolated_bonus=float(weights["context_isolated_bonus"]),
            confirm_action_name=str(conf.get("api_action_name", "confirm_30s")),
            confirm_countdown_seconds=int(conf.get("countdown_seconds", 30)),
            contract_version=str(contract.get("contract_version", "1.0.0")),
        )


def resolve_decision_contract_path() -> Path:
    for p in _CONTRACT_CANDIDATES:
        if p.is_file():
            return p
    raise FileNotFoundError(
        "decision_contract.json not found. Expected beside safety_decision_engine.py "
        "or at safeher_ai/sde/decision_contract.json"
    )


@lru_cache(maxsize=1)
def load_decision_contract() -> dict[str, Any]:
    path = resolve_decision_contract_path()
    return json.loads(path.read_text(encoding="utf-8"))


def get_default_config() -> SafetyDecisionConfig:
    return SafetyDecisionConfig.from_contract(load_decision_contract())


@dataclass
class SafetyDecision:
    risk_score: float
    risk_level: RiskLevel
    reason_codes: List[str] = field(default_factory=list)
    should_confirm: bool = False
    should_trigger_sos: bool = False
    action: str = "nothing"
    activate_gps_stream: bool = False
    distress_score: float = 0.0
    phrase_score: float = 0.0
    movement_score: float = 0.0
    volume_score: float = 0.0
    detected_phrase: Optional[str] = None
    language: Optional[str] = None
    contract_version: str = "1.0.0"

    def to_legacy_fusion_dict(
        self,
        *,
        audio_score_0_100: float,
        movement_score_0_100: float,
        heart_rate_spike: bool,
        is_night: bool,
        is_isolated: bool,
    ) -> dict:
        """Map to existing confidence_scorer / API response shape."""
        state_map = {
            "nothing": "NORMAL",
            "silent_vibration": "NORMAL",
            "confirm_30s": "SUSPICIOUS",
            "fire_immediately": "EMERGENCY",
        }
        return {
            "total_score": round(self.risk_score * 100.0, 1),
            "action": self.action,
            "state": state_map.get(self.action, "NORMAL"),
            "activate_gps_stream": self.activate_gps_stream,
            "audio_score": audio_score_0_100,
            "movement_score": movement_score_0_100,
            "heart_rate_spike": heart_rate_spike,
            "is_night": is_night,
            "is_isolated": is_isolated,
            "risk_level": self.risk_level.value,
            "risk_score": round(self.risk_score, 3),
            "reason_codes": list(self.reason_codes),
            "should_confirm": self.should_confirm,
            "should_trigger_sos": self.should_trigger_sos,
            "phrase_score": round(self.phrase_score, 3),
            "detected_phrase": self.detected_phrase,
            "phrase_language": self.language,
            "contract_version": self.contract_version,
        }


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def decide(
    audio: Optional[AudioModelResult] = None,
    speech: Optional[SpeechModelResult] = None,
    movement: Optional[MovementModelResult] = None,
    *,
    is_night: Optional[bool] = None,
    is_isolated: bool = False,
    heart_rate_spike: bool = False,
    config: Optional[SafetyDecisionConfig] = None,
) -> SafetyDecision:
    """
    Multi-signal safety decision.

    Case guidance (product):
      1 quiet "help me" + high phrase → MEDIUM/HIGH capable
      2 loud scream + high distress → potentially HIGH
      3 loud normal talk, no distress/phrase → NOT SOS
      4 phrase + distress + movement → HIGH
      5 running / high movement only → NOT automatic SOS
    """
    cfg = config or get_default_config()
    audio = audio or AudioModelResult()
    speech = speech or SpeechModelResult()
    movement = movement or MovementModelResult()

    distress = _clamp01(audio.distress_score if audio.distress_score > 0 else audio.audio_confidence)
    if distress > 1.0:
        distress = _clamp01(distress / 100.0)
    phrase = _clamp01(speech.phrase_score)
    if phrase > 1.0:
        phrase = _clamp01(phrase / 100.0)
    move = _clamp01(movement.movement_anomaly_score)
    if move > 1.0:
        move = _clamp01(move / 100.0)
    volume = _clamp01(audio.volume_score)
    if volume > 1.0:
        volume = _clamp01(volume / 100.0)

    if is_night is None:
        hour = datetime.now().hour
        is_night = hour >= 22 or hour <= 5

    reasons: List[str] = []
    score = 0.0

    if movement.fall_detected:
        reasons.append(ReasonCode.FALL_DETECTED.value)
        return SafetyDecision(
            risk_score=1.0,
            risk_level=RiskLevel.HIGH,
            reason_codes=reasons,
            should_confirm=False,
            should_trigger_sos=True,
            action="fire_immediately",
            activate_gps_stream=True,
            distress_score=distress,
            phrase_score=phrase,
            movement_score=move,
            volume_score=volume,
            detected_phrase=speech.phrase,
            language=speech.language,
            contract_version=cfg.contract_version,
        )

    if distress >= cfg.distress_medium:
        score += cfg.weight_distress * distress
        reasons.append(ReasonCode.DISTRESS_AUDIO.value)
    if phrase >= cfg.phrase_medium:
        score += cfg.weight_phrase * phrase
        reasons.append(ReasonCode.EMERGENCY_PHRASE.value)
    if move >= cfg.movement_medium:
        score += cfg.weight_movement * move
        reasons.append(ReasonCode.ABNORMAL_MOVEMENT.value)

    if volume >= cfg.volume_loud and distress >= cfg.distress_medium:
        score += cfg.weight_volume_feature * volume
        reasons.append(ReasonCode.VOLUME_FEATURE.value)
    elif volume >= cfg.volume_loud and distress < cfg.distress_medium and phrase < cfg.phrase_medium:
        reasons.append(ReasonCode.LOUD_WITHOUT_DISTRESS_SUPPRESSED.value)

    strong = 0
    if distress >= cfg.distress_high:
        strong += 1
    if phrase >= cfg.phrase_high:
        strong += 1
    if move >= cfg.movement_high:
        strong += 1
    if cfg.multi_strong_signals_bonus and strong >= 2:
        score += cfg.multi_strong_bonus
        reasons.append(ReasonCode.MULTI_SIGNAL_CONFIRMATION.value)

    if is_night:
        score += cfg.context_night_bonus
        reasons.append(ReasonCode.CONTEXT_NIGHT.value)
    if is_isolated:
        score += cfg.context_isolated_bonus
        reasons.append(ReasonCode.CONTEXT_ISOLATED.value)
    if heart_rate_spike:
        score += cfg.heart_rate_spike_bonus

    distress_or_phrase = distress >= cfg.distress_medium or phrase >= cfg.phrase_medium
    if move >= cfg.movement_medium and not distress_or_phrase and not cfg.allow_movement_only_sos:
        score = min(score, cfg.risk_medium - 0.01)
        reasons.append(ReasonCode.MOVEMENT_ONLY_SUPPRESSED.value)

    if phrase >= cfg.phrase_high and distress < cfg.distress_medium and move < cfg.movement_medium:
        if cfg.phrase_alone_can_reach_high:
            score = max(score, cfg.risk_high)
        elif cfg.phrase_alone_can_reach_medium:
            score = max(score, cfg.risk_medium)

    if phrase >= cfg.phrase_high and distress >= cfg.distress_medium:
        score = max(score, cfg.risk_high)

    if distress >= cfg.distress_high and phrase < cfg.phrase_medium:
        score = max(score, cfg.risk_high * 0.95)

    if cfg.audio_alone_can_reach_high_via_distress_floor:
        if distress >= cfg.distress_floor_high:
            score = max(score, cfg.risk_high)
        elif distress >= cfg.distress_floor_medium:
            score = max(score, cfg.risk_medium)

    if not cfg.allow_volume_only_sos:
        if volume >= cfg.volume_loud and distress < cfg.distress_medium and phrase < cfg.phrase_medium:
            score = min(score, cfg.risk_medium - 0.05)

    score = _clamp01(score)

    if score >= cfg.risk_high:
        level = RiskLevel.HIGH
        action = "fire_immediately"
        should_confirm = True
        should_trigger = True
        gps = True
    elif score >= cfg.risk_medium:
        level = RiskLevel.MEDIUM
        action = cfg.confirm_action_name
        should_confirm = True
        should_trigger = False
        gps = False
    elif score >= cfg.risk_silent:
        level = RiskLevel.LOW
        action = "silent_vibration"
        should_confirm = False
        should_trigger = False
        gps = False
    else:
        level = RiskLevel.LOW
        action = "nothing"
        should_confirm = False
        should_trigger = False
        gps = False

    seen = set()
    uniq = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)

    return SafetyDecision(
        risk_score=round(score, 3),
        risk_level=level,
        reason_codes=uniq,
        should_confirm=should_confirm,
        should_trigger_sos=should_trigger,
        action=action,
        activate_gps_stream=gps,
        distress_score=round(distress, 3),
        phrase_score=round(phrase, 3),
        movement_score=round(move, 3),
        volume_score=round(volume, 3),
        detected_phrase=speech.phrase if speech.phrase_detected or phrase > 0 else speech.phrase,
        language=speech.language,
        contract_version=cfg.contract_version,
    )


def decide_from_legacy_scores(
    audio_score: float = 0.0,
    movement_score: float = 0.0,
    phrase_score: float = 0.0,
    volume_score: float = 0.0,
    *,
    detected_phrase: Optional[str] = None,
    phrase_language: Optional[str] = None,
    fall_detected: bool = False,
    heart_rate_spike: bool = False,
    is_night: Optional[bool] = None,
    is_isolated: bool = False,
    config: Optional[SafetyDecisionConfig] = None,
) -> SafetyDecision:
    """Helper when callers still use 0–100 sensor scores."""

    def to01(v: float) -> float:
        v = float(v or 0.0)
        return _clamp01(v / 100.0) if v > 1.0 else _clamp01(v)

    cfg = config or get_default_config()
    return decide(
        audio=AudioModelResult(
            distress_score=to01(audio_score),
            audio_confidence=to01(audio_score),
            volume_score=to01(volume_score),
        ),
        speech=SpeechModelResult(
            phrase_detected=to01(phrase_score) >= cfg.phrase_medium or bool(detected_phrase),
            phrase_score=to01(phrase_score),
            language=phrase_language,
            phrase=detected_phrase,
        ),
        movement=MovementModelResult(
            movement_anomaly_score=to01(movement_score),
            fall_detected=fall_detected,
        ),
        is_night=is_night,
        is_isolated=is_isolated,
        heart_rate_spike=heart_rate_spike,
        config=cfg,
    )
