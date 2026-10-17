"""
Redis service — wraps all Redis access for the app.

Used for:
  - Dead man's switch ping tracking (replaces in-memory dict)
  - Rate limiting counters

Falls back gracefully if Redis is unavailable (logs a warning, uses
in-memory fallback so the app still works in dev without Redis).
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

_redis_client = None
_redis_available = None   # None = not yet tested
_redis_warned = False

# ── In-memory fallback (dev / Redis unavailable) ──────────────────────────────
_memory_store: dict = {}


def _get_client():
    global _redis_client, _redis_available, _redis_warned
    if _redis_available is False:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        from app.config import settings
        client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=2)
        client.ping()
        _redis_client = client
        _redis_available = True
        logger.info("Redis connected")
        return _redis_client
    except Exception as e:
        _redis_available = False
        if not _redis_warned:
            from app.config import settings
            from app.security.production_guards import is_production_like

            if is_production_like(settings) and settings.REQUIRE_REDIS_IN_PRODUCTION:
                logger.error(
                    "Redis unavailable in production/staging (%s). "
                    "In-memory fallback is disabled for multi-worker safety.",
                    e,
                )
            else:
                logger.warning(
                    "Redis unavailable (%s). Using in-memory fallback — "
                    "NOT suitable for production multi-worker deployments.",
                    e,
                )
            _redis_warned = True
        return None


def is_redis_available() -> bool:
    """Return True when Redis is connected (required for reliable dead-man switch)."""
    return _get_client() is not None


# ── Dead man's switch pings ───────────────────────────────────────────────────

PING_KEY_PREFIX = "safeher:ping:"
PING_TTL_SECONDS = 600   # 10 min — auto-expire so Redis doesn't accumulate stale keys


def record_ping(alert_id: str, timestamp: float | None = None) -> None:
    """Record a heartbeat for the given alert. Called every 60s by the app."""
    key = PING_KEY_PREFIX + alert_id
    ts = timestamp if timestamp is not None else time.time()
    client = _get_client()
    if client:
        try:
            client.set(key, str(ts), ex=PING_TTL_SECONDS)
            return
        except Exception as e:
            logger.error(f"Redis ping write failed: {e}")
    # Fallback
    _memory_store[key] = ts


def get_last_ping(alert_id: str) -> Optional[float]:
    """Return the timestamp of the last ping, or None if never pinged."""
    key = PING_KEY_PREFIX + alert_id
    client = _get_client()
    if client:
        try:
            val = client.get(key)
            return float(val) if val else None
        except Exception as e:
            logger.error(f"Redis ping read failed: {e}")
    return _memory_store.get(key)


def delete_ping(alert_id: str) -> None:
    """Remove ping record when an alert is resolved/cancelled."""
    key = PING_KEY_PREFIX + alert_id
    client = _get_client()
    if client:
        try:
            client.delete(key)
        except Exception:
            pass
    _memory_store.pop(key, None)


# ── Rate limiting ─────────────────────────────────────────────────────────────

RL_KEY_PREFIX = "safeher:rl:"


def check_rate_limit(identifier: str, limit: int, window_seconds: int = 60) -> bool:
    """
    Sliding window rate limiter.

    Args:
        identifier:     unique key, e.g. "auth:register:+919876543210"
        limit:          max requests allowed in the window
        window_seconds: window size in seconds

    Returns True if the request is allowed, False if it exceeds the limit.
    """
    key = RL_KEY_PREFIX + identifier
    client = _get_client()

    if client:
        try:
            pipe = client.pipeline()
            now = time.time()
            window_start = now - window_seconds
            # Sorted set: score = timestamp, member = timestamp string
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window_seconds + 1)
            results = pipe.execute()
            count = results[2]
            return count <= limit
        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            # Fail closed — deny request when rate-limit state is unavailable
            return False

    # In-memory fallback (simple, not multi-process safe)
    from app.config import settings
    from app.security.production_guards import is_production_like

    if is_production_like(settings) and settings.REQUIRE_REDIS_IN_PRODUCTION:
        logger.error(
            "Rate limit denied: Redis required in production but unavailable (id=%s)",
            identifier,
        )
        return False

    now = time.time()
    window_start = now - window_seconds
    store_key = f"_rl_{key}"
    timestamps = [t for t in _memory_store.get(store_key, []) if t > window_start]
    timestamps.append(now)
    _memory_store[store_key] = timestamps
    return len(timestamps) <= limit
