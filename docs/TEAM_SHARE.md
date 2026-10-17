# SafeHer team share — current app

This branch is a **clean shareable copy** of the unpublished SAFEHER app: Android, backend, SOS/UI overlay, physical-phone LAN debug, and later AI work.

It is **not** a zip of a laptop. Secrets, SDK paths, Wi-Fi IPs, audit logs, and movement training dumps are omitted on purpose.

| Field | Value |
|-------|-------|
| Repository | https://github.com/Ghige/SAFEHER |
| Branch | `team-share-current` |
| Android project | `safeher_android/` |
| Debug application ID | `com.safeher.app.debug` |
| Do not commit | `.env`, `local.properties`, `google-services.json`, Firebase Admin JSON, keystores, API keys |

SOS/UI device tests: `docs/SafeHer_Teammate_Setup_and_SOS_Test_Guide.md`

---

## Clone

```powershell
git clone https://github.com/Ghige/SAFEHER.git
cd SAFEHER
git fetch origin
git switch team-share-current
git status
git log -1 --oneline
```

If you already have a SAFEHER folder with local changes, **do not** reset it. Clone into a new directory.

Open Android Studio on **`safeher_android`**, not the monorepo root.

---

## Local files you must add (never commit)

1. Copy `safeher_android/local.properties.example` → `safeher_android/local.properties`
   - Set `sdk.dir` to **your** Android SDK
   - For a physical phone on the same Wi-Fi as the laptop:
     `DEBUG_API_BASE_URL=http://<YOUR_LAPTOP_LAN_IPV4>:8000/`
   - Leave `DEBUG_API_BASE_URL` unset for the Android emulator (`10.0.2.2`)
2. Ask the owner for a real `safeher_android/app/google-services.json` (private file, not Git). It must include `com.safeher.app.debug`.
3. Copy `safeher_backend/.env.example` → `safeher_backend/.env` and point it at **your** Postgres/Redis.

Do not copy another person’s `local.properties` or `.env`. Those contain machine paths and local IPs.

---

## Intentionally not in this branch

- `.env`, `local.properties`, `google-services.json`, Firebase Admin JSON, `*.jks`, `keystore.properties`
- `safeher_backend/app/ai/movement_model/data/` (~20k training files)
- `safeher_backend/data/audit_logs/`
- Python venvs, Gradle `build/`, APKs, datasets under `safeher_ai/data/`

---

## Physical phone register / login

1. Phone and laptop on the same Wi-Fi.
2. From `safeher_backend`: `python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
3. Allow inbound TCP 8000 in Windows Firewall.
4. Set `DEBUG_API_BASE_URL` to your laptop IPv4, then **Rebuild / Run** the debug app on the phone so `BuildConfig` picks up the URL.

This branch includes `DebugApiBaseUrl.kt`. Emulators ignore the LAN override and keep `http://10.0.2.2:8000/`.
