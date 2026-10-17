#!/usr/bin/env python3
"""Export UNREVIEWED AI feedback candidates as JSONL (no user_id, no PII)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models.ai_feedback import AiFeedbackEvent
from app.services.ai_feedback_service import event_to_dict


def main() -> int:
    out = Path(__file__).resolve().parents[1] / "data" / "ai_feedback_export.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        rows = (
            db.query(AiFeedbackEvent)
            .filter(AiFeedbackEvent.gold_eligible.is_(False))
            .all()
        )
        with out.open("w", encoding="utf-8") as f:
            for row in rows:
                rec = event_to_dict(row)
                rec.pop("user_id", None)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"Wrote {len(rows)} candidates to {out}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
