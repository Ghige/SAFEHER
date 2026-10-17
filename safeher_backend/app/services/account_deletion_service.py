"""Play Store account deletion — personal data cascade.

Anonymizes AI feedback metadata (no user_id). Deletes WAV queue files.
Does not enable SOS and does not promote gold labels.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.ai_dataset import AiDatasetSample
from app.models.blocklist import Blocklist
from app.models.contact import EmergencyContact
from app.models.helper import Helper
from app.models.user import User
from app.services.ai_feedback_service import anonymize_user_feedback
from app.services.audit_log import write_audit_event

logger = logging.getLogger(__name__)


def delete_user_account(db: Session, user: User) -> None:
    uid: uuid.UUID = user.id
    actor = str(uid)

    helper_as_responder = (
        db.query(Helper).filter(Helper.helper_user_id == uid).delete(synchronize_session=False)
    )

    alerts = db.query(Alert).filter(Alert.user_id == uid).all()
    alert_ids = [a.id for a in alerts]
    helpers_on_own = 0
    if alert_ids:
        helpers_on_own = (
            db.query(Helper)
            .filter(Helper.alert_id.in_(alert_ids))
            .delete(synchronize_session=False)
        )
    for alert in alerts:
        db.delete(alert)

    contacts = (
        db.query(EmergencyContact).filter(EmergencyContact.user_id == uid).delete(
            synchronize_session=False
        )
    )
    blocks = (
        db.query(Blocklist).filter(Blocklist.user_id == uid).delete(synchronize_session=False)
    )

    wav_removed = 0
    samples = db.query(AiDatasetSample).filter(AiDatasetSample.user_id == uid).all()
    for sample in samples:
        path = Path(sample.storage_path) if sample.storage_path else None
        if path and path.is_file():
            try:
                path.unlink()
                wav_removed += 1
            except OSError as exc:
                logger.warning("Failed to delete dataset file %s: %s", sample.storage_path, exc)
        db.delete(sample)

    anonymized = anonymize_user_feedback(db, uid)

    db.delete(user)
    db.commit()

    write_audit_event(
        "account_deleted",
        actor_id=actor,
        detail={
            "alerts_deleted": len(alerts),
            "helpers_deleted": int(helper_as_responder) + int(helpers_on_own),
            "contacts_deleted": int(contacts),
            "blocklist_deleted": int(blocks),
            "dataset_samples_deleted": len(samples),
            "wav_files_removed": wav_removed,
            "feedback_anonymized": anonymized,
        },
    )
    logger.info("Account deleted user=%s alerts=%s samples=%s", actor, len(alerts), len(samples))
