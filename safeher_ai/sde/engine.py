"""
SafeHer Safety Decision Engine — DEMO facade over the unified Stage-3 contract.

Keeps NORMAL | SUSPICIOUS | EMERGENCY labels for demos/reports while using the
same fusion algorithm as production backend.
Requires DEMO_MODE=true. Never creates real alerts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .config import DecisionEngineConfig
from .confirmation import ConfirmationResult, UserChoice, run_confirmation
from .unified_engine import UnifiedSignals, decide_unified, load_contract


@dataclass
class EngineInput:
    audio_score: float = 0.0
    speech_emergency_score: float = 0.0
    movement_score: float = 0.0
    detected_phrase: Optional[str] = None
    confidence: float = 0.0
    volume_score: float = 0.0
    fall_detected: bool = False
    is_night: Optional[bool] = False
    is_isolated: bool = False
    heart_rate_spike: bool = False
    timestamp: Optional[str] = None
    scenario_id: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class EngineOutput:
    decision: str  # NORMAL | SUSPICIOUS | EMERGENCY
    reason: str
    confidence: float
    audio_score: float
    speech_score: float
    movement_score: float
    detected_phrase: Optional[str]
    individual_model_decisions: dict[str, str]
    active_signals: list[str] = field(default_factory=list)
    multi_signal: bool = False
    trigger_reason: str = ""
    countdown_result: Optional[str] = None
    simulated_action: str = "NONE"
    confirmation: Optional[dict[str, Any]] = None
    demo_mode: bool = True
    timestamp: str = ""
    scenario_id: Optional[str] = None
    action: str = "nothing"
    risk_level: str = "LOW"
    risk_score: float = 0.0
    alert_creation_allowed: bool = False
    alert_block_reason: str = ""
    contract_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SafetyDecisionEngine:
    def __init__(self, cfg: DecisionEngineConfig):
        self.cfg = cfg
        if not cfg.demo_mode:
            raise RuntimeError("SafetyDecisionEngine requires DEMO_MODE=true")
        self.contract = load_contract()

    def decide(self, raw: EngineInput) -> EngineOutput:
        # Prefer explicit speech score; phrase confidence can fill when phrase text present.
        speech = float(raw.speech_emergency_score or 0.0)
        if raw.detected_phrase and speech <= 0.0 and raw.confidence:
            speech = float(raw.confidence)

        unified = decide_unified(
            UnifiedSignals(
                audio_distress=float(raw.audio_score or 0.0),
                speech_emergency=speech,
                movement_anomaly=float(raw.movement_score or 0.0),
                volume=float(raw.volume_score or 0.0),
                fall_detected=bool(raw.fall_detected),
                detected_phrase=raw.detected_phrase,
                is_night=raw.is_night,
                is_isolated=bool(raw.is_isolated),
                heart_rate_spike=bool(raw.heart_rate_spike),
            ),
            contract=self.contract,
            demo_mode=True,
            ai_auto_sos_enabled=False,
        )

        return EngineOutput(
            decision=unified.state,
            reason=unified.reason,
            confidence=unified.risk_score,
            audio_score=unified.audio_score,
            speech_score=unified.speech_score,
            movement_score=unified.movement_score,
            detected_phrase=unified.detected_phrase,
            individual_model_decisions=unified.individual_model_decisions,
            active_signals=unified.active_signals,
            multi_signal=unified.multi_signal,
            trigger_reason=unified.reason if unified.state == "EMERGENCY" else "",
            countdown_result=None,
            simulated_action="NONE",
            confirmation=None,
            demo_mode=True,
            timestamp=raw.timestamp or datetime.now(timezone.utc).isoformat(),
            scenario_id=raw.scenario_id,
            action=unified.action,
            risk_level=unified.risk_level,
            risk_score=unified.risk_score,
            alert_creation_allowed=unified.alert_creation_allowed,
            alert_block_reason=unified.alert_block_reason,
            contract_version=unified.contract_version,
        )

    def decide_with_confirmation(
        self,
        raw: EngineInput,
        *,
        user_choice: Optional[UserChoice] = None,
    ) -> EngineOutput:
        """
        Confirmation for SUSPICIOUS (confirm) and EMERGENCY (fire) paths.
        CANCEL → CANCELLED; NO_RESPONSE → TEST_SOS_TRIGGERED (demo log only).
        """
        out = self.decide(raw)
        needs_confirm = out.action in ("confirm_30s", "fire_immediately") or out.decision in (
            "SUSPICIOUS",
            "EMERGENCY",
        )
        if not needs_confirm:
            out.countdown_result = "NOT_APPLICABLE"
            out.simulated_action = "NONE"
            return out

        choice: UserChoice = user_choice or "NO_RESPONSE"
        conf_res: ConfirmationResult = run_confirmation(
            self.cfg, user_choice=choice, trigger_reason=out.trigger_reason or out.reason
        )
        out.countdown_result = conf_res.countdown_result
        out.simulated_action = conf_res.simulated_action
        out.confirmation = {
            "prompted": conf_res.prompted,
            "message": conf_res.message,
            "countdown_seconds": conf_res.countdown_seconds,
            "user_choice": conf_res.user_choice,
            "real_sos_attempted": conf_res.real_sos_attempted,
        }
        # Cancel never allows alert creation
        if conf_res.countdown_result == "CANCELLED":
            out.alert_creation_allowed = False
            out.alert_block_reason = "USER_CANCELLED"
        return out
