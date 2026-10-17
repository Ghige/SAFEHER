"""Print Stage 6 gold-label progress (no training, read-only compute)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from stage6_gold_review import (  # noqa: E402
    GOLD_DIR,
    TARGET_DISTRESS,
    TARGET_HN_ADDITIONAL,
    LEGACY_HN,
    load_reviews,
    persist_all,
    progress_payload,
)


def main() -> None:
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    reviews = load_reviews()
    prog = persist_all(reviews)
    c = prog["counts"]
    print("Stage 6 gold progress")
    print(f"  confirmed DISTRESS     : {c['confirmed_DISTRESS']} / {TARGET_DISTRESS}  (remaining {c['remaining_confirmed_DISTRESS']})")
    print(f"  verified HN (stage6)   : {c['verified_HARD_NEGATIVE_stage6']} / {TARGET_HN_ADDITIONAL} additional  (remaining {c['remaining_additional_HARD_NEGATIVE']})")
    print(f"  legacy HN (pre-stage6) : {LEGACY_HN}")
    print(f"  total HN incl legacy   : {c['total_HARD_NEGATIVE_incl_legacy']}")
    print(f"  awaiting 2nd DISTRESS  : {c['distress_awaiting_second_reviewer']}")
    print(f"  review rows            : {c['review_rows']}")
    print(f"  store                  : {GOLD_DIR}")
    print()
    print(json.dumps(prog, indent=2))


if __name__ == "__main__":
    main()
