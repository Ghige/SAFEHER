import uuid
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, DECIMAL
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    trigger_type = Column(String(20), nullable=False)   # manual/voice/ai_audio/ai_movement
    latitude     = Column(DECIMAL(10, 8), nullable=True)
    longitude    = Column(DECIMAL(11, 8), nullable=True)
    status       = Column(String(20), default="active") # active/cancelled/resolved/escalated
    started_at   = Column(DateTime(timezone=True), server_default=func.now())
    ended_at     = Column(DateTime(timezone=True), nullable=True)
    evidence_url = Column(Text, nullable=True)          # Google Drive link

    user    = relationship("User", back_populates="alerts")
    helpers = relationship("Helper", back_populates="alert", cascade="all, delete")
