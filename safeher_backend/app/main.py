import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import auth, users, alerts, helpers, location, ping, ai
from app.config import settings
from app.observability import configure_logging
from app.observability.middleware import RequestObservabilityMiddleware
from app.security.production_guards import is_production_like, validate_runtime_config
from app.services.audit_log import write_audit_event, purge_old_audit_files
from app.services.scheduler import run_dead_switch_scheduler

_PROD_EARLY = is_production_like(settings)
configure_logging(
    debug=settings.DEBUG,
    json_logs=bool(getattr(settings, "LOG_JSON", False)) or _PROD_EARLY,
)
logger = logging.getLogger(__name__)

# Fail closed on unsafe production config before serving traffic.
validate_runtime_config(settings)

_PROD = is_production_like(settings)
_docs_url = None if _PROD else "/docs"
_redoc_url = None if _PROD else "/redoc"


@asynccontextmanager
async def lifespan(app: FastAPI):
    purged = purge_old_audit_files()
    write_audit_event(
        "app_startup",
        detail={
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "ai_auto_sos_enabled": settings.AI_AUTO_SOS_ENABLED,
            "otp_provider": settings.OTP_PROVIDER,
            "docs_enabled": _docs_url is not None,
            "log_json": bool(getattr(settings, "LOG_JSON", False)) or _PROD,
            "audit_files_purged": purged,
        },
    )
    scheduler_task = asyncio.create_task(run_dead_switch_scheduler())
    yield
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    write_audit_event("app_shutdown", detail={"environment": settings.ENVIRONMENT})


app = FastAPI(
    title="SafeHer API",
    description="Women's safety backend — alerts, live location, helpers, dead man's switch",
    version="1.0.0",
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=None if _PROD else "/openapi.json",
    lifespan=lifespan,
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach X-Request-ID for correlating client and server logs."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Baseline browser/API hardening headers (Stage 9)."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )
        if _PROD:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        response.headers.setdefault(
            "X-SafeHer-AI-Auto-SOS",
            "enabled" if settings.AI_AUTO_SOS_ENABLED else "disabled",
        )
        return response


def _is_alert_trigger_request(request: Request) -> bool:
    return (
        request.method == "POST"
        and request.url.path.rstrip("/").endswith("/alerts/trigger")
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    request_id = getattr(request.state, "request_id", None)
    if _is_alert_trigger_request(request):
        logger.warning(
            "POST /api/v1/alerts/trigger validation failed request_id=%s errors=%s",
            request_id,
            exc.errors(),
        )
    else:
        logger.info(
            "Validation failed %s %s request_id=%s errors=%s",
            request.method,
            request.url.path,
            request_id,
            exc.errors(),
        )
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(HTTPException)
async def http_exception_logging_handler(
    request: Request,
    exc: HTTPException,
):
    request_id = getattr(request.state, "request_id", None)
    if _is_alert_trigger_request(request) or exc.status_code >= 500:
        logger.warning(
            "%s %s HTTP %s request_id=%s detail=%r",
            request.method,
            request.url.path,
            exc.status_code,
            request_id,
            exc.detail,
        )
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "Unhandled error %s %s request_id=%s",
        request.method,
        request.url.path,
        request_id,
    )
    write_audit_event(
        "unhandled_exception",
        request_id=request_id,
        detail={"path": request.url.path, "method": request.method},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
        headers={"X-Request-ID": request_id or ""},
    )


def _cors_origins() -> list[str]:
    if settings.ENVIRONMENT == "development" and not _PROD:
        return ["*"]
    origins = [
        "https://safeher.app",
        "https://api.safeher.app",
        "https://www.safeher.app",
    ]
    extra = [o.strip() for o in (settings.CORS_ALLOWED_ORIGINS or "").split(",") if o.strip()]
    return list(dict.fromkeys(origins + extra))


# Middleware order: last added = outermost
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestObservabilityMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Accept"],
)
if _PROD and (settings.TRUSTED_HOSTS or "").strip():
    hosts = [h.strip() for h in settings.TRUSTED_HOSTS.split(",") if h.strip()]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(helpers.router, prefix="/api/v1")
app.include_router(location.router, prefix="/api/v1")
app.include_router(ping.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")

_track_dir = Path(__file__).resolve().parent.parent.parent / "safeher_web" / "track"
if _track_dir.is_dir():
    app.mount("/track", StaticFiles(directory=str(_track_dir), html=True), name="track")


@app.get("/")
def root():
    return {
        "app": "SafeHer",
        "version": "1.0.0",
        "status": "running",
        "environment": settings.ENVIRONMENT,
        "ai_auto_sos_enabled": bool(settings.AI_AUTO_SOS_ENABLED),
        "docs": _docs_url,
    }
