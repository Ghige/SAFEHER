"""Stage 2: DB uniqueness / IntegrityError mapping for contacts and alerts."""

from uuid import uuid4
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import IntegrityError

from app.services import alert_service


def test_trigger_alert_maps_integrity_error_to_duplicate_message():
    db = MagicMock()
    user = MagicMock()
    user.id = uuid4()
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = user

    with patch.object(alert_service, "get_active_alert", return_value=None):
        # contact_count path uses another query chain
        contact_q = MagicMock()
        contact_q.filter.return_value.count.return_value = 1

        def query_side_effect(model):
            if model is alert_service.User:
                q = MagicMock()
                q.filter.return_value.with_for_update.return_value.first.return_value = user
                return q
            if model is alert_service.EmergencyContact:
                return contact_q
            return MagicMock()

        db.query.side_effect = query_side_effect
        db.commit.side_effect = IntegrityError("stmt", {}, Exception("unique"))

        try:
            alert_service.trigger_alert(db, user.id, "manual", 19.0, 72.0)
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "already exists" in str(exc).lower()
            db.rollback.assert_called()
