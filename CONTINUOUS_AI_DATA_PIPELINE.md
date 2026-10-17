# Continuous AI Data Pipeline

**Date:** 2026-09-16  
**Automatic retraining:** forbidden  
**Automatic gold promotion:** forbidden  
**Raw microphone / precise location / phone numbers:** not stored by this pipeline

## Status

**Safely implemented in the repository.** Not yet populated with reviewed gold from real usage.

```
Real usage (opt-in Help improve AI)
        ↓
AI prediction + confirm-first UI
        ↓
POST /api/v1/ai/feedback  (metadata only)
        ↓
Candidate row (gold_eligible=false, review_status=UNREVIEWED)
        ↓
Export JSONL → Stage-6-style human review
        ↓
DISTRESS (dual reviewers + USER_CONSENT_OPT_IN)
HARD_NEGATIVE (human verdict + license)
        ↓
Gold CSVs under safeher_ai/data/training_logs/realworld_gold/
        ↓
retraining_gate.py  (counts, leakage, license)  — does NOT train
        ↓
Manual approval required before any future training job
```

## What was implemented

| Piece | Location |
|-------|----------|
| Feedback API | `POST /api/v1/ai/feedback` |
| WAV upload retired | `POST /api/v1/ai/datasets/queue` → HTTP 410 |
| Classifier | `ai_feedback_service.classify_feedback` / Android `AiFeedbackClassifier` |
| DB | Alembic `008_ai_feedback_events` |
| Account deletion anonymizes `user_id` | `account_deletion_service` |
| Review UI | `safeher_ai/training/review_ai_feedback.py` |
| Export | `safeher_backend/scripts/export_ai_feedback_candidates.py` |
| Retraining gate | `safeher_ai/training/retraining_gate.py` (exit 2 today; **no training**) |

## Categories (candidates, never auto-gold)

| Category | When |
|----------|------|
| `USER_CONFIRMED_DISTRESS` | User taps Yes / need help |
| `AI_FALSE_POSITIVE_CANDIDATE` | User cancels / I'm safe after AI prompt |
| `USER_CONFIRMED_NORMAL` | User confirms normal when prediction was not emergency |
| `AI_FALSE_NEGATIVE_CANDIDATE` | Reserved (prediction NORMAL + explicit miss report; not wired in UI yet) |
| `AI_POSITIVE_CANDIDATE` | Reserved |
| `UNREVIEWED` | Timeout / no verdict |

False AI alerts (user cancel) → `HARD_NEGATIVE_CANDIDATE` (`fp_fn_status`).  
True distress (user confirm) → `DISTRESS_CANDIDATE`.  
Neither enters gold until human review.

## Consent

- Toggle **Help improve AI** defaults **off**.
- Payload must send `consent_granted=true` and `consent_version=privacy-v2-metadata-only`.
- Allowlisted numeric features only (`rms`, `peak`, `zcr`, `pitch_hz`, `centroid_hz`, `rolling_avg`, `duration_seconds`).
- Keys such as `latitude`, `phone`, `transcript`, `wav` are rejected.

## Leakage

`gold_policy.assign_split(event_id)` is MD5-stable: same event/session cannot be assigned both train and test. Gate fails if a gold CSV shows two splits for one id.

## Current gold eligibility

| Store | DISTRESS | HARD_NEGATIVE |
|-------|----------|----------------|
| Stage 6 lab gold CSVs (this tree) | 0 | 0 |
| Real-world gold CSVs | 0 | 0 |

**Eligible for future training today: none.**

## Status of this pipeline

| Check | Status |
|-------|--------|
| Metadata-only collection | **VERIFIED** (API tests) |
| Never auto gold | **VERIFIED** (`gold_eligible` always false on insert) |
| Never auto retrain | **VERIFIED** (`retraining_gate.py` this run: `training_executed=false`, exit 2) |
| Live app → production API events | **NOT VERIFIED** |
| Human review of real events | **NOT VERIFIED** (no production traffic) |
