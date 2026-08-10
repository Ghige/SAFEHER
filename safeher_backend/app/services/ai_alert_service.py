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
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.user import User
from app.services.alert_service import trigger_alert, get_active_alert
from app.ai.confidence_scorer import compute_confidence_score

logger = logging.getLogger(__name__)


# ── Sensor fusion ─────────────────────────────────────────────────────────────

def compute_fused_confidence(
    audio_score: float = 0.0,
    movement_score: float = 0.0,
    heart_rate_spike: bool = False,
    is_night: bool = None,
    is_isolated: bool = False,
) -> dict:
    """
    Compute combined confidence score from available sensor signals.

    Returns the full scoring dict from confidence_scorer including:
        total_score, action, activate_gps_stream, and all inputs.

    The action field tells the app what to do:
        "nothing"          → ignore
        "silent_vibration" → gentle haptic, no UI (score 40-59)
        "confirm_30s"      → vibrate + show cancel button (score 60-79)
        "fire_immediately" → fire SOS without confirmation (score 80+)
    """
    return compute_confidence_score(
        audio_score=audio_score,
        movement_score=movement_score,
        heart_rate_spike=heart_rate_spike,
        is_night=is_night,
        is_isolated=is_isolated,
    )


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
) -> dict:
    """
    Handle an SOS event from the audio monitor.

    Runs sensor fusion first. If the combined score is high enough,
    triggers an alert. Returns the fusion result and alert (if fired).

    Args:
        audio_score:    confidence from AudioMonitor SOSEvent (0-100)
        movement_score: concurrent movement model score (0-100), 0 if unavailable
    """
    fusion = compute_fused_confidence(
        audio_score=audio_score,
        movement_score=movement_score,
        is_night=is_night,
        is_isolated=is_isolated,
    )

    result = {"fusion": fusion, "alert": None}

    if fusion["action"] == "fire_immediately":
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
    # Fall with no user response = fire immediately
    if fall_detected:
        try:
            alert, _notification = trigger_alert(
                db=db,
                user_id=user_id,
                trigger_type="ai_movement",
                latitude=latitude,
                longitude=longitude,
            )
            logger.warning(f"Fall-confirmed SOS fired for user {user_id}")
            return {"fusion": None, "alert": str(alert.id), "reason": "fall_confirmed"}
        except ValueError as e:
            logger.error(f"Fall SOS trigger failed: {e}")
            return {"fusion": None, "alert": None, "reason": "trigger_failed", "trigger_error": str(e)}

    # Normal movement score path — sensor fusion
    fusion = compute_fused_confidence(
        audio_score=audio_score,
        movement_score=movement_score,
        is_night=is_night,
        is_isolated=is_isolated,
    )

    result = {"fusion": fusion, "alert": None}

    if fusion["action"] == "fire_immediately":
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
