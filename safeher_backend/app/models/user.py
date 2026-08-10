import uuid
from sqlalchemy import Column, String, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number    = Column(String(15), unique=True, nullable=False, index=True)
    name            = Column(String(100), nullable=False)
    city            = Column(String(50), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_verified     = Column(Boolean, default=False, nullable=False)   # phone OTP verified
    drive_token     = Column(Text, nullable=True)                      # Fernet-encrypted OAuth token
    fcm_token       = Column(String(512), nullable=True)               # Firebase Cloud Messaging device token
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    last_active     = Column(DateTime(timezone=True), onupdate=func.now())

    # relationships
    contacts  = relationship("EmergencyContact", back_populates="user", cascade="all, delete")
    alerts    = relationship("Alert", back_populates="user", cascade="all, delete")
    blocklist = relationship("Blocklist", back_populates="user", cascade="all, delete")
