from pydantic import BaseModel, ConfigDict, Field, field_validator
from uuid import UUID
from typing import Optional
import re


class UserRegister(BaseModel):
    phone_number: str
    name: str
    password: str
    city: Optional[str] = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        v = v.strip().replace(" ", "")
        if not re.match(r"^\+?[0-9]{10,15}$", v):
            raise ValueError("Invalid phone number")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserLogin(BaseModel):
    phone_number: str
    password: str


class OTPVerify(BaseModel):
    phone_number: str
    otp: str


class TokenRefresh(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    id: UUID
    phone_number: str
    name: str
    city: Optional[str]

    class Config:
        from_attributes = True


class ContactCreate(BaseModel):
    name: str
    phone_number: str
    relationship: Optional[str] = None
    ring_priority: int = 1

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        v = v.strip().replace(" ", "").replace("-", "")
        if not re.match(r"^\+?[0-9]{10,15}$", v):
            raise ValueError("Invalid phone number")
        return v


class DeviceTokenUpdate(BaseModel):
    fcm_token: str = Field(..., min_length=10, max_length=512)


class ContactResponse(BaseModel):
    id: UUID
    name: str
    phone_number: str
    relationship: Optional[str] = Field(None, validation_alias="relationship_type")
    ring_priority: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
