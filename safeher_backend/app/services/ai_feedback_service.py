"""
Privacy-safe AI feedback events.

Predictions NEVER become GOLD automatically.
Raw microphone, precise location, and phone numbers are rejected.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ai_feedback import AiFeedbackEvent

logger = logging.getLogger(__name__)

CONSENT_VERSION = "privacy-v2-metadata-only"

CANDIDATE_CATEGORIES = frozenset({
    "AI_POSITIVE_CANDIDATE",
    "AI_FALSE_POSITIVE_CANDIDATE",
    "AI_FALSE_NEGATIVE_CANDIDATE",
    "USER_CONFIRMED_DISTRESS",
    "USER_CONFIRMED_NORMAL",
    "UNREVIEWED",
})

USER_FEEDBACK_VALUES = frozenset({
    "CONFIRMED_EMERGENCY",
    "CONFIRMED_NORMAL",
    "CANCELLED",
    "TIMEOUT",
    "NONE",
})

SIGNAL_TYPES = frozenset({"audio", "speech", "movement"})
PREDICTION_STATES = frozenset({"SUSPICIOUS", "EMERGENCY", "NORMAL", "OTHER"})
OUTCOMES = frozenset({"NO_ALERT", "MANUAL_SOS_OPENED", "BLOCKED", "UNKNOWN"})

ALLOWED_FEATURE_KEYS = frozenset({
    "rms",
    "peak",
    "zcr",
    "pitch_hz",
    "centroid_hz",
    "rolling_avg",
    "duration_seconds",
})

FORBIDDEN_FEATURE_KEYS = frozenset({
    "latitude",
    "longitude",
    "lat",
    "lon",
    "phone",
    "phone_number",
    "transcript",
    "detected_phrase",
    "wav",
    "pcm",
    "audio",
    "audio_b64",
    "path",
    "storage_path",
    "name",
    "email",
})

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def classify_feedback(
    *,
    user_feedback: str,
    prediction_state: str,
) -> tuple[str, str]:
    """Return (candidate_category, fp_fn_status). Never a gold label."""
    uf = user_feedback.upper().strip()
    pred = prediction_state.upper().strip()

    if uf == "CONFIRMED_EMERGENCY":
        return "USER_CONFIRMED_DISTRESS", "DISTRESS_CANDIDATE"
    if uf in {"CANCELLED", "CONFIRMED_NORMAL"}:
        if pred in {"EMERGENCY", "SUSPICIOUS"}:
            return "AI_FALSE_POSITIVE_CANDIDATE", "HARD_NEGATIVE_CANDIDATE"
        return "USER_CONFIRMED_NORMAL", "HARD_NEGATIVE_CANDIDATE"
    if uf == "TIMEOUT":
        return "UNREVIEWED", "UNREVIEWED"
    if uf == "NONE" and pred == "NORMAL":
        return "AI_FALSE_NEGATIVE_CANDIDATE", "FALSE_NEGATIVE_CANDIDATE"
    return "UNREVIEWED", "UNREVIEWED"


def sanitize_features(raw: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    if not isinstance(raw, dict):
        raise ValueError("features must be an object")
    for key in raw:
        lk = str(key).lower()
        if lk in FORBIDDEN_FEATURE_KEYS:
            raise ValueError(f"Forbidden feature key rejected: {key}")
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in ALLOWED_FEATURE_KEYS:
            continue
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, (int, float)):
            cleaned[key] = float(value)
    return cleaned or None


def _require_id(value: str, field: str) -> str:
    v = (value or "").strip()
    if not v or len(v) > 64:
        raise ValueError(f"{field} is required (max 64 chars)")
    if field == "event_id" and not _UUID_RE.match(v):
        raise ValueError("event_id must be a UUID")
    return v


def record_feedback_event(
    db: Session,
    *,
    user_id: Optional[uuid.UUID],
    event_id: str,
    session_id: str,
    model_version: str,
    signal_type: str,
    prediction_state: str,
    confidence: Optional[float],
    user_feedback: str,
    outcome: str,
    consent_granted: bool,
    consent_version: str,
    features: Optional[dict[str, Any]] = None,
) -> AiFeedbackEvent:
    if not consent_granted:
        raise ValueError("consent_granted must be true to record feedback")
    if (consent_version or "").strip() != CONSENT_VERSION:
        raise ValueError(f"consent_version must be {CONSENT_VERSION}")

    event_id = _require_id(event_id, "event_id")
    session_id = _require_id(session_id, "session_id")
    model_version = (model_version or "").strip()
    if not model_version or len(model_version) > 32:
        raise ValueError("model_version is required")

    signal_type = (signal_type or "").strip().lower()
    if signal_type not in SIGNAL_TYPES:
        raise ValueError("signal_type must be audio, speech, or movement")

    prediction_state = (prediction_state or "").strip().upper()
    if prediction_state not in PREDICTION_STATES:
        raise ValueError("invalid prediction_state")

    user_feedback = (user_feedback or "").strip().upper()
    if user_feedback not in USER_FEEDBACK_VALUES:
        raise ValueError("invalid user_feedback")

    outcome = (outcome or "").strip().upper()
    if outcome not in OUTCOMES:
        raise ValueError("invalid outcome")

    if confidence is not None and not (0.0 <= float(confidence) <= 100.0):
        raise ValueError("confidence must be 0-100")

    existing = db.query(AiFeedbackEvent).filter(AiFeedbackEvent.event_id == event_id).first()
    if existing:
        return existing

    category, fp_fn = classify_feedback(
        user_feedback=user_feedback,
        prediction_state=prediction_state,
    )
    cleaned = sanitize_features(features)

    row = AiFeedbackEvent(
        id=uuid.uuid4(),
        event_id=event_id,
        session_id=session_id,
        user_id=user_id,
        model_version=model_version,
        signal_type=signal_type,
        prediction_state=prediction_state,
        confidence=float(confidence) if confidence is not None else None,
        candidate_category=category,
        user_feedback=user_feedback,
        outcome=outcome,
        fp_fn_status=fp_fn,
        consent_status="GRANTED",
        consent_version=CONSENT_VERSION,
        review_status="UNREVIEWED",
        reviewer_id=None,
        license_status="USER_CONSENT_OPT_IN",
        final_verdict=None,
        source="real_world_app",
        gold_eligible=False,
        split_bucket=None,
        features=cleaned,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(AiFeedbackEvent).filter(AiFeedbackEvent.event_id == event_id).first()
        )
        if existing:
            return existing
        raise
    db.refresh(row)
    logger.info(
        "AI feedback recorded event_id=%s category=%s gold_eligible=%s",
        event_id,
        category,
        False,
    )
    return row


def anonymize_user_feedback(db: Session, user_id: uuid.UUID) -> int:
    """Keep metadata candidates; drop the user foreign key on account deletion."""
    rows = (
        db.query(AiFeedbackEvent)
        .filter(AiFeedbackEvent.user_id == user_id)
        .all()
    )
    n = 0
    for row in rows:
        row.user_id = None
        row.consent_status = "WITHDRAWN"
        n += 1
    return n


def purge_unreviewed_feedback(db: Session, days: int) -> int:
    if days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(AiFeedbackEvent)
        .filter(
            AiFeedbackEvent.review_status == "UNREVIEWED",
            AiFeedbackEvent.created_at < cutoff,
            AiFeedbackEvent.gold_eligible.is_(False),
        )
        .all()
    )
    removed = 0
    for row in rows:
        db.delete(row)
        removed += 1
    if removed:
        db.commit()
        logger.info("Purged %s unreviewed AI feedback events older than %s days", removed, days)
    return removed


def event_to_dict(row: AiFeedbackEvent) -> dict[str, Any]:
    return {
        "event_id": row.event_id,
        "session_id": row.session_id,
        "model_version": row.model_version,
        "signal_type": row.signal_type,
        "prediction_state": row.prediction_state,
        "confidence": row.confidence,
        "candidate_category": row.candidate_category,
        "user_feedback": row.user_feedback,
        "outcome": row.outcome,
        "fp_fn_status": row.fp_fn_status,
        "consent_status": row.consent_status,
        "consent_version": row.consent_version,
        "review_status": row.review_status,
        "reviewer_id": row.reviewer_id,
        "license_status": row.license_status,
        "final_verdict": row.final_verdict,
        "source": row.source,
        "gold_eligible": bool(row.gold_eligible),
        "split_bucket": row.split_bucket,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
