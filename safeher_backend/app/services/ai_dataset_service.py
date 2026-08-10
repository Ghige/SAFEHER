"""Persist AI training dataset samples and model version metadata."""

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.ai_dataset import AiDatasetSample, AiModelVersion

logger = logging.getLogger(__name__)

_DATASET_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "ai_dataset_queue"


def ensure_seed_model_versions(db: Session) -> None:
    existing = (
        db.query(AiModelVersion)
        .filter(AiModelVersion.model_type == "audio", AiModelVersion.status == "active")
        .first()
    )
    if existing:
        return
    db.add(
        AiModelVersion(
            id=uuid.uuid4(),
            model_type="audio",
            version="v1.0",
            status="active",
            artifact_path="yamnet_distress_quant.tflite",
            metrics={"description": "Initial on-device distress classifier"},
        )
    )
    db.commit()


def get_latest_model_version(db: Session, model_type: str = "audio") -> Optional[AiModelVersion]:
    ensure_seed_model_versions(db)
    return (
        db.query(AiModelVersion)
        .filter(AiModelVersion.model_type == model_type, AiModelVersion.status == "active")
        .order_by(AiModelVersion.created_at.desc())
        .first()
    )


def queue_dataset_sample(
    db: Session,
    *,
    user_id: uuid.UUID,
    audio_bytes: bytes,
    model_version: str,
    ai_confidence: Optional[float],
    user_confirmation: Optional[bool],
    label: Optional[str],
    duration_seconds: Optional[float],
    features: Optional[dict[str, Any]],
    device_info: Optional[dict[str, Any]],
) -> AiDatasetSample:
    _DATASET_ROOT.mkdir(parents=True, exist_ok=True)
    sample_id = uuid.uuid4()
    file_path = _DATASET_ROOT / f"{sample_id}.wav"
    file_path.write_bytes(audio_bytes)

    sample = AiDatasetSample(
        id=sample_id,
        user_id=user_id,
        modality="audio",
        model_version=model_version,
        ai_confidence=ai_confidence,
        user_confirmation=user_confirmation,
        label=label,
        duration_seconds=duration_seconds,
        features=features,
        device_info=device_info,
        storage_path=str(file_path),
        status="queued",
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    logger.info(
        "AI dataset sample queued id=%s user=%s model=%s label=%s confidence=%s",
        sample_id,
        user_id,
        model_version,
        label,
        ai_confidence,
    )
    return sample


def parse_features_json(raw: Optional[str]) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid features JSON for dataset upload")
        return None
