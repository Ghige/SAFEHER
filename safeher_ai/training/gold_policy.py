"""Shared gold / leakage / license policy. Never auto-promotes candidates."""

from __future__ import annotations

import hashlib

FORBIDDEN_GOLD_LABELS = frozenset({
    "LIKELY_DISTRESS",
    "UNREVIEWED",
    "AMBIGUOUS",
    "REJECT",
    "AI_POSITIVE_CANDIDATE",
    "AI_FALSE_POSITIVE_CANDIDATE",
    "AI_FALSE_NEGATIVE_CANDIDATE",
    "USER_CONFIRMED_DISTRESS",
    "USER_CONFIRMED_NORMAL",
})

GOLD_VERDICTS = frozenset({"DISTRESS", "HARD_NEGATIVE"})
REVIEW_VERDICTS = ("DISTRESS", "HARD_NEGATIVE", "REJECT", "AMBIGUOUS")

LICENSE_OK_STAGE6 = frozenset({"SAFE", "ATTRIBUTION_REQUIRED"})
LICENSE_OK_REALWORLD = frozenset({"USER_CONSENT_OPT_IN"})
LICENSE_OK_ALL = LICENSE_OK_STAGE6 | LICENSE_OK_REALWORLD

TARGET_DISTRESS = 500
TARGET_HARD_NEGATIVE = 1000


def assign_split(event_id: str) -> str:
    """Deterministic train/val/test from event/session id. Same id never crosses splits."""
    digest = hashlib.md5(event_id.encode("utf-8")).hexdigest()
    h = int(digest[:8], 16) % 10
    if h == 0:
        return "test"
    if h == 1:
        return "val"
    return "train"


def leakage_pairs(rows: list[dict], id_key: str = "event_id") -> list[tuple[str, str, str]]:
    """Return (id, split_a, split_b) when the same id appears in more than one split."""
    by_id: dict[str, set[str]] = {}
    for r in rows:
        eid = str(r.get(id_key) or r.get("session_id") or r.get("source_id") or "").strip()
        split = str(r.get("split") or r.get("split_bucket") or "").strip()
        if not eid or not split:
            continue
        by_id.setdefault(eid, set()).add(split)
    leaks = []
    for eid, splits in by_id.items():
        if len(splits) > 1:
            ordered = sorted(splits)
            leaks.append((eid, ordered[0], ordered[1] if len(ordered) > 1 else ordered[0]))
    return leaks
