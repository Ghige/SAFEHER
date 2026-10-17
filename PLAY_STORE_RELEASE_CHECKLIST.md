# Play Store Release Checklist (Internal Testing)

Use this document while filling Play Console. Live Console clicks are **NOT VERIFIED** until you do them.

---

## A. Local package (repository)

- [x] Application ID: `com.safeher.app`
- [x] Version name: `2.0.0` / version code: `1`
- [x] `AI_AUTO_SOS_ENABLED=false` (Gradle + DecisionContract)
- [x] `DEMO_MODE=true` (Gradle BuildConfig + DecisionContract JSON)
- [x] Release BASE_URL `https://api.safeher.app/`
- [x] Cleartext disabled in main network config
- [x] Account deletion: Settings → Delete account → `DELETE /api/v1/users/me`
- [x] Help improve AI off by default; metadata-only; no WAV upload (HTTP 410)
- [x] Crashlytics plugin + `CrashlyticsTree` on release (`ENABLE_LOGGING=false`)
- [x] `yamnet_distress_quant.tflite` in `app/src/main/assets/` (~3.8 MB)
- [ ] Confirm upload-key SHA-256 in Play Console (**you**)
- [x] `bundleRelease` AAB on this machine — **PASS** `app/build/outputs/bundle/release/app-release.aab` (128,454,765 bytes, 2026-09-17 13:51 IST)

### Commands (Windows)

```bat
cd safeher_android
python scripts\verify_play_release.py
powershell -File scripts\print_upload_key_fingerprint.ps1
gradlew.bat :app:bundleRelease
python scripts\verify_play_release.py --aab app\build\outputs\bundle\release\app-release.aab
```

Upload file: `safeher_android/app/build/outputs/bundle/release/app-release.aab`

---

## B. Play Console listing copy (prepare locally)

**Title (max 50):** SafeHer — Women's Safety SOS

**Short description (max 80):**
One-tap SOS, live location sharing, and on-device AI prompts — you stay in control.

**Full description:**

SafeHer helps you call for help quickly and keep trusted people informed.

Manual SOS
• Trigger an emergency alert from the SOS button.
• Share live location with emergency contacts you choose.
• Cancel the alert when you are safe.

AI monitoring (optional, confirm-first)
• On-device audio distress detection can show a confirmation countdown.
• Automatic AI SOS is OFF. SafeHer will not send an emergency alert unless you confirm or use manual SOS.
• You can turn AI monitoring off in Settings.

Privacy
• Location is used for SOS, live sharing, and monitoring you enable.
• Microphone audio is processed on the device. Raw recordings are not uploaded.
• Optional “Help improve AI” (off by default) sends only metadata after you respond to a prompt — never phone numbers or precise GPS in that pipeline.
• Delete your account anytime in Settings.

SafeHer is an assistive safety tool. It does not replace police, ambulance, or local emergency numbers. Always call your local emergency number when you are in immediate danger.

---

## C. Data safety (Play form)

Declare **yes, we collect/share some data**. Map as follows:

| Data type | Collected? | Shared? | Required / optional | Purpose |
|-----------|------------|---------|---------------------|---------|
| Phone number | Yes (account) | No (except to your emergency contacts / WhatsApp when you trigger SOS) | Required for account | App functionality, account |
| Name | Yes | Shared with contacts/helpers only during SOS you start | Required | App functionality |
| Approximate / precise location | Yes, while SOS or live tracking or AI monitoring you enable | Yes, with emergency contacts via maps/track link during SOS | Optional until SOS | App functionality |
| Microphone | On-device only; **not uploaded** as audio | No | Optional (AI monitoring) | App functionality |
| Crash logs (Crashlytics) | Yes (release) | Shared with Google Firebase | Optional (diagnostics) | Analytics / crash reporting |
| Device token (FCM) | Yes | Google FCM | Required for push | App functionality |

**Security practices**
- Data encrypted in transit (HTTPS).
- Users can request deletion: in-app **Delete account** (`DELETE /api/v1/users/me`).
- Account deletion removes profile, contacts, alerts; anonymizes AI feedback `user_id`.

**Privacy policy URL:** **NOT VERIFIED** — host the in-app policy (`Settings → Privacy Policy` text) at a public HTTPS URL and paste it in Console.

**Account deletion URL (optional extra):** same privacy page, plus in-app path.

---

## D. Content rating (IARC questionnaire — suggested answers)

Complete the official questionnaire; do not skip. Suggested based on this app:

