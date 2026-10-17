"""
Stage 9/11 durable audit log (append-only JSONL) + retention purge.

Stores security-relevant events without secrets/PII payloads.
Does not enable SOS or train models.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)
_lock = threading.Lock()

_DEFAULT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "audit_logs"

_REDACT_KEY_FRAGMENTS = (
    "password",
    "token",
    "secret",
    "otp",
    "authorization",
    "cookie",
    "phone",
    "lat",
    "lon",
    "longitude",
    "latitude",
    "email",
    "transcript",
    "audio",
    "pcm",
    "wav",
    "maps",
    "track_url",
    "track_token",
    "name",
    "recipient",
)


def _audit_dir() -> Path:
    raw = (getattr(settings, "AUDIT_LOG_DIR", "") or "").strip()
    root = Path(raw) if raw else _DEFAULT_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _audit_path() -> Path:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _audit_dir() / f"audit_{day}.jsonl"


def _redact(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            lk = str(k).lower()
            if any(s in lk for s in _REDACT_KEY_FRAGMENTS):
                out[k] = "[REDACTED]"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def write_audit_event(
    event: str,
    *,
    actor_id: Optional[str] = None,
    request_id: Optional[str] = None,
    detail: Optional[dict[str, Any]] = None,
) -> None:
    """Append one audit event. Never raises to callers (fail-safe logging)."""
    try:
        record = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": event,
            "actor_id": actor_id,
            "request_id": request_id,
            "environment": settings.ENVIRONMENT,
            "ai_auto_sos_enabled": bool(settings.AI_AUTO_SOS_ENABLED),
            "detail": _redact(detail or {}),
        }
        line = json.dumps(record, ensure_ascii=False)
        path = _audit_path()
        with _lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            purge_old_audit_files()
    except Exception as exc:
        logger.error("audit write failed: %s", exc)


def purge_old_audit_files() -> int:
    """
    Delete audit_*.jsonl older than AUDIT_RETENTION_DAYS.
    Returns number of files removed. Fail-safe.
    """
    try:
        days = int(getattr(settings, "AUDIT_RETENTION_DAYS", 30) or 30)
        if days <= 0:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        removed = 0
        root = _audit_dir()
        for path in root.glob("audit_*.jsonl"):
            # audit_YYYY-MM-DD.jsonl
            stem = path.stem  # audit_2026-08-31
            try:
                day_s = stem.split("_", 1)[1]
                file_day = datetime.strptime(day_s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if file_day < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        return removed
    except Exception as exc:
        logger.warning("audit purge failed: %s", exc)
        return 0
