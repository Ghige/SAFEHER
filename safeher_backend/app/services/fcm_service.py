"""
Firebase Cloud Messaging — push notifications to the SafeHer Android app.

Requires firebase-credentials.json and FCM enabled in Firebase Console.
"""

import logging

from app.services.firebase_service import ensure_firebase_initialized

logger = logging.getLogger(__name__)


def send_push(token: str, title: str, body: str, data: dict | None = None) -> bool:
    """Send a push notification to a single device token."""
    if not token:
        return False
    if not ensure_firebase_initialized():
        logger.warning("FCM skipped — Firebase not configured")
        return False
    try:
        from firebase_admin import messaging

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            token=token,
        )
        messaging.send(message)
        logger.info("FCM push sent")
        return True
    except Exception as e:
        logger.error(f"FCM push failed: {e}")
        return False


def notify_alert_escalated(fcm_token: str | None, user_name: str) -> bool:
    if not fcm_token:
        return False
    return send_push(
        token=fcm_token,
        title="SafeHer — Alert Escalated",
        body=f"Your alert may need attention. Your phone stopped responding.",
        data={"type": "alert_escalated"},
    )