| Topic | Suggested |
|-------|-----------|
| Violence | No realistic violence; no user-vs-user combat |
| Sexual content | None |
| Language | Users may type names; no required profanity |
| Controlled substances | None |
| Gambling | None |
| User-generated content | Emergency contacts’ names; SOS messages to contacts — moderate UGC |
| Location sharing | Yes, user-initiated |
| Digital purchases | No (unless you add them later) |
| Target age | Adults; safety utility |

Expected rating band: typically **PEGI 3 / Everyone** or similar — **NOT VERIFIED** until IARC returns a certificate.

---

## E. Permissions justification (Play declarations)

| Permission | Why |
|------------|-----|
| `INTERNET` / `ACCESS_NETWORK_STATE` | Account, SOS, live location, FCM |
| `ACCESS_FINE_LOCATION` / `COARSE` | SOS pin and live sharing |
| `ACCESS_BACKGROUND_LOCATION` | Continue sharing after the screen is off during an active SOS |
| `RECORD_AUDIO` | Optional on-device distress detection |
| `FOREGROUND_SERVICE` + `LOCATION` / `MICROPHONE` | Ongoing SOS tracking and optional AI monitoring |
| `POST_NOTIFICATIONS` | SOS and monitoring notifications |
| `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` | Keep SOS/monitoring alive (user can refuse) |

Microphone and GPS hardware are `required="false"` so the app can install without them; SOS still needs location when used.

---

## F. Tester setup

1. Play Console → your app → **Testing → Internal testing**.  
2. Create a release; upload the AAB.  
3. Testers: email list **or** Google Group (must use the Google account on the phone).  
4. Copy the Internal testing opt-in URL; testers open it while logged into that account.  
5. Testers install from Play Store (Internal track), not a sideloaded APK.  
6. Testers must use **real Twilio OTP** once production API is live — there is **no** in-app 123456 shortcut in release.

Test script for testers (no real emergency):
1. Register / verify OTP.  
2. Add one emergency contact (use a tester-owned number).  
3. Open Settings → confirm AI auto behaviour copy; leave Help improve AI **off** unless they consent.  
4. Deny then grant microphone/location; confirm the app explains and offers system settings.  
5. Manual SOS: start countdown, **cancel before send** or send only to the tester contact.  
6. Delete account on a spare login and confirm they cannot log in.

**Do not** ask testers to rely on automatic AI SOS. It is disabled.

---

## G. Production API (you / ops — NOT VERIFIED here)

Release app will call `https://api.safeher.app/`. If the host is down, requests fail closed (timeout / HTTPS policy); the UI already surfaces offline/API errors. It will **not** fall back to `10.0.2.2` or HTTP.

Backend must boot with:
`ENVIRONMENT=production`, `DEBUG=false`, Twilio OTP, Redis, non-default `SECRET_KEY`, `AI_AUTO_SOS_ENABLED=false`.

---

## H. Session verification (this packaging run)

| Check | Result |
|-------|--------|
| `python scripts/verify_play_release.py --aab app-release.aab` | **PASS** |
| Upload key fingerprint script | **PASS** (passwords omitted). SHA-256 `53:B2:87:3C:4E:83:2A:3B:7B:FA:B5:41:CC:1C:3B:92:28:EE:1A:28:23:E6:92:E0:1C:BD:79:8B:32:5D:53:79`. `storeFile=release/safeher-upload-local.jks` — local smoke key, **not** Play identity |
| `:app:testDebugUnitTest` | **PASS** — 177 tests, 0 failures (includes `GoldenVectorParityTest`) |
| Backend pytest `safeher_backend/tests` | **PASS** — 121 passed |
| `:app:bundleRelease` | **PASS** — BUILD SUCCESSFUL; `app/build/outputs/bundle/release/app-release.aab` (128,454,765 bytes) |
| AAB contains TFLite + contract; no keystore/.env | **PASS** — `base/assets/yamnet_distress_quant.tflite` (3,827,768 bytes), `base/assets/decision_contract.json`; 269 entries |
| Release BuildConfig | **PASS** — `AI_AUTO_SOS_ENABLED=false`, `DEMO_MODE=true`, `BASE_URL=https://api.safeher.app/`, `ENABLE_LOGGING=false` |

### test_alerts.py leftover import

**Obsolete import**, not a production regression. `app.ai.movement_model.inference` / `is_jogging` do not exist; tests now use `movement_inference.predict_panic_movement`. DecisionContract was not changed.
