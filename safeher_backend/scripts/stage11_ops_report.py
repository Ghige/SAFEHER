#!/usr/bin/env python3
"""
Stage 11 ops report — summarize local audit JSONL + metrics endpoint if reachable.

Does NOT enable AI SOS. Does NOT send WhatsApp/alerts.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = ROOT / "data" / "audit_logs"
OUT = (
    ROOT.parent
    / "safeher_ai"
    / "data"
    / "training_logs"
    / "stage11_ops_report.json"
)


def summarize_audit(audit_dir: Path) -> dict:
    events: Counter[str] = Counter()
    files = sorted(audit_dir.glob("audit_*.jsonl")) if audit_dir.is_dir() else []
    lines = 0
    ai_flag_false = 0
    for path in files[-14:]:  # last ~2 weeks of daily files
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            lines += 1
            events[row.get("event", "unknown")] += 1
            if row.get("ai_auto_sos_enabled") is False:
                ai_flag_false += 1
    return {
        "audit_dir": str(audit_dir),
        "files_scanned": len(files[-14:]),
        "events_total": lines,
        "events_by_type": dict(events),
        "ai_auto_sos_false_count": ai_flag_false,
    }


def main() -> int:
    audit_dir = Path(os.environ.get("AUDIT_LOG_DIR") or DEFAULT_AUDIT)
    base = os.environ.get("SAFEHER_OPS_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ai_auto_sos_enabled_expected": False,
        "audit": summarize_audit(audit_dir),
        "live": {},
    }
    try:
        ping = httpx.get(f"{base}/api/v1/ping/", timeout=3.0)
        report["live"]["ping_status"] = ping.status_code
        report["live"]["ping_body"] = ping.json() if ping.is_success else None
        metrics = httpx.get(f"{base}/api/v1/ping/metrics", timeout=3.0)
        report["live"]["metrics_status"] = metrics.status_code
        report["live"]["metrics"] = metrics.json() if metrics.is_success else None
        ready = httpx.get(f"{base}/api/v1/ping/ready", timeout=5.0)
        report["live"]["ready_status"] = ready.status_code
        report["live"]["ready_body"] = ready.json() if ready.content else None
    except Exception as exc:
        report["live"]["error"] = type(exc).__name__
        report["live"]["note"] = "Backend not reachable — audit summary only"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
