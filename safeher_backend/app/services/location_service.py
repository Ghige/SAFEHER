from sqlalchemy.orm import Session
from uuid import UUID
from math import radians, sin, cos, sqrt, atan2
from app.services.firebase_service import push_location_update
from app.services.alert_constants import ONGOING_ALERT_STATUSES
from app.models.alert import Alert
from app.models.user import User
import logging

logger = logging.getLogger(__name__)


def update_live_location(
    db: Session,
    alert_id: UUID,
    user_id: UUID,
    latitude: float,
    longitude: float
) -> bool:
    """
    Update user's live location during an active alert.
    Pushes to Firebase so contacts see it in real time.
    """
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.user_id == user_id,
        Alert.status.in_(ONGOING_ALERT_STATUSES),
    ).first()

    if not alert:
        return False

    # Update DB with latest coords
    alert.latitude  = latitude
    alert.longitude = longitude
    db.commit()

    # Push to Firebase for real-time tracking
    user = db.query(User).filter(User.id == user_id).first()
    push_location_update(
        alert_id=str(alert_id),
        latitude=latitude,
        longitude=longitude,
        user_name=user.name if user else "User"
    )
    return True


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance in meters between two GPS coordinates.
    Used to find nearby helpers within radius.
    """
    R = 6371000  # Earth radius in metres

    phi1, phi2 = radians(lat1), radians(lat2)
    dphi       = radians(lat2 - lat1)
    dlambda    = radians(lon2 - lon1)

    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c
