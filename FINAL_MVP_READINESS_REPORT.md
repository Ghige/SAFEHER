# Final MVP Readiness Report

**Date:** 2026-09-16  
**Scope:** Play Internal Testing readiness + continuous AI learning foundation  
**Kill-switch unchanged:** `AI_AUTO_SOS_ENABLED=false`, `DEMO_MODE=true`, confirm-first  
**DecisionContract:** not modified  
**Models:** not retrained; weights not modified  
**Emergency alerts:** not sent by this work

## Answers

### 1. Is SafeHer ready for Google Play Internal Testing?

**No.** Repository-side Play items that can be implemented in this tree are in place (account deletion, privacy/consent alignment, metadata-only AI feedback, CI workflow, signed local AAB/APK, health checks, production guards). External and listing requirements are not closed.

### 2. What exact blockers remain?

**BLOCKED**

- Live Twilio SMS OTP on a real handset  
- Meta WhatsApp **delivery** of approved templates to a staging recipient  
- Production Play **upload keystore identity** (local JKS signed the AAB; it is not proven to be the Play Console upload key)  
- On-device **TFLite** asset `yamnet_distress_quant.tflite` missing from `app/src/main/assets/`  
- Play Console: app listing, Data safety, content rating, testers, privacy policy URL  

**NOT VERIFIED**

- Production host `https://api.safeher.app/` DNS/TLS/`/ready`  
- Production Redis (`REQUIRE_REDIS_IN_PRODUCTION`)  
- PostgreSQL restore drill on a disposable DB (`pg_restore` / `restore_database.py --yes`)  
- GitHub Actions run of `.github/workflows/ci.yml`  
- Crashlytics console receiving a release crash/non-fatal  
- Physical phone: permission denials, manual SOS, Internal Testing install  
- Hosted privacy policy URL for Play  

**Pre-existing local test noise (not Play blockers, not faked)**

- `tests/test_ai_api.py::test_confidence_query` expects `confirm_30s` at fused 70; current SDE returns `fire_immediately` at 65. Contract was **not** changed to make the test pass.  
- `tests/test_auth.py::test_register` uses a fixed phone; 400 if that user already exists in the local DB.  
- `tests/test_helpers.py::test_haversine_known_distance` formula vs 20 km bound.  
- `tests/test_alerts.py` collection error (`movement_model.inference` missing).  
- `RollingConfidenceWindowTest.isSingleSpike_detectsOutlier` still failing (pre-existing window logic).  

### 3. Is the continuous AI data pipeline safely implemented?

**Yes, in-repo.** Predictions are stored as candidates only. `gold_eligible` is false on insert. WAV queue returns **410**. Retraining gate refuses to train (exit 2, `training_executed=false`). Live traffic through production is **NOT VERIFIED**.

### 4. What data is currently eligible for future training?

**None.** Gate counts: confirmed DISTRESS = 0, verified HARD_NEGATIVE = 0 (Stage 6 CSVs absent in this tree + real-world gold empty). Unreviewed / user-confirmed candidate labels are **not** eligible.

### 5. What still requires human review?

- All real-world `ai_feedback_events` (`UNREVIEWED`, including user-confirmed distress and cancel/false-positive candidates)  
- Remaining Stage 6 lab listening queue (when the CSV is present)  
- Any row with verdict `AMBIGUOUS` or `REJECT`  
- Dual second reviewer for any DISTRESS candidate  

### 6. What should we improve next?

1. Play Console Internal Testing: upload key, AAB, testers, Data safety, public privacy URL.  
2. Bundle licensed `yamnet_distress_quant.tflite`.  
3. Staging: live Twilio OTP + Meta non-emergency template probe.  
4. Restore drill + Redis on staging; point release `BASE_URL` at a live API.  
5. Device QA: permissions, manual SOS, confirm-first (AI must not auto-alert).  
6. After real opt-in usage: export candidates, dual-review, only then reconsider gold counts — **do not train yet**.

## Local verification this session

| Check | Status |
|-------|--------|
| Backend new tests (`test_ai_feedback`, `test_account_deletion`) + Stage 0/9/11/OTP suite | **VERIFIED** — 36 passed in the focused run; full `tests/` 113 passed / 3 failed (pre-existing) |
| `retraining_gate.py` | **VERIFIED** — training forbidden, exit 2 |
| Android unit tests added (classifier, feedback repo, delete account, settings) | **VERIFIED** |
| `AiMonitoringViewModelTest` after flow stubs | **VERIFIED** |
| `:app:assembleRelease` + `:app:bundleRelease` | **VERIFIED** — BUILD SUCCESSFUL; APK and AAB paths exist locally |
| Alembic 008 | **VERIFIED** on local Postgres (table created; upgrade made idempotent if table already exists) |
| Twilio live / Meta live / Play Console / physical phone | **NOT VERIFIED** |

## Repo changes (evidence-based)

- `DELETE /api/v1/users/me` + Settings delete-account UI  
- `POST /api/v1/ai/feedback` metadata-only; WAV queue 410  
- Privacy strings match “no raw upload”  
- Hourly dataset/feedback retention in scheduler; purge uses `recorded_at`  
- CI workflow, AAB docs, review + retraining-gate scripts  
- Confirm-first and auto-SOS flags unchanged  

**STOP. No model retraining was started.**
