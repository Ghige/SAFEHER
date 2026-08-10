"""
WhatsApp alert service via Meta WhatsApp Cloud API.

Emergency contacts receive a WhatsApp message with:
  - What happened (trigger type)
  - Google Maps link to last known location
  - Signed live tracking link (no app install needed)

API: POST https://graph.facebook.com/v23.0/{phone-number-id}/messages
Docs: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages

Development: uses Meta's pre-approved sample template (hello_world).
Production: set META_WHATSAPP_TEMPLATE_ALERT / META_WHATSAPP_TEMPLATE_CANCEL
to your approved utility templates with {{1}}…{{4}} body placeholders.
"""

from __future__ import annotations

import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_META_GRAPH_BASE = "https://graph.facebook.com"
_META_API_VERSION = "v23.0"
_DEV_SAMPLE_TEMPLATE = "hello_world"
_DEV_SAMPLE_LANGUAGE = "en_US"

_TRIGGER_LABELS = {
    "manual": "pressed the SOS button",
    "voice": "triggered a voice SOS",
    "ai_audio": "AI detected a distress sound",
    "ai_movement": "AI detected panic movement",
    "shake": "shook their phone for SOS",
    "escalated": "may be in danger — their phone stopped responding",
}


def _to_e164_digits(phone_number: str) -> str:
    """Normalise a stored phone number to E.164 digits (no +) for Meta API."""
    phone = phone_number.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        return phone[1:]
    phone = phone.lstrip("0")
    cc = settings.PHONE_COUNTRY_CODE
    if phone.startswith(cc) and len(phone) > len(cc):
        return phone
    return f"{cc}{phone}"


def _single_line(value: str) -> str:
    """Template variable values must not contain newlines."""
    return " ".join(value.split())


def _messages_url() -> str:
    return f"{_META_GRAPH_BASE}/{_META_API_VERSION}/{settings.META_PHONE_NUMBER_ID}/messages"


def _meta_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def _template_needs_body_parameters(template_name: str) -> bool:
    return template_name != _DEV_SAMPLE_TEMPLATE


def _build_template_payload(
    *,
    to_phone: str,
    template_name: str,
    language_code: str,
    body_parameters: list[str],
) -> dict:
    template: dict = {
        "name": template_name,
        "language": {"code": language_code},
    }
    if body_parameters and _template_needs_body_parameters(template_name):
        template["components"] = [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": param} for param in body_parameters],
            }
        ]

    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": _to_e164_digits(to_phone),
        "type": "template",
        "template": template,
    }


def _log_response_error(to_phone: str, log_context: str, response: httpx.Response) -> None:
    response_body = response.text
    error_code = None
    error_message = None
    try:
        error = response.json().get("error", {})
        error_code = error.get("code")
        error_message = error.get("message")
    except Exception:
        pass

    logger.error(
        "WhatsApp send failed to %s (%s): status=%s error_code=%s error_message=%s response_body=%s",
        to_phone,
        log_context,
        response.status_code,
        error_code,
        error_message,
        response_body,
    )


def _send_template_message(
    *,
    to_phone: str,
    template_name: str,
    language_code: str,
    body_parameters: list[str],
    log_context: str,
) -> bool:
    if not settings.META_ACCESS_TOKEN or not settings.META_PHONE_NUMBER_ID:
        logger.error(
            "Meta WhatsApp not configured: META_ACCESS_TOKEN and META_PHONE_NUMBER_ID are required"
        )
        return False

    payload = _build_template_payload(
        to_phone=to_phone,
        template_name=template_name,
        language_code=language_code,
        body_parameters=body_parameters,
    )
    url = _messages_url()
    recipient = payload["to"]

    logger.info(
        "Meta WhatsApp request url=%s phone_number_id=%s waba_id=%s recipient=%s "
        "template=%s context=%s payload=%s",
        url,
        settings.META_PHONE_NUMBER_ID,
        settings.META_WABA_ID,
        recipient,
        template_name,
        log_context,
        json.dumps(payload),
    )

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=_meta_headers(), json=payload)

        logger.info(
            "Meta WhatsApp response context=%s status=%s body=%s",
            log_context,
            response.status_code,
            response.text,
        )

        if response.is_success:
            data = response.json()
            message_id = data.get("messages", [{}])[0].get("id", "unknown")
            logger.info(
                "WhatsApp message sent to %s (%s) message_id=%s",
                to_phone,
                log_context,
                message_id,
            )
            return True

        _log_response_error(to_phone, log_context, response)
        return False

    except Exception as exc:
        logger.error("WhatsApp send failed to %s (%s): %s", to_phone, log_context, exc)
        return False


def _alert_template_name() -> str:
    return settings.META_WHATSAPP_TEMPLATE_ALERT or _DEV_SAMPLE_TEMPLATE


def _cancel_template_name() -> str:
    return settings.META_WHATSAPP_TEMPLATE_CANCEL or _DEV_SAMPLE_TEMPLATE


def _template_language() -> str:
    if settings.META_WHATSAPP_TEMPLATE_LANGUAGE:
        return settings.META_WHATSAPP_TEMPLATE_LANGUAGE
    if _alert_template_name() == _DEV_SAMPLE_TEMPLATE:
        return _DEV_SAMPLE_LANGUAGE
    return "en"


def send_whatsapp_alert(
    to_phone: str,
    user_name: str,
    alert_id: str,
    latitude: float | None = None,
    longitude: float | None = None,
    trigger_type: str = "manual",
    track_token: str | None = None,
) -> bool:
    """
    Send WhatsApp alert to an emergency contact via Meta Cloud API.
    Contact does NOT need any app installed.
    """
    if track_token:
        live_link = f"{settings.TRACK_BASE_URL}?token={track_token}"
    else:
        live_link = f"{settings.TRACK_BASE_URL}/{alert_id}"

    trigger_text = _TRIGGER_LABELS.get(trigger_type, "triggered an alert")

    if latitude is not None and longitude is not None:
        location_text = _single_line(f"https://maps.google.com/?q={latitude},{longitude}")
    else:
        location_text = "Location unavailable — use the live tracking link below."

    body_parameters = [
        _single_line(user_name),
        _single_line(trigger_text),
        location_text,
        _single_line(live_link),
    ]

    return _send_template_message(
        to_phone=to_phone,
        template_name=_alert_template_name(),
        language_code=_template_language(),
        body_parameters=body_parameters,
        log_context=f"alert_id={alert_id}",
    )


def send_cancellation_message(to_phone: str, user_name: str) -> bool:
    """Notify contacts that the alert was cancelled — false alarm."""
    return _send_template_message(
        to_phone=to_phone,
        template_name=_cancel_template_name(),
        language_code=_template_language(),
        body_parameters=[_single_line(user_name)],
        log_context="cancellation",
    )
