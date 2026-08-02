from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime


class HelperResponse(BaseModel):
    id: UUID
    alert_id: UUID
    status: str
    notified_at: datetime
    identity_revealed: bool
    approved_by_user: bool
    # name/phone only revealed if identity_revealed=True
    name: Optional[str] = None
    phone_number: Optional[str] = None

    class Config:
        from_attributes = True


class BlocklistCreate(BaseModel):
    blocked_phone: str


class BlocklistResponse(BaseModel):
    id: UUID
    blocked_phone: str

    class Config:
        from_attributes = True
