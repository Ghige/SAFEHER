from sqlalchemy.orm import Session
from uuid import UUID
import logging

from app.models.helper import Helper
from app.models.user import User
from app.models.alert import Alert
from app.models.blocklist import Blocklist
from app.services.location_service import haversine_distance
from app.services.firebase_service import push_helper_update
from app.services.alert_constants import ONGOING_ALERT_STATUSES
from app.config import settings

logger = logging.getLogger(__name__)

# In production this would use a spatial index (PostGIS)
# For V1 we load active users and filter by distance in Python
# Switch to PostGIS ST_DWithin query for V2


def find_and_notify_helpers(
    db: Session,
    alert_id: str,
    user_id: str,
    latitude: float,
    longitude: float
):
    """
    Find registered helpers within HELPER_SEARCH_RADIUS_METERS.
    Skips users on the blocked list.
    Notifies them via Firebase push notification.

    MVP: match helpers by the alert user's city (same city, case-insensitive).
    Skips helper notification when the alert user has no city set.
    GPS radius search requires stored helper locations (V2 / PostGIS).
    """
    alert_user = db.query(User).filter(User.id == user_id).first()
    if not alert_user or not alert_user.city:
        logger.info(
            f"Skipping helper notification for alert {alert_id} — "
            "alert user has no city set"
        )
        return

    alert_city = alert_user.city.strip().lower()

    blocked = db.query(Blocklist).filter(
        Blocklist.user_id == user_id
    ).all()
    blocked_phones = {b.blocked_phone for b in blocked}

    candidates = (
        db.query(User)
        .filter(
            User.id != user_id,
            User.city.isnot(None),
        )
        .all()
    )

    nearby = []
    for u in candidates:
        if u.phone_number in blocked_phones:
            continue
        if u.city and u.city.strip().lower() == alert_city:
            nearby.append(u)

    alert_uuid = UUID(alert_id) if isinstance(alert_id, str) else alert_id

    for helper_user in nearby[:5]:
        helper = Helper(
            alert_id=alert_uuid,
            helper_user_id=helper_user.id,
            status="notified",
            identity_revealed=False,
            approved_by_user=False
        )
        db.add(helper)
        db.commit()
        db.refresh(helper)

        push_helper_update(alert_id, str(helper.id), "notified")
        logger.info(
            f"Helper {helper_user.id} notified for alert {alert_id} "
            f"(city match: {alert_user.city})"
        )


def approve_helper(db: Session, helper_id: UUID, alert_user_id: UUID) -> Helper:
    """User approves a helper — reveals helper's identity to them."""
    helper = db.query(Helper).filter(Helper.id == helper_id).first()
    if not helper:
        raise ValueError("Helper not found")

    # Verify this alert belongs to the requesting user and is still ongoing
    alert = db.query(Alert).filter(
        Alert.id == helper.alert_id,
        Alert.user_id == alert_user_id
    ).first()
    if not alert:
        raise ValueError("Unauthorized")
    if alert.status not in ONGOING_ALERT_STATUSES:
        raise ValueError("Active alert not found")

    helper.identity_revealed = True
    helper.approved_by_user  = True
    db.commit()
    db.refresh(helper)

    push_helper_update(str(helper.alert_id), str(helper_id), "approved")
    return helper


def helper_respond(db: Session, alert_id: UUID, helper_user_id: UUID) -> Helper:
    """Helper says they are coming."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert or alert.status not in ONGOING_ALERT_STATUSES:
        raise ValueError("Alert not found")
    if alert.user_id == helper_user_id:
        raise ValueError("Unauthorized")

    helper = db.query(Helper).filter(
        Helper.alert_id == alert_id,
        Helper.helper_user_id == helper_user_id,
        Helper.status == "notified",
    ).first()
    if not helper:
        raise ValueError("Not found")

    helper.status = "responding"
    db.commit()
    db.refresh(helper)

    push_helper_update(str(alert_id), str(helper.id), "responding")
    return helper


def block_helper(db: Session, helper_id: UUID, alert_user_id: UUID):
    """Block a specific helper from this and future alerts."""
    helper = db.query(Helper).filter(Helper.id == helper_id).first()
    if not helper:
        raise ValueError("Helper not found")

    alert = db.query(Alert).filter(
        Alert.id == helper.alert_id,
        Alert.user_id == alert_user_id,
    ).first()
    if not alert:
        raise ValueError("Unauthorized")

    helper.status = "cancelled"
    db.commit()

    push_helper_update(str(helper.alert_id), str(helper_id), "cancelled")
