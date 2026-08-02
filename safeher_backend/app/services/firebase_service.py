import firebase_admin
from firebase_admin import credentials, db
from app.config import settings
import logging

logger = logging.getLogger(__name__)

_initialized = False


def _init_firebase():
    global _initialized
    if not _initialized:
        try:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred, {
                "databaseURL": settings.FIREBASE_DATABASE_URL
            })
            _initialized = True
        except Exception as e:
            logger.error(f"Firebase init failed: {e}")


def push_location_update(alert_id: str, latitude: float, longitude: float, user_name: str):
    """
    Push live location to Firebase Realtime DB.
    Contacts watching the live link will see this update instantly.
    """
    _init_firebase()
    try:
        ref = db.reference(f"alerts/{alert_id}/location")
        ref.set({
            "latitude":  latitude,
            "longitude": longitude,
            "user_name": user_name,
            "timestamp": {".sv": "timestamp"}   # Firebase server timestamp
        })
        logger.info(f"Location pushed for alert {alert_id}")
        return True
    except Exception as e:
        logger.error(f"Firebase location push failed: {e}")
        return False


def set_alert_status(alert_id: str, status: str):
    """Update alert status in Firebase so live trackers know it's resolved."""
    _init_firebase()
    try:
        ref = db.reference(f"alerts/{alert_id}/status")
        ref.set(status)
        return True
    except Exception as e:
        logger.error(f"Firebase status update failed: {e}")
        return False


def push_helper_update(alert_id: str, helper_id: str, status: str):
    """Notify the user's app that a helper is responding."""
    _init_firebase()
    try:
        ref = db.reference(f"alerts/{alert_id}/helpers/{helper_id}")
        ref.update({"status": status, "updated_at": {".sv": "timestamp"}})
        return True
    except Exception as e:
        logger.error(f"Firebase helper update failed: {e}")
        return False
