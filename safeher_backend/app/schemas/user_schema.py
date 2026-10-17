from pydantic import BaseModel, ConfigDict, Field, field_validator
from uuid import UUID
from typing import Optional
import re


def _normalize_phone(v: str) -> str:
    v = v.strip().replace(" ", "").replace("-", "")
    if not re.match(r"^\+?[0-9]{10,15}$", v):
        raise ValueError("Invalid phone number")
    return v


class UserRegister(BaseModel):
    phone_number: str
    name: str = Field(..., min_length=1, max_length=100)
    password: str
    city: Optional[str] = Field(None, max_length=100)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        return _normalize_phone(v)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        name = v.strip()
        if not name:
            raise ValueError("Name is required")
        return name

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserLogin(BaseModel):
    phone_number: str
    password: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        return _normalize_phone(v)


class OTPSend(BaseModel):
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        return _normalize_phone(v)


class OTPVerify(BaseModel):
    phone_number: str
    otp: str = Field(..., min_length=6, max_length=6)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        return _normalize_phone(v)

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 6:
            raise ValueError("OTP must be exactly 6 digits")
        return v


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
    name: str = Field(..., min_length=1, max_length=100)
    phone_number: str
    relationship: Optional[str] = Field(None, max_length=50)
    ring_priority: int = Field(1, ge=1, le=5)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        name = v.strip()
        if not name:
            raise ValueError("Name is required")
        return name

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        return _normalize_phone(v)


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
