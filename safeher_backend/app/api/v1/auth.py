from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta

from app.db.session import get_db
from app.models.user import User
from app.schemas.user_schema import UserRegister, UserLogin, OTPVerify, OTPSend, TokenResponse
from app.config import settings
from app.services import otp_service
from app.services.redis_service import check_rate_limit

router = APIRouter(prefix="/auth", tags=["Authentication"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


def _authenticate_user(db: Session, phone_number: str, password: str) -> User:
    """Shared login logic for JSON and OAuth2 (Swagger) flows."""
    user = db.query(User).filter(User.phone_number == phone_number).first()
    if not user or not _verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def _rate_limit_auth(request: Request) -> None:
    """
    Apply rate limiting to auth endpoints.
    Keyed on client IP so attackers can't enumerate phone numbers at scale.
    """
    ip = request.client.host if request.client else "unknown"
    allowed = check_rate_limit(
        identifier=f"auth:{ip}",
        limit=settings.RATE_LIMIT_AUTH_PER_MINUTE,
        window_seconds=60
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait before trying again."
        )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(
    payload: UserRegister,
    request: Request,
    db: Session = Depends(get_db)
):
    """Register a new user with phone number."""
    _rate_limit_auth(request)

    existing = db.query(User).filter(User.phone_number == payload.phone_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Phone number already registered")

    user = User(
        phone_number=payload.phone_number,
        name=payload.name,
        city=payload.city,
        hashed_password=_hash_password(payload.password),
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Send OTP for phone verification
    otp_service.send_otp(payload.phone_number)

    token = _create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    """Login with phone number and password (JSON — used by the Android app)."""
    _rate_limit_auth(request)

    user = _authenticate_user(db, payload.phone_number, payload.password)
    token = _create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.post("/token", response_model=TokenResponse)
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    OAuth2-compatible token endpoint for Swagger **Authorize** and other OAuth2 clients.

    Use **username** = phone number (e.g. `9876543210`) and **password** = account password.
    Returns a bearer token attached automatically to protected endpoints in `/docs`.
    """
    _rate_limit_auth(request)

    user = _authenticate_user(db, form_data.username, form_data.password)
    token = _create_access_token(str(user.id))
    return TokenResponse(access_token=token)


def _rate_limit_otp_phone(phone_number: str) -> None:
    """Per-phone OTP send limit (independent of IP auth bucket)."""
    allowed = check_rate_limit(
        identifier=f"otp:{phone_number}",
        limit=settings.RATE_LIMIT_OTP_PER_PHONE_PER_MINUTE,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests for this number. Please wait before trying again.",
        )


@router.post("/send-otp")
def send_otp(
    payload: OTPSend,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Send OTP to a phone number for verification.
    Rate limited by IP and per-phone to prevent SMS spam.
    """
    _rate_limit_auth(request)
    _rate_limit_otp_phone(payload.phone_number)

    sent = otp_service.send_otp(payload.phone_number)
    if not sent:
        raise HTTPException(status_code=500, detail="Failed to send OTP. Try again later.")
    return {"message": "OTP sent successfully"}


@router.post("/verify-otp")
def verify_otp(
    payload: OTPVerify,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Verify OTP sent to phone number. Marks user as verified on success.
    """
    _rate_limit_auth(request)

    verified = otp_service.verify_otp(payload.phone_number, payload.otp)
    if not verified:
        raise HTTPException(
            status_code=400,
            detail="Invalid, expired, or too many OTP attempts. Request a new OTP.",
        )

    user = db.query(User).filter(User.phone_number == payload.phone_number).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found for this phone number")

    user.is_verified = True
    db.commit()

    return {"message": "Phone number verified successfully"}


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(db: Session = Depends(get_db)):
    """Refresh expired JWT token — V2: use refresh token stored securely."""
    raise HTTPException(status_code=501, detail="Use /auth/login to get a new token")
