from sqlalchemy.orm import Session
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
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(
            "trigger_alert rejected: user_id=%s reason=user_not_found trigger_type=%s",
            user_id,
            trigger_type,
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
    db.commit()
    db.refresh(alert)

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

    # Push to Firebase for live tracking
    if latitude and longitude:
        push_location_update(
            alert_id=str(alert.id),
            latitude=latitude,
            longitude=longitude,
            user_name=user.name
        )

    # Find and notify nearby helpers
    if latitude and longitude:
        find_and_notify_helpers(
            db=db,
            alert_id=str(alert.id),
            user_id=str(user_id),
            latitude=latitude,
            longitude=longitude
        )

    logger.info(
        f"Alert {alert.id} triggered for user {user_id} via {trigger_type} "
        f"(whatsapp sent={sent_count}, failed={failed_count})"
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
    for contact in contacts:
        send_cancellation_message(contact.phone_number, user_name)

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
