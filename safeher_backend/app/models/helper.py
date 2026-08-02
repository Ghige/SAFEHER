import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Helper(Base):
    __tablename__ = "helpers"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id         = Column(UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=False)
    helper_user_id   = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status           = Column(String(20), default="notified")  # notified/responding/arrived/cancelled
    notified_at      = Column(DateTime(timezone=True), server_default=func.now())
    identity_revealed= Column(Boolean, default=False)   # hidden until user approves
    approved_by_user = Column(Boolean, default=False)

    alert  = relationship("Alert", back_populates="helpers")
    helper = relationship("User", foreign_keys=[helper_user_id])
