"""
AI alert service — bridges the on-device AI models to the alert pipeline.

The audio and movement models run on the device (Flutter app / Python edge process).
When they fire, they call this service's HTTP endpoints, which then call
trigger_alert() with the appropriate trigger_type and confidence metadata.

This module also exposes compute_fused_confidence() for the sensor fusion
layer, so the app can check the combined score before firing.

Flow:
    AudioMonitor fires SOSEvent
        → POST /api/v1/ai/audio-sos  (trigger_type="ai_audio")

    Movement model fires
        → POST /api/v1/ai/movement-sos  (trigger_type="ai_movement")

    Sensor fusion (app-side) wants a score
        → POST /api/v1/ai/confidence  → returns score + recommended action
"""

import logging
import time
from sqlalchemy.orm import Session
from uuid import UUID

from app.config import settings
from app.models.user import User
from app.services.alert_service import trigger_alert, get_active_alert
from app.ai.confidence_scorer import compute_confidence_score
from app.services.audit_log import write_audit_event
from app.observability import metrics

logger = logging.getLogger(__name__)


def ai_auto_sos_allowed() -> bool:
    """Hard gate: automatic AI SOS is disabled unless explicitly enabled."""
    return bool(settings.AI_AUTO_SOS_ENABLED)


def _blocked_ai_auto_sos(extra: dict | None = None) -> dict:
    body = {
        "alert": None,
        "ai_auto_sos_enabled": False,
        "ai_auto_sos_blocked": True,
        "reason": "ai_auto_sos_disabled",
        "message": (
            "Automatic AI SOS is disabled (AI_AUTO_SOS_ENABLED=false). "
            "No WhatsApp/SMS/call was sent. Use manual SOS if needed."
        ),
    }
    if extra:
        body.update(extra)
    return body


# ── Sensor fusion ─────────────────────────────────────────────────────────────

def compute_fused_confidence(
    audio_score: float = 0.0,
    movement_score: float = 0.0,
    heart_rate_spike: bool = False,
    is_night: bool = None,
    is_isolated: bool = False,
    phrase_score: float = 0.0,
    volume_score: float = 0.0,
    detected_phrase: str = None,
    phrase_language: str = None,
    fall_detected: bool = False,
) -> dict:
    """
    Multi-signal Safety Decision Engine (via confidence_scorer compat layer).

    Action field (existing SOS flow):
        "nothing" | "silent_vibration" | "confirm_30s" | "fire_immediately"

    Also returns risk_level, reason_codes, should_confirm, should_trigger_sos.
    Volume alone never fires SOS.

    Stage 8: confirm-first metadata is always attached; AI never auto-sends when
    AI_AUTO_SOS_ENABLED is false.
    """
    started = time.perf_counter()
    fusion = compute_confidence_score(
        audio_score=audio_score,
        movement_score=movement_score,
        heart_rate_spike=heart_rate_spike,
        is_night=is_night,
        is_isolated=is_isolated,
        phrase_score=phrase_score,
        volume_score=volume_score,
        detected_phrase=detected_phrase,
        phrase_language=phrase_language,
        fall_detected=fall_detected,
    )
    action = fusion.get("action", "nothing")
    needs_confirm = action in ("confirm_30s", "fire_immediately")
    fusion["confirm_first"] = {
        "beta": True,
        "requires_user_confirmation": needs_confirm,
        "countdown_seconds": 30,
        "ai_auto_sos_enabled": ai_auto_sos_allowed(),
        "no_response_policy": (
            "DISMISS_SAFE_NO_ALERT"
            if not ai_auto_sos_allowed()
            else "CONTRACT_DEMO_SIMULATION_ONLY"
        ),
        "fall_bypasses_confirm_ui": False,
        "real_alert_allowed": False if not ai_auto_sos_allowed() else action == "fire_immediately",
    }
    latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
    metrics.observe_ms("ai_confidence_fusion", latency_ms)
    metrics.incr("ai_confidence_requests_total")
    metrics.incr(f"ai_action_{action}")

    # Stage 11: scores/action only — never log detected_phrase / audio / coords
    logger.info(
        "AI confidence action=%s score=%s confirm_first=%s fall=%s auto_sos=%s "
        "latency_ms=%s has_phrase_score=%s",
        action,
        fusion.get("total_score"),
        needs_confirm,
        fall_detected,
        ai_auto_sos_allowed(),
        latency_ms,
        phrase_score > 0,
    )
    write_audit_event(
        "ai_inference",
        detail={
            "action": action,
            "total_score": fusion.get("total_score"),
            "risk_level": fusion.get("risk_level"),
            "fall_detected": fall_detected,
            "latency_ms": latency_ms,
            "audio_score_bucket": _score_bucket(audio_score),
            "movement_score_bucket": _score_bucket(movement_score),
            "phrase_score_bucket": _score_bucket(phrase_score),
            "real_alert_allowed": fusion["confirm_first"]["real_alert_allowed"],
        },
    )
    return fusion


def _score_bucket(score: float) -> str:
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "na"
    if s < 0.2:
        return "low"
    if s < 0.55:
        return "mid"
    if s < 0.75:
        return "high"
    return "very_high"


