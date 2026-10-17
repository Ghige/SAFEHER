"""
Stage 11 — in-process ops metrics (no external Prometheus required).

Thread-safe counters + latency samples for health dashboards /reports.
Does not enable AI SOS. Does not send alerts.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any

_lock = threading.Lock()
_started = time.time()

_counters: dict[str, int] = defaultdict(int)
_latency_ms: dict[str, list[float]] = defaultdict(list)
_MAX_SAMPLES = 500


def incr(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] += amount


def observe_ms(name: str, value_ms: float) -> None:
    with _lock:
        bucket = _latency_ms[name]
        bucket.append(float(value_ms))
        if len(bucket) > _MAX_SAMPLES:
            del bucket[: len(bucket) - _MAX_SAMPLES]


def _percentile(sorted_vals: list[float], pct: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    idx = int(round((pct / 100.0) * (len(sorted_vals) - 1)))
    idx = max(0, min(idx, len(sorted_vals) - 1))
    return sorted_vals[idx]


def snapshot() -> dict[str, Any]:
    with _lock:
        counters = dict(_counters)
        latency: dict[str, Any] = {}
        for name, samples in _latency_ms.items():
            ordered = sorted(samples)
            latency[name] = {
                "count": len(ordered),
                "p50_ms": _percentile(ordered, 50),
                "p95_ms": _percentile(ordered, 95),
                "max_ms": ordered[-1] if ordered else None,
            }
    return {
        "uptime_seconds": round(time.time() - _started, 1),
        "counters": counters,
        "latency": latency,
    }


def reset_for_tests() -> None:
    with _lock:
        _counters.clear()
        _latency_ms.clear()
