"""Unit tests for Meta WhatsApp alert delivery."""

import json
from unittest.mock import MagicMock, patch

import httpx

from app.services import meta_whatsapp_service


def _mock_meta_response(*, status_code: int = 200, message_id: str = "wamid.test123"):
    response = MagicMock(spec=httpx.Response)
    response.is_success = status_code < 400
    response.status_code = status_code
    response.text = '{"messages":[{"id":"wamid.test123"}]}' if status_code < 400 else '{"error":{"code":131047,"message":"Invalid recipient"}}'
    if status_code < 400:
        response.json.return_value = {"messages": [{"id": message_id}]}
    else:
        response.json.return_value = {
            "error": {"code": 131047, "message": "Invalid recipient"}
        }
    return response


@patch("app.services.meta_whatsapp_service.httpx.Client")
@patch("app.services.meta_whatsapp_service.settings")
def test_send_whatsapp_alert_success(mock_settings, mock_client_cls):
    mock_settings.META_ACCESS_TOKEN = "meta-token"
    mock_settings.META_PHONE_NUMBER_ID = "1317778761409496"
    mock_settings.META_WABA_ID = "1052905050650648"
    mock_settings.META_WHATSAPP_TEMPLATE_ALERT = ""
    mock_settings.META_WHATSAPP_TEMPLATE_LANGUAGE = ""
    mock_settings.TRACK_BASE_URL = "https://safeher.app/track"
    mock_settings.PHONE_COUNTRY_CODE = "91"

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = _mock_meta_response()
    mock_client_cls.return_value = mock_client

    result = meta_whatsapp_service.send_whatsapp_alert(
        to_phone="7498506625",
        user_name="Aditi",
        latitude=19.076,
        longitude=72.8777,
        alert_id="alert-123",
        trigger_type="manual",
        track_token="signed-jwt",
    )

    assert result is True
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer meta-token"
    assert "1317778761409496/messages" in mock_client.post.call_args.args[0]

    payload = call_kwargs["json"]
    assert payload["type"] == "template"
    assert payload["to"] == "917498506625"
    assert payload["template"]["name"] == "hello_world"
    assert payload["template"]["language"]["code"] == "en_US"
    assert "components" not in payload["template"]


@patch("app.services.meta_whatsapp_service.httpx.Client")
@patch("app.services.meta_whatsapp_service.settings")
def test_send_whatsapp_alert_custom_template(mock_settings, mock_client_cls):
    mock_settings.META_ACCESS_TOKEN = "meta-token"
    mock_settings.META_PHONE_NUMBER_ID = "1317778761409496"
    mock_settings.META_WABA_ID = "1052905050650648"
    mock_settings.META_WHATSAPP_TEMPLATE_ALERT = "safeher_alert"
    mock_settings.META_WHATSAPP_TEMPLATE_LANGUAGE = "en"
    mock_settings.TRACK_BASE_URL = "https://safeher.app/track"
    mock_settings.PHONE_COUNTRY_CODE = "91"

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = _mock_meta_response()
    mock_client_cls.return_value = mock_client

    meta_whatsapp_service.send_whatsapp_alert(
        to_phone="7498506625",
        user_name="Aditi",
        alert_id="alert-123",
    )

    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["template"]["name"] == "safeher_alert"
    params = payload["template"]["components"][0]["parameters"]
    assert params[0]["text"] == "Aditi"


@patch("app.services.meta_whatsapp_service.httpx.Client")
@patch("app.services.meta_whatsapp_service.settings")
def test_send_whatsapp_alert_failure_returns_false(mock_settings, mock_client_cls):
    mock_settings.META_ACCESS_TOKEN = "meta-token"
    mock_settings.META_PHONE_NUMBER_ID = "1317778761409496"
    mock_settings.META_WABA_ID = "1052905050650648"
    mock_settings.META_WHATSAPP_TEMPLATE_ALERT = ""
    mock_settings.META_WHATSAPP_TEMPLATE_LANGUAGE = ""
    mock_settings.TRACK_BASE_URL = "https://safeher.app/track"
    mock_settings.PHONE_COUNTRY_CODE = "91"

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = _mock_meta_response(status_code=400)
    mock_client_cls.return_value = mock_client

    result = meta_whatsapp_service.send_whatsapp_alert(
        to_phone="7498506625",
        user_name="Aditi",
        alert_id="alert-123",
    )

    assert result is False


@patch("app.services.meta_whatsapp_service.httpx.Client")
@patch("app.services.meta_whatsapp_service.settings")
def test_send_whatsapp_alert_missing_config_returns_false(mock_settings, mock_client_cls):
    mock_settings.META_ACCESS_TOKEN = ""
    mock_settings.META_PHONE_NUMBER_ID = ""
    mock_settings.META_WHATSAPP_TEMPLATE_ALERT = ""
    mock_settings.META_WHATSAPP_TEMPLATE_LANGUAGE = ""
    mock_settings.TRACK_BASE_URL = "https://safeher.app/track"
    mock_settings.PHONE_COUNTRY_CODE = "91"

    result = meta_whatsapp_service.send_whatsapp_alert(
        to_phone="7498506625",
        user_name="Aditi",
        alert_id="alert-123",
    )

    assert result is False
    mock_client_cls.assert_not_called()


@patch("app.services.meta_whatsapp_service.httpx.Client")
@patch("app.services.meta_whatsapp_service.settings")
def test_send_cancellation_message_success(mock_settings, mock_client_cls):
    mock_settings.META_ACCESS_TOKEN = "meta-token"
    mock_settings.META_PHONE_NUMBER_ID = "1317778761409496"
    mock_settings.META_WABA_ID = "1052905050650648"
    mock_settings.META_WHATSAPP_TEMPLATE_CANCEL = ""
    mock_settings.META_WHATSAPP_TEMPLATE_LANGUAGE = ""
    mock_settings.PHONE_COUNTRY_CODE = "91"

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = _mock_meta_response()
    mock_client_cls.return_value = mock_client

    result = meta_whatsapp_service.send_cancellation_message("7498506625", "Aditi")

    assert result is True
    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["template"]["name"] == "hello_world"
    assert payload["to"] == "917498506625"
