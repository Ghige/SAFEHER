from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from uuid import UUID
from datetime import datetime
import logging

from app.models.alert import Alert
from app.models.user import User
from app.models.contact import EmergencyContact
from app.services.meta_whatsapp_service import send_whatsapp_alert, send_cancellation_message
from app.services.firebase_service import push_location_update, set_alert_status
from app.services.alert_constants import ONGOING_ALERT_STATUSES
from app.services.helper_service import find_and_notify_helpers
from app.services.redis_service import delete_ping
from app.services.audit_log import write_audit_event
from app.observability import metrics

logger = logging.getLogger(__name__)


def trigger_alert(
    db: Session,
    user_id: UUID,
    trigger_type: str,
    latitude: float = None,
    longitude: float = None
) -> tuple[Alert, dict]:
    """
    Core alert trigger function.
    1. Creates alert record in DB
    2. Sends WhatsApp to all active emergency contacts
    3. Pushes location to Firebase for live tracking
    4. Notifies nearby helpers
    """
    # Serialize concurrent triggers for the same user (race-safe with unique index).
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .with_for_update()
        .first()
    )
    if not user:
        logger.warning(
            "trigger_alert rejected: user_id=%s reason=user_not_found trigger_type=%s",
            user_id,
            trigger_type,
        )
        metrics.incr("sos_trigger_rejected_total")
        write_audit_event(
            "sos_lifecycle",
            actor_id=str(user_id),
            detail={"phase": "rejected", "reason": "user_not_found", "trigger_type": trigger_type},
        )
        raise ValueError("User not found")

    existing = get_active_alert(db, user_id)
    if existing:
        logger.warning(
            "trigger_alert rejected: user_id=%s reason=active_alert_exists "
            "existing_alert_id=%s existing_status=%s trigger_type=%s",
            user_id,
            existing.id,
            existing.status,
            trigger_type,
        )
        metrics.incr("sos_trigger_rejected_total")
        write_audit_event(
            "sos_lifecycle",
            actor_id=str(user_id),
            detail={
                "phase": "rejected",
                "reason": "active_alert_exists",
                "trigger_type": trigger_type,
                "existing_alert_id": str(existing.id),
            },
        )
        raise ValueError("An active alert already exists")

    contact_count = (
        db.query(EmergencyContact)
        .filter(
            EmergencyContact.user_id == user_id,
            EmergencyContact.is_active == True,
        )
        .count()
    )
    if contact_count == 0:
        logger.warning(
            "trigger_alert rejected: user_id=%s reason=no_emergency_contacts trigger_type=%s",
            user_id,
            trigger_type,
        )
        metrics.incr("sos_trigger_rejected_total")
        write_audit_event(
            "sos_lifecycle",
            actor_id=str(user_id),
            detail={
                "phase": "rejected",
                "reason": "no_emergency_contacts",
                "trigger_type": trigger_type,
            },
        )
        raise ValueError("Add at least one emergency contact before triggering SOS")

    # Create alert record
    alert = Alert(
        user_id=user_id,
        trigger_type=trigger_type,
        latitude=latitude,
        longitude=longitude,
        status="active"
    )
    db.add(alert)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning(
            "trigger_alert integrity conflict user_id=%s trigger_type=%s err=%s",
            user_id,
            trigger_type,
            exc.orig if hasattr(exc, "orig") else exc,
        )
        raise ValueError("An active alert already exists") from exc
    db.refresh(alert)

    write_audit_event(
        "sos_lifecycle",
        actor_id=str(user_id),
        detail={
            "phase": "created",
            "alert_id": str(alert.id),
            "trigger_type": trigger_type,
            "has_coords": latitude is not None and longitude is not None,
            "contact_count": contact_count,
        },
    )
    metrics.incr("sos_trigger_created_total")

    # Generate signed tracking token for WhatsApp links
    from app.api.v1.location import create_track_token
    track_token = create_track_token(str(alert.id))

    # Get active contacts sorted by priority
    contacts = (
        db.query(EmergencyContact)
        .filter(
            EmergencyContact.user_id == user_id,
            EmergencyContact.is_active == True
        )
        .order_by(EmergencyContact.ring_priority)
        .all()
    )

    # Send WhatsApp to all contacts
    sent_count = 0
    failed_count = 0
    for contact in contacts:
        if send_whatsapp_alert(
            to_phone=contact.phone_number,
            user_name=user.name,
            latitude=latitude,
            longitude=longitude,
            alert_id=str(alert.id),
            trigger_type=trigger_type,
            track_token=track_token,
        ):
            sent_count += 1
        else:
            failed_count += 1

    notification_status = {
        "whatsapp_sent_count": sent_count,
        "whatsapp_failed_count": failed_count,
        "whatsapp_all_delivered": failed_count == 0 and sent_count > 0,
    }

    write_audit_event(
        "sos_delivery_status",
        actor_id=str(user_id),
        detail={
            "alert_id": str(alert.id),
            "trigger_type": trigger_type,
            "whatsapp_sent_count": sent_count,
            "whatsapp_failed_count": failed_count,
            "whatsapp_all_delivered": notification_status["whatsapp_all_delivered"],
        },
    )
    metrics.incr("sos_whatsapp_sent_total", sent_count)
    metrics.incr("sos_whatsapp_failed_total", failed_count)

    # Push to Firebase for live tracking (explicit None checks — 0.0 is valid)
    if latitude is not None and longitude is not None:
        push_location_update(
            alert_id=str(alert.id),
            latitude=latitude,
            longitude=longitude,
            user_name=user.name
        )

    # Find and notify nearby helpers
    if latitude is not None and longitude is not None:
        find_and_notify_helpers(
            db=db,
            alert_id=str(alert.id),
            user_id=str(user_id),
            latitude=latitude,
            longitude=longitude
        )

    logger.info(
        "Alert %s triggered for user %s via %s (whatsapp sent=%s, failed=%s)",
        alert.id,
        user_id,
        trigger_type,
        sent_count,
        failed_count,
    )
    return alert, notification_status


