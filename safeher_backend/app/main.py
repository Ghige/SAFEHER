import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import auth, users, alerts, helpers, location, ping, ai
from app.config import settings
from app.services.scheduler import run_dead_switch_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_task = asyncio.create_task(run_dead_switch_scheduler())
    yield
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="SafeHer API",
    description="🛡️ Women's safety backend — alerts, live location, helpers, dead man's switch",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


def _is_alert_trigger_request(request: Request) -> bool:
    return (
        request.method == "POST"
        and request.url.path.rstrip("/").endswith("/alerts/trigger")
    )


@app.exception_handler(RequestValidationError)
async def alert_trigger_validation_handler(
    request: Request,
    exc: RequestValidationError,
):
    if _is_alert_trigger_request(request):
        logger.warning(
            "POST /api/v1/alerts/trigger validation failed: errors=%s body=%r",
            exc.errors(),
            exc.body,
        )
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(HTTPException)
async def alert_trigger_http_exception_handler(
    request: Request,
    exc: HTTPException,
):
    if _is_alert_trigger_request(request):
        logger.warning(
            "POST /api/v1/alerts/trigger HTTP %s detail=%r",
            exc.status_code,
            exc.detail,
        )
    return await http_exception_handler(request, exc)


# CORS — restrict to your domain in production
_origins = (
    ["*"]
    if settings.ENVIRONMENT == "development"
    else ["https://safeher.app", "https://api.safeher.app"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(auth.router,     prefix="/api/v1")
app.include_router(users.router,    prefix="/api/v1")
app.include_router(alerts.router,   prefix="/api/v1")
app.include_router(helpers.router,  prefix="/api/v1")
app.include_router(location.router, prefix="/api/v1")
app.include_router(ping.router,     prefix="/api/v1")
app.include_router(ai.router,       prefix="/api/v1")

# Static track page for local/dev — production: deploy safeher_web/track to safeher.app
_track_dir = Path(__file__).resolve().parent.parent.parent / "safeher_web" / "track"
if _track_dir.is_dir():
    app.mount("/track", StaticFiles(directory=str(_track_dir), html=True), name="track")


@app.get("/")
def root():
    return {
        "app":     "SafeHer",
        "version": "1.0.0",
        "status":  "running 🛡️",
        "docs":    "/docs"
    }
