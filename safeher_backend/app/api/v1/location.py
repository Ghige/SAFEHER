"""
Location routes.

POST /location/update  — authenticated, updates live GPS coords for an active alert.
GET  /location/live/{alert_id}?token={signed_token} — semi-public, for contacts.

The live endpoint uses a short-lived signed token instead of exposing the
raw alert UUID. Emergency contacts receive the signed URL in their WhatsApp
message. The token encodes the alert_id and expires after 24 hours.
This prevents anyone who guesses or stumbles upon a UUID from tracking a user.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from uuid import UUID
from jose import jwt, JWTError
from datetime import datetime, timedelta

from app.db.session import get_db
from app.api.deps import get_current_user, get_verified_user
from app.models.user import User
from app.models.alert import Alert
from app.schemas.alert_schema import LocationUpdate
from app.services.location_service import update_live_location
from app.services.alert_constants import ONGOING_ALERT_STATUSES
from app.services.redis_service import check_rate_limit
from app.config import settings

router = APIRouter(prefix="/location", tags=["Location"])

TRACK_TOKEN_EXPIRY_HOURS = 24
TRACK_TOKEN_PURPOSE = "live_track"


# ── Token helpers ─────────────────────────────────────────────────────────────

def create_track_token(alert_id: str) -> str:
    """
    Create a signed, expiring token for sharing live location with contacts.
    Encodes alert_id + purpose + expiry. Uses the same SECRET_KEY as JWT.
    """
    expire = datetime.utcnow() + timedelta(hours=TRACK_TOKEN_EXPIRY_HOURS)
    return jwt.encode(
        {"alert_id": alert_id, "purpose": TRACK_TOKEN_PURPOSE, "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


def decode_track_token(token: str) -> str:
    """Decode and validate a track token. Returns alert_id or raises 403."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("purpose") != TRACK_TOKEN_PURPOSE:
            raise HTTPException(status_code=403, detail="Invalid tracking token")
        return payload["alert_id"]
    except JWTError:
        raise HTTPException(status_code=403, detail="Tracking link has expired or is invalid")


# ── Routes ────────────────────────────────────────────────────────────────────

def _rate_limit_location(request, user_id: str) -> None:
    allowed = check_rate_limit(
        identifier=f"location:{user_id}",
        limit=settings.RATE_LIMIT_ALERT_PER_MINUTE,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many location updates.")


@router.post("/update")
def update_location(
    payload: LocationUpdate,
    request: Request,
    current_user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """Send current GPS coordinates during an active alert."""
    _rate_limit_location(request, str(current_user.id))
    success = update_live_location(
        db=db,
        alert_id=payload.alert_id,
        user_id=current_user.id,
        latitude=payload.latitude,
        longitude=payload.longitude
    )
    if not success:
        raise HTTPException(status_code=404, detail="No active alert found")
    return {"status": "location updated"}


@router.get("/track-link/{alert_id}")
def get_track_link(
    alert_id: UUID,
    current_user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """
    Generate a signed tracking URL for an active alert.
    Called by the app when generating the WhatsApp message link.
    Only the alert owner can generate a tracking link.
    """
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.user_id == current_user.id,
        Alert.status.in_(ONGOING_ALERT_STATUSES),
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="No active alert found")

    token = create_track_token(str(alert_id))
    return {
        "track_url": f"https://safeher.app/track?token={token}",
        "expires_in_hours": TRACK_TOKEN_EXPIRY_HOURS
    }


@router.get("/live")
def live_location(
    token: str = Query(..., description="Signed tracking token from WhatsApp link"),
    db: Session = Depends(get_db)
):
    """
    Get live location for an alert via signed token.

    This endpoint is for emergency contacts — they open a link in their browser,
    no login required. The signed token prevents unauthorised access.
    Token is included in the WhatsApp message sent to contacts.
    """
    alert_id = decode_track_token(token)

    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    show_coords = alert.status in ONGOING_ALERT_STATUSES
    lat = float(alert.latitude) if show_coords and alert.latitude else None
    lng = float(alert.longitude) if show_coords and alert.longitude else None

    return {
        "alert_id":   str(alert.id),
        "latitude":   lat,
        "longitude":  lng,
        "status":     alert.status,
        "started_at": str(alert.started_at),
        "maps_embed": (
            f"https://maps.google.com/maps?q={lat},{lng}&output=embed"
            if lat is not None and lng is not None else None
        )
    }