# ── AI-triggered alerts ───────────────────────────────────────────────────────

def handle_audio_sos(
    db: Session,
    user_id: UUID,
    audio_score: float,
    movement_score: float = 0.0,
    latitude: float = None,
    longitude: float = None,
    is_night: bool = None,
    is_isolated: bool = False,
    phrase_score: float = 0.0,
    volume_score: float = 0.0,
    detected_phrase: str = None,
    phrase_language: str = None,
) -> dict:
    """
    Handle an SOS event from the audio / multi-signal path.

    Runs Safety Decision Engine first. If action is fire_immediately,
    triggers the existing alert pipeline. SOS flow unchanged.
    """
    fusion = compute_fused_confidence(
        audio_score=audio_score,
        movement_score=movement_score,
        is_night=is_night,
        is_isolated=is_isolated,
        phrase_score=phrase_score,
        volume_score=volume_score,
        detected_phrase=detected_phrase,
        phrase_language=phrase_language,
    )

    result = {
        "fusion": fusion,
        "alert": None,
        "ai_auto_sos_enabled": ai_auto_sos_allowed(),
    }

    if fusion["action"] == "fire_immediately":
        if not ai_auto_sos_allowed():
            logger.warning(
                "AI audio SOS blocked (AI_AUTO_SOS_ENABLED=false) user=%s score=%s",
                user_id,
                fusion.get("total_score"),
            )
            result.update(_blocked_ai_auto_sos({"fusion": fusion}))
            return result
        try:
            alert, _notification = trigger_alert(
                db=db,
                user_id=user_id,
                trigger_type="ai_audio",
                latitude=latitude,
                longitude=longitude,
            )
            result["alert"] = str(alert.id)
            logger.warning(
                f"AI audio SOS fired for user {user_id} — "
                f"audio={audio_score:.1f} movement={movement_score:.1f} "
                f"score={fusion['total_score']}"
            )
        except ValueError as e:
            logger.error(f"Audio SOS trigger failed: {e}")
            result["trigger_error"] = str(e)

    elif fusion["action"] in ("confirm_30s", "silent_vibration"):
        # App should show a confirmation UI; this backend call just returns the score
        logger.info(
            f"AI audio: action={fusion['action']} score={fusion['total_score']} "
            f"for user {user_id} — waiting for app confirmation"
        )

    return result


def handle_movement_sos(
    db: Session,
    user_id: UUID,
    movement_score: float,
    fall_detected: bool = False,
    audio_score: float = 0.0,
    latitude: float = None,
    longitude: float = None,
    is_night: bool = None,
    is_isolated: bool = False,
) -> dict:
    """
    Handle a panic movement event.

    A confirmed fall (fall_detected=True with no-response) fires immediately
    regardless of the fusion score — it's a hard signal.

    A high movement score without fall goes through normal fusion.
    """
    # Fall with no user response = fire immediately (still gated by AI_AUTO_SOS_ENABLED)
    if fall_detected:
        if not ai_auto_sos_allowed():
            logger.warning(
                "Fall-confirmed AI SOS blocked (AI_AUTO_SOS_ENABLED=false) user=%s",
                user_id,
            )
            return _blocked_ai_auto_sos(
                {"fusion": None, "fall_detected": True, "would_have_reason": "fall_confirmed"}
            )
        try:
            alert, _notification = trigger_alert(
                db=db,
                user_id=user_id,
                trigger_type="ai_movement",
                latitude=latitude,
                longitude=longitude,
            )
            logger.warning(f"Fall-confirmed SOS fired for user {user_id}")
            return {
                "fusion": None,
                "alert": str(alert.id),
                "reason": "fall_confirmed",
                "ai_auto_sos_enabled": True,
            }
        except ValueError as e:
            logger.error(f"Fall SOS trigger failed: {e}")
            return {
                "fusion": None,
                "alert": None,
                "reason": "trigger_failed",
                "trigger_error": str(e),
                "ai_auto_sos_enabled": True,
            }

    # Normal movement score path — sensor fusion
    fusion = compute_fused_confidence(
        audio_score=audio_score,
        movement_score=movement_score,
        is_night=is_night,
        is_isolated=is_isolated,
    )

    result = {
        "fusion": fusion,
        "alert": None,
        "ai_auto_sos_enabled": ai_auto_sos_allowed(),
    }

    if fusion["action"] == "fire_immediately":
        if not ai_auto_sos_allowed():
            logger.warning(
                "AI movement SOS blocked (AI_AUTO_SOS_ENABLED=false) user=%s score=%s",
                user_id,
                fusion.get("total_score"),
            )
            result.update(_blocked_ai_auto_sos({"fusion": fusion}))
            return result
        try:
            alert, _notification = trigger_alert(
                db=db,
                user_id=user_id,
                trigger_type="ai_movement",
                latitude=latitude,
                longitude=longitude,
            )
            result["alert"] = str(alert.id)
            logger.warning(
                f"AI movement SOS fired for user {user_id} — "
                f"movement={movement_score:.1f} score={fusion['total_score']}"
            )
        except ValueError as e:
            logger.error(f"Movement SOS trigger failed: {e}")
            result["trigger_error"] = str(e)

    return result
