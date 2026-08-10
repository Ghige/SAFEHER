import uuid
from sqlalchemy import Column, String, DateTime, Text, Float, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.database import Base


class AiModelVersion(Base):
    __tablename__ = "ai_model_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_type = Column(String(32), nullable=False)
    version = Column(String(32), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    artifact_path = Column(Text, nullable=True)
    metrics = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AiDatasetSample(Base):
    __tablename__ = "ai_dataset_samples"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    modality = Column(String(20), nullable=False, default="audio")
    model_version = Column(String(32), nullable=False)
    ai_confidence = Column(Float, nullable=True)
    user_confirmation = Column(Boolean, nullable=True)
    label = Column(String(64), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    features = Column(JSONB, nullable=True)
    device_info = Column(JSONB, nullable=True)
    storage_path = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
