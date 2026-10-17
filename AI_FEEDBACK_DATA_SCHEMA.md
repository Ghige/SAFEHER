# AI Feedback Data Schema

Consent version: `privacy-v2-metadata-only`  
Table: `ai_feedback_events` (Alembic 008)

## Event (API `POST /api/v1/ai/feedback`)

| Field | Required | Notes |
|-------|----------|--------|
| `event_id` | yes | UUID; idempotent unique key |
| `session_id` | yes | Confirm-session id; used as source id for splits |
| `model_version` | yes | e.g. `v1.0` |
| `signal_type` | yes | `audio` \| `speech` \| `movement` |
| `prediction_state` | yes | `SUSPICIOUS` \| `EMERGENCY` \| `NORMAL` \| `OTHER` |
| `confidence` | no | 0–100 |
| `user_feedback` | yes | `CONFIRMED_EMERGENCY` \| `CONFIRMED_NORMAL` \| `CANCELLED` \| `TIMEOUT` \| `NONE` |
| `outcome` | yes | `NO_ALERT` \| `MANUAL_SOS_OPENED` \| `BLOCKED` \| `UNKNOWN` |
| `consent_granted` | yes | must be true |
| `consent_version` | yes | must match server constant |
| `features` | no | allowlisted numeric keys only |

## Stored columns (not accepted from client as gold)

| Column | Default / rule |
|--------|----------------|
| `candidate_category` | derived; never a gold label |
| `fp_fn_status` | `DISTRESS_CANDIDATE` / `HARD_NEGATIVE_CANDIDATE` / `UNREVIEWED` |
| `consent_status` | `GRANTED` (or `WITHDRAWN` after account deletion) |
| `review_status` | `UNREVIEWED` until human review |
| `reviewer_id` | null until review |
| `license_status` | `USER_CONSENT_OPT_IN` |
| `final_verdict` | null until review: `DISTRESS` \| `HARD_NEGATIVE` \| `REJECT` \| `AMBIGUOUS` |
| `gold_eligible` | **always false** on insert |
| `split_bucket` | null until promotion |
| `user_id` | set null on account deletion |

## Forbidden in this table

Raw WAV/PCM, precise lat/lon, phone numbers, transcripts, names.

## Gold CSV verdicts (after review only)

`DISTRESS`, `HARD_NEGATIVE`  
Never: `LIKELY_DISTRESS`, `UNREVIEWED`, `AMBIGUOUS`, `REJECT`, or unverified user-generated candidate category names.
