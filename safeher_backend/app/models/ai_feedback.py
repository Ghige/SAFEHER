import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.db.database import Base


class AiFeedbackEvent(Base):
    """Privacy-safe AI prediction feedback. Never gold training data by default."""

    __tablename__ = "ai_feedback_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_ai_feedback_events_event_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    model_version = Column(String(32), nullable=False)
    signal_type = Column(String(20), nullable=False)
    prediction_state = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=True)
    candidate_category = Column(String(48), nullable=False)
    user_feedback = Column(String(32), nullable=False)
    outcome = Column(String(32), nullable=False)
    fp_fn_status = Column(String(48), nullable=False)
    consent_status = Column(String(24), nullable=False)
    consent_version = Column(String(64), nullable=False)
    review_status = Column(String(24), nullable=False, default="UNREVIEWED")
    reviewer_id = Column(String(64), nullable=True)
    license_status = Column(String(32), nullable=False)
    final_verdict = Column(String(24), nullable=True)
    source = Column(String(32), nullable=False, default="real_world_app")
    gold_eligible = Column(Boolean, nullable=False, default=False)
    split_bucket = Column(String(16), nullable=True)
    notes = Column(Text, nullable=True)
    features = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
