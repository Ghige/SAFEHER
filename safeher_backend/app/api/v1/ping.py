from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.db.session import SessionLocal
from app.observability import metrics
from app.services import redis_service

router = APIRouter(prefix="/ping", tags=["Health"])


@router.get("/")
def ping():
    """Liveness — process is up."""
    return {
        "status": "ok",
        "service": "safeher-backend",
        "ai_auto_sos_enabled": bool(settings.AI_AUTO_SOS_ENABLED),
    }


@router.get("/ready")
def ready():
    """
    Readiness — DB required; Redis reported.
    Returns HTTP 503 when database is down (orchestrators can restart/drain).
    Does not probe Meta/Twilio (external; would create false negatives).
    """
    checks: dict = {
        "database": "unknown",
        "redis": "unknown",
        "meta_configured": bool(
            (settings.META_ACCESS_TOKEN or "").strip()
            and (settings.META_PHONE_NUMBER_ID or "").strip()
        ),
        "ai_auto_sos_enabled": bool(settings.AI_AUTO_SOS_ENABLED),
    }

    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            checks["database"] = "ok"
        finally:
            db.close()
    except Exception:
        checks["database"] = "error"

    client = redis_service._get_client()
    if client is None:
        checks["redis"] = "unavailable_memory_fallback"
    else:
        try:
            client.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"

    if checks["database"] != "ok":
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "checks": checks},
        )

    overall = "ok" if checks["redis"] == "ok" else "degraded"
    return {"status": overall, "checks": checks}


@router.get("/metrics")
def ops_metrics():
    """
    Stage 11 in-process metrics snapshot (JSON).
    Not Prometheus exposition format — suitable for ops dashboards/scripts.
    """
    if not getattr(settings, "METRICS_ENABLED", True):
        return Response(status_code=404, content="metrics disabled")
    snap = metrics.snapshot()
    snap["ai_auto_sos_enabled"] = bool(settings.AI_AUTO_SOS_ENABLED)
    snap["environment"] = settings.ENVIRONMENT
    return snap
