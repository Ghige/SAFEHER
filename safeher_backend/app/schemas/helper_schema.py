from pydantic import BaseModel, field_validator
from uuid import UUID
from typing import Optional
from datetime import datetime
import re


def _normalize_phone(v: str) -> str:
    v = v.strip().replace(" ", "").replace("-", "")
    if not re.match(r"^\+?[0-9]{10,15}$", v):
        raise ValueError("Invalid phone number")
    return v


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

    @field_validator("blocked_phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _normalize_phone(v)


class BlocklistResponse(BaseModel):
    id: UUID
    blocked_phone: str

    class Config:
        from_attributes = True
