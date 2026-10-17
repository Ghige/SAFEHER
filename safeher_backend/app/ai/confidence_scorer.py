"""
SafeHer — Confidence Scorer (compat layer)

Delegates to the multi-signal Safety Decision Engine.
Legacy callers that only pass audio/movement scores keep working.

Volume is never a sole SOS trigger. Prefer SafetyDecisionEngine for new code.
"""

from typing import Optional

from app.ai.safety_decision_engine import decide_from_legacy_scores, get_default_config

# Tier boundaries loaded from decision_contract.json risk bands * 100
_cfg = get_default_config()
TIER_SILENT_VIBRATION = int(round(_cfg.risk_silent * 100))
TIER_CONFIRM_30S = int(round(_cfg.risk_medium * 100))
TIER_IMMEDIATE_SOS = int(round(_cfg.risk_high * 100))
CONFIRM_COUNTDOWN_SECONDS = _cfg.confirm_countdown_seconds


def compute_confidence_score(
    audio_score: float = 0.0,
    movement_score: float = 0.0,
    heart_rate_spike: bool = False,
    is_night: bool = None,
    is_isolated: bool = False,
    phrase_score: float = 0.0,
    volume_score: float = 0.0,
    detected_phrase: Optional[str] = None,
    phrase_language: Optional[str] = None,
    fall_detected: bool = False,
) -> dict:
    """
    Compute SafeHer multi-signal decision and return legacy fusion dict.

    New optional inputs:
        phrase_score (0–100 or 0–1), volume_score (feature only),
        detected_phrase, phrase_language, fall_detected
    """
    decision = decide_from_legacy_scores(
        audio_score=audio_score,
        movement_score=movement_score,
        phrase_score=phrase_score,
        volume_score=volume_score,
        detected_phrase=detected_phrase,
        phrase_language=phrase_language,
        fall_detected=fall_detected,
        heart_rate_spike=heart_rate_spike,
        is_night=is_night,
        is_isolated=is_isolated,
    )
    return decision.to_legacy_fusion_dict(
        audio_score_0_100=float(audio_score) if float(audio_score) > 1 else float(audio_score) * 100.0,
        movement_score_0_100=float(movement_score) if float(movement_score) > 1 else float(movement_score) * 100.0,
        heart_rate_spike=heart_rate_spike,
        is_night=bool(is_night) if is_night is not None else ("CONTEXT_NIGHT" in decision.reason_codes),
        is_isolated=is_isolated,
    )


def tick_decay(current_score: float, decay_rate: float = 0.9) -> float:
    """Apply one decay tick to a 0–100 score (temporal smoothing helper)."""
    return max(round(current_score * decay_rate, 1), 0.0)
