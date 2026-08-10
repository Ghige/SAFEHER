"""
Dead man's switch — escalates an alert if the app stops pinging.

The app calls POST /alerts/ping/{alert_id} every 60 seconds while an alert
is active. If pings stop for DEAD_SWITCH_TIMEOUT_SECONDS (default 3 min),
it likely means the phone was smashed, confiscated, or the user is incapacitated.

Ping state is stored in Redis (persistent across restarts, works with
multiple workers). Falls back to in-memory if Redis is unavailable.
"""

from sqlalchemy.orm import Session
from datetime import datetime
from app.models.alert import Alert
from app.models.user import User
from app.models.contact import EmergencyContact
from app.services.meta_whatsapp_service import send_whatsapp_alert
from app.services.firebase_service import set_alert_status
from app.services.fcm_service import notify_alert_escalated
from app.services import redis_service
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def record_ping(alert_id: str) -> None:
    """Record a heartbeat ping from the app."""
    redis_service.record_ping(alert_id)
    logger.debug(f"Ping recorded for alert {alert_id}")


def check_dead_switches(db: Session) -> None:
    """
    Called by a background scheduler every minute.
    If an active alert hasn't pinged in DEAD_SWITCH_TIMEOUT_SECONDS,
    escalate — the phone may be offline, smashed, or taken.
    """
    timeout = settings.DEAD_SWITCH_TIMEOUT_SECONDS
    now = datetime.utcnow()

    active_alerts = db.query(Alert).filter(Alert.status == "active").all()

    for alert in active_alerts:
        alert_id = str(alert.id)
        last_ping_ts = redis_service.get_last_ping(alert_id)

        if last_ping_ts is None:
            # No ping yet — baseline from alert start so dead switch uses real elapsed time
            import time
            baseline = alert.started_at.timestamp() if alert.started_at else time.time()
            redis_service.record_ping(alert_id, timestamp=baseline)
            continue

        from datetime import datetime as dt
        import time
        seconds_since = time.time() - last_ping_ts

        if seconds_since > timeout:
            logger.warning(
                f"Dead switch triggered for alert {alert_id} — "
                f"{seconds_since:.0f}s since last ping"
            )
            _escalate_alert(db, alert)


def _escalate_alert(db: Session, alert: Alert) -> None:
    """Escalate — send a second urgent WhatsApp to all contacts."""
    alert.status = "escalated"
    db.commit()

    set_alert_status(str(alert.id), "escalated")
    redis_service.delete_ping(str(alert.id))

    user = db.query(User).filter(User.id == alert.user_id).first()
    contacts = db.query(EmergencyContact).filter(
        EmergencyContact.user_id == alert.user_id,
        EmergencyContact.is_active == True
    ).all()

    from app.api.v1.location import create_track_token
    track_token = create_track_token(str(alert.id))

    for contact in contacts:
        send_whatsapp_alert(
            to_phone=contact.phone_number,
            user_name=user.name if user else "User",
            latitude=float(alert.latitude) if alert.latitude is not None else None,
            longitude=float(alert.longitude) if alert.longitude is not None else None,
            alert_id=str(alert.id),
            trigger_type="escalated",
            track_token=track_token,
        )

    if user and user.fcm_token:
        notify_alert_escalated(user.fcm_token, user.name)

    logger.info(f"Alert {alert.id} escalated — contacts re-notified")
