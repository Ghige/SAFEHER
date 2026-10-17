#!/usr/bin/env python3
"""
Validate Redis reachability for SafeHer P0-4.

Does NOT enable AI SOS. Does NOT send alerts.
Exit 0 = ping OK; exit 1 = unreachable; exit 2 = redis package/config issue.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        try:
            from app.config import settings

            url = settings.REDIS_URL
        except Exception as exc:
            print(f"REDIS_URL missing and settings load failed: {exc}")
            return 2

    try:
        import redis
    except ImportError:
        print("redis package not installed")
        return 2

    try:
        client = redis.from_url(
            url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2
        )
        pong = client.ping()
        client.close()
    except Exception as exc:
        print(f"REDIS_STATUS=UNAVAILABLE error={type(exc).__name__}: {exc}")
        print("NOT VERIFIED: start Redis (e.g. docker compose -f docker-compose.p0.yml up -d)")
        return 1

    print(f"REDIS_STATUS=OK ping={pong} url_scheme={url.split(':', 1)[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
