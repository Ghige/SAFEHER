from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from uuid import UUID
from typing import Optional, Literal
from datetime import datetime

TriggerType = Literal["manual", "voice", "ai_audio", "ai_movement", "shake"]


class AlertTrigger(BaseModel):
    trigger_type: TriggerType
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def coords_must_be_paired(self):
        if (self.latitude is None) ^ (self.longitude is None):
            raise ValueError("latitude and longitude must both be provided or both omitted")
        return self


class AlertResponse(BaseModel):
    id: UUID
    trigger_type: str
    latitude: Optional[float]
    longitude: Optional[float]
    status: str
    started_at: datetime
    ended_at: Optional[datetime]
    evidence_url: Optional[str]

    model_config = ConfigDict(from_attributes=True)

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def decimal_to_float(cls, v):
        return float(v) if v is not None else None


class LocationUpdate(BaseModel):
    alert_id: UUID
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class AlertTriggerResponse(AlertResponse):
    """Alert trigger response including WhatsApp delivery summary."""

    whatsapp_sent_count: int = 0
    whatsapp_failed_count: int = 0
    whatsapp_all_delivered: bool = False


class PingRequest(BaseModel):
    alert_id: UUID
