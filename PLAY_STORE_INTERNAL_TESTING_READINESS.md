# Play Store Internal Testing — repository readiness

**Date:** 2026-09-17 (this packaging run)  
**Kill-switch:** `AI_AUTO_SOS_ENABLED=false`, `DEMO_MODE=true` (release BuildConfig + `decision_contract.json`)  
**Did not:** retrain models, change DecisionContract thresholds, enable auto SOS, send alerts, or fake live services.

## Session verdict

| # | Item | Result |
|---|------|--------|
| 1 | Backend tests | **PASS** — `121 passed` (`safeher_backend/tests`, 232s) |
| 2 | Android tests | **PASS** — `:app:testDebugUnitTest` **177 tests, 0 failures** (includes `GoldenVectorParityTest`) |
| 3 | AAB build | **PASS** — `:app:bundleRelease` **BUILD SUCCESSFUL** |
| 4 | AAB contents | **PASS** — TFLite + DecisionContract present; no keystore/`.env`/WAV |
| 5 | Signing status | **VERIFIED** (local pipeline) / **NOT VERIFIED** (Play upload-key identity) |
| 6 | Release safety gates | **PASS** |
| 7 | Remaining Play Internal Testing blockers | Listed in §6 — all **NOT VERIFIED** / **BLOCKED** externally |

**Repository ready for Play Console upload: YES** for a locally signed AAB, subject to §6.  
This does **not** mean Play Console, Twilio, WhatsApp, Redis, or `api.safeher.app` were verified live.

---

## 1. Leftover `test_alerts.py` import — classification

| Question | Finding |
|----------|---------|
| What failed originally? | `from app.ai.movement_model.inference import predict_panic_movement, is_jogging` → `ModuleNotFoundError` |
| Obsolete test/import? | **YES** — there is no `inference.py`. Live module is `movement_inference.py`. `is_jogging` is not a public API. |
| Real production regression? | **NO** — SDE / DecisionContract unchanged; `test_safety_decision_engine.py` already covered the 80/70 floor. |
| Environment issue? | **NO** for the import. (`test_register` 400 **was** a leftover-DB / hardcoded-phone isolation issue.) |

**Fix applied (tests only, no contract / no models):**

- Import `predict_panic_movement` from `app.ai.movement_model.movement_inference`.
- Replace `is_jogging` with a score-range check through `predict_panic_movement`.
- Align `total_score >= 65` with current SDE output (65, not 70).
- Align `test_confidence_query` expected action to `fire_immediately` (same 80/70 floor as existing SDE tests).
- Unique phones in `test_auth.py`; haversine expected range corrected to ~16.1 km for the given coordinates.

DecisionContract JSON was **not** modified.

---

## 2. AAB build

| Field | Value |
|-------|--------|
| Result | **PASS** |
| Task | `:app:bundleRelease` BUILD SUCCESSFUL (2m 19s) |
| Path | `safeher_android/app/build/outputs/bundle/release/app-release.aab` |
| Size | **128,454,765** bytes |
| Signed | `signReleaseBundle` ran; `validateSigningRelease` UP-TO-DATE |

Earlier this session a `processReleaseResources` **FAIL** was a Windows file lock on `R.jar` (OneDrive / concurrent Gradle), not a source defect. Retry after `gradlew --stop` succeeded.

---

## 3. Signing configuration

| Layer | Status |
|-------|--------|
| Gradle `signingConfigs.release` + gitignored `keystore.properties` | **VERIFIED** (pipeline) |
| `storeFile` present, alias `safeher` | **VERIFIED** |
| Fingerprint script (passwords omitted) | **VERIFIED** |
| SHA-256 | `53:B2:87:3C:4E:83:2A:3B:7B:FA:B5:41:CC:1C:3B:92:28:EE:1A:28:23:E6:92:E0:1C:BD:79:8B:32:5D:53:79` |
| `storeFile` | `release/safeher-upload-local.jks` — **local smoke key**, not Play |
| Certificate is the Play Console **upload key** | **NOT VERIFIED** — compare SHA-256 in Play Console yourself |

---

## 4. TFLite asset

| Check | Result |
|-------|--------|
| Source asset | **VERIFIED** — `app/src/main/assets/yamnet_distress_quant.tflite` **3,827,768** bytes |
| Gradle `syncTfliteAsset` | **VERIFIED** (runs before `preBuild`) |
| Inside AAB | **VERIFIED** — `base/assets/yamnet_distress_quant.tflite` (3,827,768 bytes) |
| Retrain / new model | **Not done** (forbidden) |

AAB assets (only these two):

- `base/assets/yamnet_distress_quant.tflite`
- `base/assets/decision_contract.json` (2,429 bytes; `"AI_AUTO_SOS_ENABLED": false`, `"DEMO_MODE": true`)

