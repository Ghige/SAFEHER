# AI Data Review Policy

Reuses Stage 6 dual-review rules for lab audio. Real-world events are **metadata-only** (no WAV). Reviewers must be conservative: if metadata is insufficient, verdict **AMBIGUOUS**.

## Verdicts

| Verdict | Meaning | Gold? |
|---------|---------|-------|
| `DISTRESS` | Human confirms distress-quality event | Only after **two different reviewer_ids** both choose DISTRESS **and** `license_status` in `{SAFE, ATTRIBUTION_REQUIRED}` (lab) or `{USER_CONSENT_OPT_IN}` (real-world) |
| `HARD_NEGATIVE` | Human confirms non-emergency / false AI alert | After **at least one** human HARD_NEGATIVE + license OK. Dual agreement recorded but not required. |
| `REJECT` | Unusable / policy violation | Never gold |
| `AMBIGUOUS` | Unsure | Never gold |

## Never auto-promote

- AI predictions
- `UNREVIEWED` rows
- `USER_CONFIRMED_*` / `AI_*_CANDIDATE` category names
- `LIKELY_DISTRESS`
- Heuristic folder labels (Stage 6)

## Tools

| Queue | Command |
|-------|---------|
| Stage 6 lab clips | `python training/stage6_gold_review.py` |
| Real-world metadata | `python scripts/export_ai_feedback_candidates.py` then `python training/review_ai_feedback.py --import ... --reviewer <id>` |

Audit trail: `safeher_ai/data/training_logs/realworld_gold/promotion_audit.jsonl` and `reviews.csv`.

## Account deletion

Personal identifiers are removed. Anonymized metadata (no `user_id`) may remain for review if it was collected under opt-in. It still cannot enter gold without human verdicts.

## Status

| Item | Status |
|------|--------|
| Policy encoded in review scripts | **VERIFIED** |
| Dual DISTRESS gate | **VERIFIED** (code) |
| Production reviews completed | **NOT VERIFIED** (zero real-world gold rows) |
