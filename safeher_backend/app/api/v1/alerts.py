import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from uuid import UUID

from app.db.session import get_db
from app.api.deps import get_current_user, get_verified_user
from app.models.user import User
from app.schemas.alert_schema import AlertTrigger, AlertResponse, AlertTriggerResponse
from app.services.alert_service import (
    trigger_alert, cancel_alert,
    get_active_alert, get_alert_history
)
from app.services.dead_switch import record_ping
from app.services.redis_service import check_rate_limit
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["Alerts"])

_TRIGGER_PATH = "/api/v1/alerts/trigger"


def _rate_limit_alert(request: Request, user_id: str) -> None:
    """Rate limit alert triggers per user to prevent abuse."""
    allowed = check_rate_limit(
        identifier=f"alert:{user_id}",
        limit=settings.RATE_LIMIT_ALERT_PER_MINUTE,
        window_seconds=60
    )
    if not allowed:
        detail = "Too many requests."
        logger.warning(
            "POST %s rate limited user_id=%s detail=%r",
            _TRIGGER_PATH,
            user_id,
            detail,
        )
        raise HTTPException(status_code=429, detail=detail)


@router.post("/trigger", response_model=AlertTriggerResponse, status_code=201)
def trigger(
    payload: AlertTrigger,
    request: Request,
    current_user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """Fire an alert — sends WhatsApp to contacts + notifies helpers."""
    logger.info(
        "POST %s user_id=%s trigger_type=%s latitude=%s longitude=%s",
        _TRIGGER_PATH,
        current_user.id,
        payload.trigger_type,
        payload.latitude,
        payload.longitude,
    )
    _rate_limit_alert(request, str(current_user.id))
    try:
        alert, notification_status = trigger_alert(
            db=db,
            user_id=current_user.id,
            trigger_type=payload.trigger_type,
            latitude=payload.latitude,
            longitude=payload.longitude
        )
        return AlertTriggerResponse.model_validate(
            {**AlertResponse.model_validate(alert).model_dump(), **notification_status}
        )
    except ValueError as e:
        detail = str(e)
        logger.warning(
            "POST %s rejected user_id=%s detail=%r",
            _TRIGGER_PATH,
            current_user.id,
            detail,
            exc_info=True,
        )
        logger.warning(
            "POST %s returning HTTP 400 detail=%r",
            _TRIGGER_PATH,
            detail,
        )
        raise HTTPException(status_code=400, detail=detail) from e
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "POST %s unexpected error user_id=%s trigger_type=%s",
            _TRIGGER_PATH,
            current_user.id,
            payload.trigger_type,
        )
        raise


@router.post("/cancel/{alert_id}", response_model=AlertResponse)
def cancel(
    alert_id: UUID,
    current_user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """Cancel active alert — false alarm. Notifies contacts it's safe."""
    try:
        return cancel_alert(db, alert_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/ping/{alert_id}")
def ping(
    alert_id: UUID,
    current_user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """
    Dead man's switch heartbeat — app sends this every 60 seconds.
    If pings stop, backend escalates the alert automatically.
    """
    active = get_active_alert(db, current_user.id)
    if not active or active.id != alert_id:
        raise HTTPException(status_code=404, detail="No active alert found")

    record_ping(str(alert_id))
    return {"status": "ok", "alert_id": str(alert_id)}


@router.get("/history", response_model=list[AlertResponse])
def history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_alert_history(db, current_user.id)


@router.get("/active", response_model=AlertResponse)
def active_alert(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    alert = get_active_alert(db, current_user.id)
    if not alert:
        raise HTTPException(status_code=404, detail="No active alert")
    return alert
