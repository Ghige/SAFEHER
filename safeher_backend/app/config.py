from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/safeher_db"

    # JWT
    SECRET_KEY: str = "change-this-to-a-random-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h dev; production should use ≤120

    # Meta WhatsApp Cloud API (emergency contact messages)
    META_ACCESS_TOKEN: str = ""
    META_PHONE_NUMBER_ID: str = ""
    META_WABA_ID: str = ""
    # Dev default: hello_world (Meta sample template). Override for production templates.
    META_WHATSAPP_TEMPLATE_ALERT: str = ""
    META_WHATSAPP_TEMPLATE_CANCEL: str = ""
    META_WHATSAPP_TEMPLATE_LANGUAGE: str = ""

    # Firebase
    FIREBASE_CREDENTIALS_PATH: str = "./firebase-credentials.json"
    FIREBASE_DATABASE_URL: str = ""

    # Google APIs
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    # Stage 9: production/staging must have Redis (no silent in-memory RL fallback)
    REQUIRE_REDIS_IN_PRODUCTION: bool = True

    # App
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    # Comma-separated extra CORS origins (production always includes safeher.app hosts)
    CORS_ALLOWED_ORIGINS: str = ""
    # Trusted hosts for production (comma-separated); empty = middleware off (dev)
    TRUSTED_HOSTS: str = "safeher.app,api.safeher.app,localhost,127.0.0.1"

    # Alert settings
    DEAD_SWITCH_INTERVAL_SECONDS: int = 60
    DEAD_SWITCH_TIMEOUT_SECONDS: int = 180
    HELPER_SEARCH_RADIUS_METERS: int = 500
    CONFIRMATION_WINDOW_SECONDS: int = 30

    # Country code for WhatsApp (e.g. "91" for India, "1" for US)
    PHONE_COUNTRY_CODE: str = "91"

    # Public URLs (no trailing slash)
    TRACK_BASE_URL: str = "https://safeher.app/track"
    API_BASE_URL: str = "https://api.safeher.app"

    # Rate limiting (requests per period)
    RATE_LIMIT_AUTH_PER_MINUTE: int = 5
    RATE_LIMIT_ALERT_PER_MINUTE: int = 10
    RATE_LIMIT_OTP_PER_PHONE_PER_MINUTE: int = 3
    RATE_LIMIT_LOCATION_PER_MINUTE: int = 30
    RATE_LIMIT_DATASET_PER_MINUTE: int = 10
    RATE_LIMIT_CONFIDENCE_PER_MINUTE: int = 60

    # Drive token encryption key (Fernet) — generate with: Fernet.generate_key()
    DRIVE_TOKEN_ENCRYPTION_KEY: str = ""

    # OTP settings
    OTP_EXPIRY_MINUTES: int = 10
    # OTP provider: "mock" (dev only) | "twilio" (Twilio Verify SMS)
    # production/staging boot refuses mock; twilio requires TWILIO_* below
    OTP_PROVIDER: str = "mock"
    OTP_MAX_VERIFY_ATTEMPTS: int = 5
    # Dev-only shortcut code; ignored when ENVIRONMENT is production/staging
    OTP_ALLOW_DEV_SHORTCUT: bool = True
    # Twilio Verify (when OTP_PROVIDER=twilio)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_VERIFY_SERVICE_SID: str = ""

    # Stage 0/9 safety: AI must NEVER auto-fire WhatsApp/SOS while this is false.
    # Manual SOS (/alerts/trigger) is unaffected. Stage 9 keeps this false.
    AI_AUTO_SOS_ENABLED: bool = False

    # Privacy / dataset retention (Stage 9/11)
    AI_DATASET_MAX_UPLOAD_BYTES: int = 2_000_000  # ~2 MB WAV (legacy queue; new uploads rejected)
    AI_DATASET_RETENTION_DAYS: int = 30
    AI_FEEDBACK_UNREVIEWED_RETENTION_DAYS: int = 365
    AI_FEEDBACK_CONSENT_VERSION: str = "privacy-v2-metadata-only"
    AUDIT_LOG_DIR: str = ""  # default: safeher_backend/data/audit_logs
    AUDIT_RETENTION_DAYS: int = 30
    # Stage 11 observability
    LOG_JSON: bool = False  # true in production for structured stdout
    METRICS_ENABLED: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