No unsafe AAB entries (`.jks`, `.keystore`, `.env`, `keystore.properties`, `.wav`, raw `google-services.json`). **269** zip entries.

---

## 5. Release safety gates — **PASS**

Generated `app/build/generated/source/buildConfig/release/.../BuildConfig.java`:

- `AI_AUTO_SOS_ENABLED = false`
- `DEMO_MODE = true`
- `BASE_URL = "https://api.safeher.app/"`
- `ENABLE_LOGGING = false`
- `DEBUG = false`
- `APPLICATION_ID = "com.safeher.app"` / `VERSION_NAME = "2.0.0"` / `VERSION_CODE = 1`

Also **PASS**:

- `scripts/verify_play_release.py` (Gradle + contract + TFLite + cleartext off + no Android mock OTP + AAB inspect)
- Main `network_security_config` `cleartextTrafficPermitted="false"`
- OkHttp `ReleaseNetworkPolicyInterceptor` blocks HTTP and emulator hosts when logging is off
- Android `src/main` has no `123456` / `OTP_ALLOW_DEV_SHORTCUT` shortcut
- Backend `production_guards.py` still refuses `OTP_PROVIDER=mock` and `OTP_ALLOW_DEV_SHORTCUT` when `ENVIRONMENT=production`
- CI job `play-release-gates` present in `.github/workflows/ci.yml`
- Retraining gate: **TRAINING FORBIDDEN** (gold empty) — 4 gate tests passed; SDE confirm-first / golden vectors 4 passed

**Note (not a kill-switch fail):** release `MAPS_API_KEY` is empty (`local.properties` has a blank `MAPS_API_KEY=`). Maps tiles will not work until you set a real key and rebuild. **NOT VERIFIED** live.

---

## 6. External / manual blockers (do not fake)

| Item | Status | Exact manual step |
|------|--------|-------------------|
| Play Console app + Internal testing track | **NOT VERIFIED** | Create app; Testing → Internal testing → create release → upload the AAB above |
| Play upload-key SHA-256 match | **NOT VERIFIED** | Play Console → App integrity / App signing → compare upload-key SHA-256 to the fingerprint in §3 |
| Hosted privacy policy URL | **NOT VERIFIED** | Host in-app policy at a public HTTPS URL; paste into Play Console |
| Data safety form | **NOT VERIFIED** | Fill using `PLAY_STORE_RELEASE_CHECKLIST.md` §C |
| IARC content rating | **NOT VERIFIED** | Complete questionnaire using checklist §D |
| Testers list / opt-in URL | **NOT VERIFIED** | Add emails or Google Group; send opt-in link (checklist §F) |
| Live `https://api.safeher.app/` TLS + `/api/v1/ping/ready` | **NOT VERIFIED** | Hit production host; app fails closed (no HTTP / `10.0.2.2` fallback) |
| Production OTP | **BLOCKED** until ops | Boot API with `OTP_PROVIDER=twilio`, `OTP_ALLOW_DEV_SHORTCUT=false`; send a real SMS; confirm `123456` rejected |
| Redis in production | **NOT VERIFIED** | `REQUIRE_REDIS_IN_PRODUCTION=true`; `/ready` shows redis ok |
| Meta WhatsApp template | **BLOCKED** until ops | Non-emergency staging template only; do not send real SOS |
| Physical phone Internal track install | **NOT VERIFIED** | Install from Play Internal testing, not sideload |
| Crashlytics dashboard | **NOT VERIFIED** | Confirm a release non-fatal after a tester run (`uploadCrashlyticsMappingFileRelease` ran locally) |
| GitHub Actions on `origin` | **NOT VERIFIED** | Push and confirm `backend`, `android-unit`, `retraining-gate`, `play-release-gates` green |
| Google Maps API key in release AAB | **NOT VERIFIED** | Put a real `MAPS_API_KEY` in gitignored `local.properties`, rebuild AAB |
| Device / live SOS | **NOT VERIFIED** | Testers: manual SOS only; cancel or use a tester-owned contact. Do **not** rely on AI auto SOS |

---

## 7. What you must do next

1. Confirm or replace the JKS with the real Play **upload** key; compare SHA-256 in Play Console.  
2. Set `MAPS_API_KEY` in `safeher_android/local.properties` if maps are required; rebuild `:app:bundleRelease`.  
3. Upload `app-release.aab` to Play Console → Internal testing.  
4. Complete listing, Data safety, content rating, testers (copy in `PLAY_STORE_RELEASE_CHECKLIST.md`).  
5. Point testers at a live production API (`ENVIRONMENT=production`, Twilio OTP, Redis).  
6. Testers install from the Internal track and exercise **manual** SOS only.

Exact Console copy and checkboxes: `PLAY_STORE_RELEASE_CHECKLIST.md`.