def cancel_alert(db: Session, alert_id: UUID, user_id: UUID) -> Alert:
    """Cancel an active alert — false alarm."""
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.user_id == user_id,
        Alert.status.in_(ONGOING_ALERT_STATUSES),
    ).first()

    if not alert:
        raise ValueError("Active alert not found")

    alert.status = "cancelled"
    alert.ended_at = datetime.utcnow()
    db.commit()
    db.refresh(alert)

    set_alert_status(str(alert_id), "cancelled")
    delete_ping(str(alert_id))

    user = db.query(User).filter(User.id == user_id).first()
    contacts = db.query(EmergencyContact).filter(
        EmergencyContact.user_id == user_id,
        EmergencyContact.is_active == True
    ).all()
    user_name = user.name if user else "User"
    cancel_sent = 0
    cancel_failed = 0
    for contact in contacts:
        if send_cancellation_message(contact.phone_number, user_name):
            cancel_sent += 1
        else:
            cancel_failed += 1

    write_audit_event(
        "sos_lifecycle",
        actor_id=str(user_id),
        detail={
            "phase": "cancelled",
            "alert_id": str(alert_id),
            "cancel_whatsapp_sent": cancel_sent,
            "cancel_whatsapp_failed": cancel_failed,
        },
    )
    metrics.incr("sos_cancelled_total")

    return alert


def get_active_alert(db: Session, user_id: UUID) -> Alert:
    """Return the user's current in-progress alert (active or escalated)."""
    return db.query(Alert).filter(
        Alert.user_id == user_id,
        Alert.status.in_(ONGOING_ALERT_STATUSES),
    ).first()


def get_alert_history(db: Session, user_id: UUID) -> list:
    """Get past alerts for the user."""
    return (
        db.query(Alert)
        .filter(Alert.user_id == user_id)
        .order_by(Alert.started_at.desc())
        .limit(50)
        .all()
    )


def update_alert_evidence(db: Session, alert_id: UUID, drive_url: str):
    """Attach Google Drive evidence link to alert record."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert:
        alert.evidence_url = drive_url
        db.commit()
