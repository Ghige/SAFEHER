# Play Store MVP Readiness

**Date:** 2026-09-16  
**Kill-switch:** `AI_AUTO_SOS_ENABLED=false`, DecisionContract `DEMO_MODE=true`, confirm-first.  
**Rule:** External systems are not faked.

## Verdict

**SafeHer is NOT ready for Google Play Internal Testing.** Repository-side Play blockers that could be fixed in code are largely closed. Live OTP, WhatsApp delivery, production host, Redis, restore drill, Play Console listing, Play upload keystore identity, TFLite on-device assets, and physical-device SOS remain **BLOCKED** or **NOT VERIFIED**.

## Item status

| # | Item | Status | Evidence / manual verification required |
|---|------|--------|------------------------------------------|
| 1 | Backend production configuration | **VERIFIED** (repo) / **NOT VERIFIED** (live host) | Guards in `production_guards.py`, `.env.production.example`. Manual: boot API on a production-like host with `ENVIRONMENT=production`, `DEBUG=false`, non-default `SECRET_KEY`, Twilio OTP, Redis required; confirm process refuses unsafe config. |
| 2 | Real OTP + production guards | **VERIFIED** (code + unit/integration with mock) / **BLOCKED** (live SMS) | Twilio Verify implemented; mock forbidden in production/staging. Manual: send OTP to a real phone via Twilio Verify; enter code in app; confirm 123456 shortcut is rejected in staging/production. |
| 3 | WhatsApp / Meta + staging | **VERIFIED** (code, dry-run probe) / **BLOCKED** (live delivery) | Meta Cloud API service exists; emergency templates refused by design in probe. Manual: approved templates + `STAGING_WHATSAPP_RECIPIENT`; send a **non-emergency** staging template; confirm contacts receive it. Do not send real SOS. |
| 4 | Redis / rate limiting | **VERIFIED** (code + memory fallback in tests) / **NOT VERIFIED** (prod Redis) | Rate limits + `/ping/ready` Redis check. Manual: `REDIS_URL` on staging, `REQUIRE_REDIS_IN_PRODUCTION=true`, `GET /api/v1/ping/ready` shows `redis=ok`. |
| 5 | PostgreSQL backup + restore | **VERIFIED** (scripts exist) / **NOT VERIFIED** (restore drill) | `scripts/backup_database.py`, `scripts/restore_database.py`. Manual: `pg_dump` then restore to a **disposable** DB with `--yes`; record RPO/RTO. |
| 6 | Android release signing / AAB | **VERIFIED** (local signed APK+AAB this run) / **BLOCKED** (Play upload key identity) | This workstation: `assembleRelease` + `bundleRelease` **BUILD SUCCESSFUL**; `app/build/outputs/apk/release/app-release.apk` and `app/build/outputs/bundle/release/app-release.aab` exist. Manual: confirm the JKS is the Play Console **upload** key (not a throwaway local key), then upload AAB to Internal Testing. |
| 7 | Android permissions + failure handling | **VERIFIED** (repo) / **NOT VERIFIED** (device) | Settings permission screen, rationale, App Settings deep link, battery optimization card. Manual: deny mic/location; confirm monitoring/SOS explain and offer settings; grant and retry. |
| 8 | Privacy / consent / retention | **VERIFIED** (repo) | Privacy copy aligned with metadata-only feedback; Help improve AI off by default; consent version `privacy-v2-metadata-only`; hourly purge of expired WAV queue + unreviewed feedback retention. Manual: legal review of Play Data safety form + hosted privacy URL. |
| 9 | Account deletion | **VERIFIED** (repo + API tests) / **NOT VERIFIED** (Play Console form) | `DELETE /api/v1/users/me`; Settings → Delete account. Tests: `tests/test_account_deletion.py`. Manual: create account on staging, delete in app, confirm login 404 and Play Data safety “account deletion” URL. |
| 10 | Production logging / PII protection | **VERIFIED** (repo) | JSON logs, audit JSONL redaction (phone/lat/lon/transcript/audio). Manual: inspect one production log line has no phone/OTP/WAV. |
| 11 | Crash / error handling | **VERIFIED** (repo) / **NOT VERIFIED** (Crashlytics console) | Firebase Crashlytics tree on release. Manual: force a non-fatal on a release build; confirm in Firebase console. |
| 12 | Health / readiness | **VERIFIED** (repo + tests) | `/api/v1/ping/`, `/ready` (503 if DB down), `/metrics`. Manual: hit production `/ready`. |
| 13 | Release build configuration | **VERIFIED** (repo + this build) | Release `BASE_URL=https://api.safeher.app/`, `ENABLE_LOGGING=false`, `AI_AUTO_SOS_ENABLED=false`, minify on, cleartext disabled in main network config. Manual: `apktool`/bundletool dump confirms flags. |
| 14 | CI / release validation | **VERIFIED** (workflow file) / **NOT VERIFIED** (GitHub run) | `.github/workflows/ci.yml` (backend pytest + retraining gate + Android unit tests). Manual: push and confirm GitHub Actions green. |
| 15 | Play Store readiness documentation | **VERIFIED** (this file + related docs) | Still need Play Console store listing, Data safety, content rating, testers list. |

## Additional Play blockers (not in the 15-item list)

| Item | Status | Manual verification |
|------|--------|---------------------|
| On-device `yamnet_distress_quant.tflite` in assets | **VERIFIED** (git-tracked ~3.8 MB; Gradle `syncTfliteAsset`) | Rebuild AAB and confirm entry inside the bundle. |
| Production API `https://api.safeher.app/` live | **NOT VERIFIED** | DNS + TLS + `/ready`. |
| Physical phone Internal Testing install | **NOT VERIFIED** | Install from Play Internal track; manual SOS only. |
| Privacy policy public URL | **NOT VERIFIED** | Host the in-app policy at a stable HTTPS URL for Play. |

## AI safety (must remain)

- `AI_AUTO_SOS_ENABLED=false` in backend config, production example, Android debug **and** release `BuildConfig`.
- `DEMO_MODE=true` in `decision_contract.json`.
- Confirm-first 30s UI; cancel/timeout send **no** alert.
- DecisionContract thresholds **not** changed in this work.
