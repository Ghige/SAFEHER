"""
AI model endpoints — receive SOS events from the on-device AI models
and run sensor fusion before deciding whether to fire an alert.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, model_validator
from typing import Optional

from app.db.session import get_db
from app.api.deps import get_current_user, get_verified_user
from app.models.user import User
from app.services.ai_alert_service import (
    handle_audio_sos,
    handle_movement_sos,
    compute_fused_confidence,
)
from app.services.ai_dataset_service import (
    get_latest_model_version,
)
from app.services.ai_feedback_service import (
    CONSENT_VERSION,
    event_to_dict,
    record_feedback_event,
)
from app.services.redis_service import check_rate_limit
from app.config import settings

router = APIRouter(prefix="/ai", tags=["AI Models"])


class _CoordValidationMixin(BaseModel):
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def coords_must_be_paired(self):
        if (self.latitude is None) ^ (self.longitude is None):
            raise ValueError("latitude and longitude must both be provided or both omitted")
        return self


class AudioSOSPayload(_CoordValidationMixin):
    audio_score: float = Field(..., ge=0, le=100)
    movement_score: float = Field(0.0, ge=0, le=100)
    phrase_score: float = Field(0.0, ge=0, le=100)
    volume_score: float = Field(0.0, ge=0, le=100)
    detected_phrase: Optional[str] = None
    phrase_language: Optional[str] = None
    is_night: Optional[bool] = None
    is_isolated: bool = False


class MovementSOSPayload(_CoordValidationMixin):
    movement_score: float = Field(..., ge=0, le=100)
    fall_detected: bool = False
    audio_score: float = Field(0.0, ge=0, le=100)
    phrase_score: float = Field(0.0, ge=0, le=100)
    is_night: Optional[bool] = None
    is_isolated: bool = False


class FusionQueryPayload(BaseModel):
    audio_score: float = Field(0.0, ge=0, le=100)
    movement_score: float = Field(0.0, ge=0, le=100)
    phrase_score: float = Field(0.0, ge=0, le=100)
    volume_score: float = Field(0.0, ge=0, le=100)
    detected_phrase: Optional[str] = None
    phrase_language: Optional[str] = None
    heart_rate_spike: bool = False
    is_night: Optional[bool] = None
    is_isolated: bool = False
    fall_detected: bool = False


class PhraseDetectPayload(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=500)


def _rate_limit_ai_sos(request: Request, user_id: str) -> None:
    allowed = check_rate_limit(
        identifier=f"ai_sos:{user_id}",
        limit=settings.RATE_LIMIT_ALERT_PER_MINUTE,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many AI SOS requests.")


@router.post("/audio-sos")
def audio_sos(
    payload: AudioSOSPayload,
    request: Request,
    current_user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """
    Called by AudioMonitor when distress audio is confirmed.
    Runs sensor fusion and fires an alert if score >= 80.
    Returns the fusion result and alert ID (if fired).
    """
    _rate_limit_ai_sos(request, str(current_user.id))
    result = handle_audio_sos(
        db=db,
        user_id=current_user.id,
        audio_score=payload.audio_score,
        movement_score=payload.movement_score,
        latitude=payload.latitude,
        longitude=payload.longitude,
        is_night=payload.is_night,
        is_isolated=payload.is_isolated,
        phrase_score=payload.phrase_score,
        volume_score=payload.volume_score,
        detected_phrase=payload.detected_phrase,
        phrase_language=payload.phrase_language,
    )
    return result


@router.post("/movement-sos")
def movement_sos(
    payload: MovementSOSPayload,
    request: Request,
    current_user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """
    Called by the movement model when panic movement or a fall is detected.
    Fall with no-response fires immediately. High movement score goes through fusion.
    """
    _rate_limit_ai_sos(request, str(current_user.id))
    result = handle_movement_sos(
        db=db,
        user_id=current_user.id,
        movement_score=payload.movement_score,
        fall_detected=payload.fall_detected,
        audio_score=payload.audio_score,
        latitude=payload.latitude,
        longitude=payload.longitude,
        is_night=payload.is_night,
        is_isolated=payload.is_isolated,
    )
    return result


@router.post("/confidence")
def confidence_score(
    payload: FusionQueryPayload,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Query the sensor fusion score without firing an alert.
    Useful for the app to decide whether to show a warning UI.
    """
    allowed = check_rate_limit(
        identifier=f"ai_confidence:{current_user.id}",
        limit=settings.RATE_LIMIT_CONFIDENCE_PER_MINUTE,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many confidence requests.")
    return compute_fused_confidence(
        audio_score=payload.audio_score,
        movement_score=payload.movement_score,
        heart_rate_spike=payload.heart_rate_spike,
        is_night=payload.is_night,
        is_isolated=payload.is_isolated,
        phrase_score=payload.phrase_score,
        volume_score=payload.volume_score,
        detected_phrase=payload.detected_phrase,
        phrase_language=payload.phrase_language,
        fall_detected=payload.fall_detected,
    )


@router.post("/detect-phrase")
def detect_phrase(
    payload: PhraseDetectPayload,
    current_user: User = Depends(get_current_user),
):
    """Score emergency phrases from a transcript (extensible catalog)."""
    from app.ai.speech_phrase_detector import detect_emergency_phrase

    result = detect_emergency_phrase(payload.transcript)
    return {
        "phrase_detected": result.phrase_detected,
        "phrase_score": result.phrase_score,
        "language": result.language,
        "phrase": result.phrase,
    }


class ModelVersionResponse(BaseModel):
    model_type: str
    version: str
    status: str
    artifact_path: Optional[str] = None


class DatasetQueueResponse(BaseModel):
    sample_id: str
    status: str


class FeedbackPayload(BaseModel):
    event_id: str = Field(..., min_length=36, max_length=64)
    session_id: str = Field(..., min_length=8, max_length=64)
    model_version: str = Field(..., min_length=1, max_length=32)
    signal_type: str = Field(..., min_length=3, max_length=20)
    prediction_state: str = Field(..., min_length=3, max_length=32)
    confidence: Optional[float] = Field(None, ge=0, le=100)
    user_feedback: str = Field(..., min_length=3, max_length=32)
    outcome: str = Field(..., min_length=3, max_length=32)
    consent_granted: bool = False
    consent_version: str = Field(..., min_length=1, max_length=64)
    features: Optional[dict] = None


class FeedbackResponse(BaseModel):
    event_id: str
    candidate_category: str
    review_status: str
    gold_eligible: bool
    fp_fn_status: str


@router.get("/models/latest", response_model=ModelVersionResponse)
def latest_model_version(
    model_type: str = "audio",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the active production model version for on-device clients."""
    record = get_latest_model_version(db, model_type=model_type)
    if not record:
        raise HTTPException(status_code=404, detail="No active model version found")
    return ModelVersionResponse(
        model_type=record.model_type,
        version=record.version,
        status=record.status,
        artifact_path=record.artifact_path,
    )


@router.post("/datasets/queue", response_model=DatasetQueueResponse)
async def queue_ai_dataset_sample(
    request: Request,
    audio: UploadFile = File(...),
    model_version: str = Form(...),
    ai_confidence: Optional[float] = Form(None),
    user_confirmation: Optional[bool] = Form(None),
    label: Optional[str] = Form(None),
    duration_seconds: Optional[float] = Form(None),
    features_json: Optional[str] = Form(None),
    device_info_json: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retired: raw WAV uploads are not accepted. Use POST /ai/feedback."""
    raise HTTPException(
        status_code=410,
        detail=(
            "Raw audio dataset upload is retired. "
            "Use POST /api/v1/ai/feedback (metadata only). "
            "Microphone recordings are not stored."
        ),
    )


@router.post("/feedback", response_model=FeedbackResponse)
def submit_ai_feedback(
    payload: FeedbackPayload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Record a privacy-safe AI feedback candidate.
    Never promotes to GOLD. Never trains. Never stores WAV/location/phone.
    """
    allowed = check_rate_limit(
        identifier=f"ai_feedback:{current_user.id}",
        limit=settings.RATE_LIMIT_DATASET_PER_MINUTE,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many feedback events.")
    if not payload.consent_granted:
        raise HTTPException(
            status_code=403,
            detail="Help-improve consent is required to record AI feedback.",
        )
    if payload.consent_version != CONSENT_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"consent_version must be {CONSENT_VERSION}",
        )
    try:
        row = record_feedback_event(
            db,
            user_id=current_user.id,
            event_id=payload.event_id,
            session_id=payload.session_id,
            model_version=payload.model_version,
            signal_type=payload.signal_type,
            prediction_state=payload.prediction_state,
            confidence=payload.confidence,
            user_feedback=payload.user_feedback,
            outcome=payload.outcome,
            consent_granted=payload.consent_granted,
            consent_version=payload.consent_version,
            features=payload.features,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    body = event_to_dict(row)
    return FeedbackResponse(
        event_id=body["event_id"],
        candidate_category=body["candidate_category"],
        review_status=body["review_status"],
        gold_eligible=False,
        fp_fn_status=body["fp_fn_status"],
    )
