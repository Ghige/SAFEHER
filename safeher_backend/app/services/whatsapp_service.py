"""
WhatsApp alert service via Twilio.

Emergency contacts receive a WhatsApp message with:
  - What happened (trigger type)
  - Google Maps link to last known location
  - Signed live tracking link (no app install needed)

Phone numbers are normalised using PHONE_COUNTRY_CODE from config,
so the app works in any country — not hardcoded to +91.
"""

from twilio.rest import Client
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def _to_whatsapp_number(phone_number: str) -> str:
    """
    Normalise a stored phone number to Twilio's whatsapp:+E.164 format.
    Uses PHONE_COUNTRY_CODE from config (default "91" for India).
    """
    phone = phone_number.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        return f"whatsapp:{phone}"
    phone = phone.lstrip("0")
    cc = settings.PHONE_COUNTRY_CODE
    if phone.startswith(cc) and len(phone) > len(cc):
        phone = phone[len(cc):]
    return f"whatsapp:+{cc}{phone}"


def send_whatsapp_alert(
    to_phone: str,
    user_name: str,
    latitude: float,
    longitude: float,
    alert_id: str,
    trigger_type: str = "manual",
    track_token: str = None,
) -> bool:
    """
    Send WhatsApp alert to an emergency contact via Twilio.
    Contact does NOT need any app installed.

    track_token: signed JWT for the live tracking link. If not provided,
                 a raw alert link is used (less secure but functional).
    """
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        maps_link = f"https://maps.google.com/?q={latitude},{longitude}"
        if track_token:
            live_link = f"https://safeher.app/track?token={track_token}"
        else:
            live_link = f"https://safeher.app/track/{alert_id}"

        trigger_labels = {
            "manual":      "pressed the SOS button",
            "voice":       "triggered a voice SOS",
            "ai_audio":    "AI detected a distress sound",
            "ai_movement": "AI detected panic movement",
            "shake":       "shook their phone for SOS",
            "escalated":   "may be in danger — their phone stopped responding",
        }
        trigger_text = trigger_labels.get(trigger_type, "triggered an alert")

        message = (
            f"🚨 *SAFEHER ALERT* 🚨\n\n"
            f"*{user_name}* {trigger_text} and needs help.\n\n"
            f"📍 *Last known location:*\n{maps_link}\n\n"
            f"🔴 *Track live location:*\n{live_link}\n\n"
            f"Please call them or go to their location immediately.\n\n"
            f"_This alert was sent automatically by SafeHer._"
        )

        client.messages.create(
            from_=settings.TWILIO_WHATSAPP_NUMBER,
            to=_to_whatsapp_number(to_phone),
            body=message
        )
        logger.info(f"WhatsApp alert sent to {to_phone} for alert {alert_id}")
        return True

    except Exception as e:
        logger.error(f"WhatsApp send failed to {to_phone}: {e}")
        return False


def send_cancellation_message(to_phone: str, user_name: str) -> bool:
    """Notify contacts that the alert was cancelled — false alarm."""
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            from_=settings.TWILIO_WHATSAPP_NUMBER,
            to=_to_whatsapp_number(to_phone),
            body=(
                f"✅ *SafeHer Update*\n\n"
                f"{user_name} has cancelled the alert. They are safe. 🙏\n\n"
                f"_No further action needed._"
            )
        )
        return True
    except Exception as e:
        logger.error(f"Cancellation message failed: {e}")
        return False
