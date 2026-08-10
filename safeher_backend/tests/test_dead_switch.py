"""Unit tests for dead man's switch escalation logic."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models.alert import Alert
from app.models.contact import EmergencyContact
from app.models.user import User
from app.services.dead_switch import check_dead_switches


def _make_alert(**kwargs):
    alert = MagicMock(spec=Alert)
    alert.id = kwargs.get("id", uuid4())
    alert.user_id = kwargs.get("user_id", uuid4())
    alert.status = kwargs.get("status", "active")
    alert.latitude = kwargs.get("latitude", 19.0)
    alert.longitude = kwargs.get("longitude", 72.0)
    alert.started_at = kwargs.get("started_at", datetime.now(timezone.utc))
    return alert


@patch("app.services.dead_switch._escalate_alert")
@patch("app.services.dead_switch.redis_service")
def test_check_dead_switches_escalates_after_timeout(mock_redis, mock_escalate):
    alert = _make_alert()
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [alert]

    import time
    mock_redis.get_last_ping.return_value = time.time() - 400

    check_dead_switches(db)

    mock_escalate.assert_called_once_with(db, alert)


@patch("app.services.dead_switch.redis_service")
def test_check_dead_switches_sets_baseline_from_started_at(mock_redis):
    alert = _make_alert()
    started = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    alert.started_at = started
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [alert]
    mock_redis.get_last_ping.return_value = None

    check_dead_switches(db)

    mock_redis.record_ping.assert_called_once()
    args, kwargs = mock_redis.record_ping.call_args
    assert kwargs.get("timestamp") == started.timestamp()


@patch("app.services.dead_switch._escalate_alert")
@patch("app.services.dead_switch.redis_service")
def test_check_dead_switches_no_escalation_within_timeout(mock_redis, mock_escalate):
    alert = _make_alert()
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [alert]

    import time
    mock_redis.get_last_ping.return_value = time.time() - 30

    check_dead_switches(db)

    mock_escalate.assert_not_called()
