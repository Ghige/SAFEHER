import uuid
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.database import Base


class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name          = Column(String(100), nullable=False)
    phone_number  = Column(String(15), nullable=False)
    relationship_type = Column(String(50), nullable=True)  # Mom, Friend, Sister etc
    ring_priority = Column(Integer, default=1)          # 1, 2, 3 — alert order
    is_active     = Column(Boolean, default=True)

    user = relationship("User", back_populates="contacts")
