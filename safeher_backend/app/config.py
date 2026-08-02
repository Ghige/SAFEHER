from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/safeher_db"

    # JWT
    SECRET_KEY: str = "change-this-to-a-random-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Twilio WhatsApp
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_NUMBER: str = "whatsapp:+14155238886"

    # Firebase
    FIREBASE_CREDENTIALS_PATH: str = "./firebase-credentials.json"
    FIREBASE_DATABASE_URL: str = ""

    # Google APIs
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # App
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Alert settings
    DEAD_SWITCH_INTERVAL_SECONDS: int = 60       # ping every 60s
    DEAD_SWITCH_TIMEOUT_SECONDS: int = 180       # escalate if no ping for 3 min
    HELPER_SEARCH_RADIUS_METERS: int = 500       # find helpers within 500m
    CONFIRMATION_WINDOW_SECONDS: int = 30        # time to cancel before alert fires

    # Country code for WhatsApp (e.g. "91" for India, "1" for US)
    PHONE_COUNTRY_CODE: str = "91"

    # Rate limiting (requests per period)
    RATE_LIMIT_AUTH_PER_MINUTE: int = 5
    RATE_LIMIT_ALERT_PER_MINUTE: int = 10

    # Drive token encryption key (Fernet) — generate with: Fernet.generate_key()
    DRIVE_TOKEN_ENCRYPTION_KEY: str = ""

    # OTP settings
    OTP_EXPIRY_MINUTES: int = 10
    # OTP provider: "twilio_verify" | "mock" (mock = dev only)
    OTP_PROVIDER: str = "mock"
    TWILIO_VERIFY_SERVICE_SID: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
