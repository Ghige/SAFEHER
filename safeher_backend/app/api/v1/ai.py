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
    queue_dataset_sample,
    parse_features_json,
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
    is_night: Optional[bool] = None
    is_isolated: bool = False


class MovementSOSPayload(_CoordValidationMixin):
    movement_score: float = Field(..., ge=0, le=100)
    fall_detected: bool = False
    audio_score: float = Field(0.0, ge=0, le=100)
    is_night: Optional[bool] = None
    is_isolated: bool = False


class FusionQueryPayload(BaseModel):
    audio_score: float = Field(0.0, ge=0, le=100)
    movement_score: float = Field(0.0, ge=0, le=100)
    heart_rate_spike: bool = False
    is_night: Optional[bool] = None
    is_isolated: bool = False


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
    current_user: User = Depends(get_current_user),
):
    """
    Query the sensor fusion score without firing an alert.
    Useful for the app to decide whether to show a warning UI.
    """
    return compute_fused_confidence(
        audio_score=payload.audio_score,
        movement_score=payload.movement_score,
        heart_rate_spike=payload.heart_rate_spike,
        is_night=payload.is_night,
        is_isolated=payload.is_isolated,
    )


class ModelVersionResponse(BaseModel):
    model_type: str
    version: str
    status: str
    artifact_path: Optional[str] = None


class DatasetQueueResponse(BaseModel):
    sample_id: str
    status: str


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
    """
    Queue an audio clip for future retraining. Requires user opt-in on device.
    Infrastructure only — no on-server retraining.
    """
    if not audio.content_type or "audio" not in audio.content_type:
        raise HTTPException(status_code=400, detail="Upload must be an audio file")
    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio upload")

    sample = queue_dataset_sample(
        db=db,
        user_id=current_user.id,
        audio_bytes=audio_bytes,
        model_version=model_version,
        ai_confidence=ai_confidence,
        user_confirmation=user_confirmation,
        label=label,
        duration_seconds=duration_seconds,
        features=parse_features_json(features_json),
        device_info=parse_features_json(device_info_json),
    )
    return DatasetQueueResponse(sample_id=str(sample.id), status=sample.status)
