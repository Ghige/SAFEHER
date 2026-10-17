"""
Background scheduler for alert lifecycle tasks.

Runs check_dead_switches() on a fixed interval so the dead man's switch
escalates alerts when the app stops pinging.
"""

import asyncio
import logging
import time

from app.config import settings
from app.db.session import SessionLocal
from app.services.ai_dataset_service import purge_expired_dataset_samples
from app.services.ai_feedback_service import purge_unreviewed_feedback
from app.services.dead_switch import check_dead_switches

logger = logging.getLogger(__name__)

_CHECK_INTERVAL_SECONDS = 60
_PURGE_INTERVAL_SECONDS = 3600


async def run_dead_switch_scheduler() -> None:
    """Poll active alerts and escalate when pings stop. Hourly dataset/feedback purge."""
    logger.info(
        "Dead switch scheduler started (interval=%ss, timeout=%ss)",
        _CHECK_INTERVAL_SECONDS,
        settings.DEAD_SWITCH_TIMEOUT_SECONDS,
    )
    last_purge = 0.0
    while True:
        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            await asyncio.to_thread(check_dead_switches, db)
            now = time.time()
            if now - last_purge >= _PURGE_INTERVAL_SECONDS:
                await asyncio.to_thread(_run_retention_purge, db)
                last_purge = now
        except Exception:
            logger.exception("Dead switch check failed")
        finally:
            db.close()


def _run_retention_purge(db) -> None:
    try:
        purge_expired_dataset_samples(db)
    except Exception:
        logger.exception("Dataset sample purge failed")
    try:
        days = int(getattr(settings, "AI_FEEDBACK_UNREVIEWED_RETENTION_DAYS", 365))
        purge_unreviewed_feedback(db, days)
    except Exception:
        logger.exception("AI feedback purge failed")
