"""
Background scheduler for alert lifecycle tasks.

Runs check_dead_switches() on a fixed interval so the dead man's switch
escalates alerts when the app stops pinging.
"""

import asyncio
import logging

from app.config import settings
from app.db.session import SessionLocal
from app.services.dead_switch import check_dead_switches

logger = logging.getLogger(__name__)

_CHECK_INTERVAL_SECONDS = 60


async def run_dead_switch_scheduler() -> None:
    """Poll active alerts and escalate when pings stop."""
    logger.info(
        "Dead switch scheduler started (interval=%ss, timeout=%ss)",
        _CHECK_INTERVAL_SECONDS,
        settings.DEAD_SWITCH_TIMEOUT_SECONDS,
    )
    while True:
        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            await asyncio.to_thread(check_dead_switches, db)
        except Exception:
            logger.exception("Dead switch check failed")
        finally:
            db.close()
