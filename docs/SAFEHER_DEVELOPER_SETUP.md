# SafeHer Developer Setup Guide

**Complete fresh-machine handover for cloning GitHub, configuring credentials, running the FastAPI backend in VS Code, running the Android app in Android Studio, and connecting the two.**

- Repository (verified remote): `https://github.com/Ghige/SAFEHER.git`
- Guide date: 2026-10-05
- Scope: documentation and configuration templates only. This guide does not redesign the app, AI, SOS, auth, APIs, models, or thresholds.
- Companion PDF: `docs/SAFEHER_DEVELOPER_SETUP.pdf` (regenerate with `python scripts/generate_developer_setup_pdf.py`)

**This Markdown file is the complete source of truth.** The PDF is the printable copy of the same guide.

---

## Status labels used in this guide

| Label | Meaning |
|-------|---------|
| VERIFIED | Confirmed from files in this repository |
| NOT VERIFIED | Could not be confirmed from the repository; needs a developer/environment check |
| REQUIRES USER CREDENTIAL | A teammate must provide a private file or secret |
| REQUIRES EXTERNAL ACCOUNT | Needs Firebase / Google / Meta / Twilio / Postgres access |
| REQUIRES MANUAL SETUP | Must be done on the machine; Git clone is not enough |

---

## 1. Project overview

SafeHer is a personal-safety platform:

- **Android app** (`safeher_android/`): Kotlin + Jetpack Compose, package `com.safeher.app`, versionName `2.0.0`, versionCode `1` (VERIFIED in `app/build.gradle.kts`).
- **Backend** (`safeher_backend/`): FastAPI app `app.main:app`, JWT auth, PostgreSQL, optional Redis, Firebase Admin, Meta WhatsApp Cloud API.
- **On-device AI**: quantized YAMNet TFLite `yamnet_distress_quant.tflite` bundled in the APK. Live path is confirm-first. `AI_AUTO_SOS_ENABLED=false` on Android and backend (VERIFIED). Manual SOS is separate.
- **Web track page** (`safeher_web/track/`): static emergency-contact map page. Backend can serve it at `/track/` when the monorepo layout is intact.
- **Training pipeline** (`safeher_ai/`): used to train/export TFLite. **Not required to run the app** if the production model files are present (they are tracked in Git; VERIFIED via `git ls-files`).

A developer cloning this repository should **not** retrain the model just to run the application.

---

## 2. Architecture overview (as implemented)

```
Physical phone or emulator
        |
        |  HTTP(S) to FastAPI
        v
safeher_android  ---- Retrofit ---->  safeher_backend (uvicorn :8000)
        |                                  |
        | TFLite in assets                 | PostgreSQL (required)
        | AudioMonitorService (mic FGS)    | Redis (optional in development)
        | LocationForegroundService        | Firebase Admin JSON (FCM)
        | Firebase (google-services.json)  | Meta WhatsApp (optional for local login tests)
        v
Confirm-first AI popup. Auto SOS is OFF.
```

**Debug API URL selection (VERIFIED in `DebugApiBaseUrl.kt` + `app/build.gradle.kts`):**

1. **Release builds** always use `https://api.safeher.app/`. `DEBUG_API_BASE_URL` is compiled as empty. Release forbids cleartext (`app/src/main/res/xml/network_security_config.xml`).
2. **Debug builds** with `DEBUG_API_BASE_URL` set in gitignored `local.properties`: that LAN URL is used for **all** debug devices, including emulators.
3. **Debug builds** with no override:
   - Emulator: `http://10.0.2.2:8000/` (special alias to the host machine).
   - Physical device: Gradle `debug` `BASE_URL` also falls back to `http://10.0.2.2:8000/` when the override is empty, which **does not work on a real phone**. For a physical phone you **must** set `DEBUG_API_BASE_URL` to your laptop LAN IP.

Debug network security allows cleartext HTTP (`app/src/debug/res/xml/network_security_config.xml`).

**CURRENT MACHINE EXAMPLE ONLY -- DO NOT USE AS A PERMANENT VALUE:**

```
http://192.168.1.17:8000/
```

Every developer must look up **their own** IPv4 on the Wi-Fi that the phone uses. DHCP addresses change.

---

## 3. Project structure (actual repository)

```
SAFEHER/
├── README.md                          # Points here and to the PDF
├── PRODUCTION_SETUP.md                # Production DNS / Firebase / WhatsApp checklist
├── TEAM_HANDOVER.pdf                  # Short older onboarding PDF
├── docs/
│   ├── SAFEHER_DEVELOPER_SETUP.md     # This file
│   └── SAFEHER_DEVELOPER_SETUP.pdf    # Printable copy
├── scripts/
│   ├── generate_developer_setup_pdf.py
│   └── generate_handover_pdf.py
├── .github/workflows/ci.yml           # Backend pytest on Python 3.11 + Postgres 16
├── safeher_android/                   # Android Studio project root
│   ├── app/                           # Application module
│   ├── gradle/wrapper/                # Gradle 9.3.0 wrapper
│   ├── local.properties.example
│   └── keystore.properties.example
├── safeher_backend/                   # FastAPI project (open this folder in VS Code)
│   ├── app/                           # Application code (main.py, api, models, services)
│   ├── alembic/versions/              # Migrations 001-008
│   ├── tests/
│   ├── requirements.txt
│   ├── .env.example
│   ├── .env.production.example
│   ├── docker-compose.p0.yml          # Optional Redis + optional Postgres
│   └── firebase-credentials.json.example
├── safeher_ai/                        # Training / export; models/final holds TFLite
├── safeher_web/                       # Static /track page
└── PLAY_STORE_*.md                    # Store checklists (not required to run locally)
```

| Folder | Role |
|--------|------|
| `safeher_android/` | Open **this** directory in Android Studio. |
| `safeher_backend/` | Open **this** directory in VS Code. Run uvicorn from here. |
| `safeher_ai/` | Train/export YAMNet. Not needed for day-to-day app run. |
| `safeher_web/` | Emergency contact track HTML. |
| `docs/` | This handover. |
| `.github/workflows/` | CI: backend tests with `OTP_PROVIDER=mock`. |

**NOT VERIFIED:** exact list of every untracked local-only file on a given developer machine.

---

## 4. KNOWN SETUP BLOCKERS

Do not treat a Git clone as a one-click install. The following must be completed or acknowledged.

1. **REQUIRES USER CREDENTIAL / REQUIRES EXTERNAL ACCOUNT:** Android Gradle Google Services plugin is applied (`libs.plugins.google.services`). A real `safeher_android/app/google-services.json` is **required** to sync/build. It is gitignored. Placeholders in `google-services.json.example` will **not** talk to Firebase. Obtain the file from a teammate or Firebase Console.
2. **REQUIRES USER CREDENTIAL:** Backend `.env` is gitignored. Copy `.env.example`. PostgreSQL must exist and match `DATABASE_URL`.
3. **REQUIRES MANUAL SETUP:** Android `local.properties` is gitignored. Android Studio usually writes `sdk.dir`. Physical-device testing also needs `DEBUG_API_BASE_URL`.
4. **REQUIRES EXTERNAL ACCOUNT (optional for login-only local tests):** Firebase Admin JSON at `FIREBASE_CREDENTIALS_PATH` is required for backend FCM. Login/register against Postgres can work without it; push notifications will not. **NOT VERIFIED** whether every backend boot path fails hard if the JSON is missing.
5. **REQUIRES MANUAL SETUP:** Physical phone and laptop must share Wi-Fi. Windows Firewall must allow inbound TCP 8000. Uvicorn must bind `0.0.0.0`.
6. **WhatsApp / Twilio / Maps:** Not required to register/login with mock OTP. Required for real SMS OTP, maps tiles, and emergency WhatsApp. **REQUIRES EXTERNAL ACCOUNT.**
7. **GitHub vs this working tree:** This documentation describes the workspace as of 2026-10-05, including `DEBUG_API_BASE_URL`. If a clone of `origin/main` is missing those files, Gradle/API URL behavior may differ. Check `git log` / `git status` after clone. See the final report from the authoring session.
8. **Clean-machine install:** This guide was **not** executed on a blank PC as an end-to-end proof. Commands were checked against repository files, not against a fresh OS image.
9. **Release signing:** `keystore.properties` and `*.jks` are gitignored. Debug builds do not need them. Play Store / release APK requires them (**REQUIRES USER CREDENTIAL**).
10. **Training datasets:** `safeher_ai/data/` is gitignored and **not** required to run inference.

---

## 5. Prerequisites (install first)

### REQUIRED

| Tool | Version / notes | Status |
|------|-----------------|--------|
| Git | Any current Git for Windows | VERIFIED needed to clone |
| Python | **3.11.x** (comment in `safeher_backend/requirements.txt`; CI uses `3.11`) | VERIFIED |
| PostgreSQL | 16 used in CI and `docker-compose.p0.yml`. Other 14+ versions **NOT VERIFIED** | VERIFIED for 16 in CI/compose |
| Android Studio | README previously said Ladybug+. **Exact installer version NOT VERIFIED** | NOT VERIFIED |
| JDK | Android `compileOptions` / `kotlinOptions` target **JVM 17**. Android Studio bundled JBR 21 can compile that target. | VERIFIED target 17 |
| Android SDK | Platform **35** (`compileSdk = 35`, `targetSdk = 35`), `minSdk = 26` | VERIFIED |
| Gradle | Wrapper **9.3.0** (`gradle-wrapper.properties`) | VERIFIED |
| Android Gradle Plugin | **8.7.3** (`gradle/libs.versions.toml`) | VERIFIED |
| Kotlin | **2.0.21** | VERIFIED |
| GitHub access | Clone `https://github.com/Ghige/SAFEHER.git` (private access may be required) | REQUIRES EXTERNAL ACCOUNT |

### OPTIONAL

| Tool | Why |
|------|-----|
| Redis 7 | Dead-man switch + rate limits. Dev falls back to in-memory if Redis is down (`redis_service.py`). Production/staging refuse that fallback when `REQUIRE_REDIS_IN_PRODUCTION=true`. |
| Docker Desktop | `safeher_backend/docker-compose.p0.yml` can start Redis and (profile `with-db`) Postgres. |
| Meta WhatsApp Cloud API | Emergency contact messages. |
| Twilio Verify | Real SMS OTP (`OTP_PROVIDER=twilio`). |
| Google Maps API key | Map tiles. Empty `MAPS_API_KEY` still builds. |
| VS Code Python extension | Convenience only. |

### DEVELOPMENT ONLY

- `OTP_PROVIDER=mock` and `OTP_ALLOW_DEV_SHORTCUT=true` (defaults in `.env.example`).
- Debug cleartext HTTP to LAN / `10.0.2.2`.
- `ENVIRONMENT=development`, `DEBUG=true`.

### PRODUCTION ONLY (do not use for this local guide)

- `ENVIRONMENT=production`, `OTP_PROVIDER=twilio`, `OTP_ALLOW_DEV_SHORTCUT=false`.
- Release base URL `https://api.safeher.app/`.
- Redis required. See `PRODUCTION_SETUP.md` and `.env.production.example`.

**SDK components (VERIFIED as required by Gradle; exact SDK Manager checkbox names NOT VERIFIED):**

- Android SDK Platform 35
- Android SDK Build-Tools (version not pinned in Gradle; Android Studio installs a default)
- Android SDK Platform-Tools (adb)
- Google Play services / Google APIs as pulled by Gradle dependencies
- Emulator image: **x86_64 or ARM system image with Google APIs, API 26+** (API 35 recommended). Exact AVD name NOT VERIFIED.

---

## 6. Developer credential checklist

### REQUIRED before a useful local run

- [ ] GitHub access to this repository
- [ ] Python 3.11
- [ ] PostgreSQL running with a database matching `DATABASE_URL`
- [ ] Backend `.env` copied from `.env.example` (placeholders replaced)
- [ ] `SECRET_KEY` changed from the example string for anything beyond throwaway local use
- [ ] Android Studio + JDK 17-capable toolchain
- [ ] Android SDK Platform 35
- [ ] `safeher_android/local.properties` with valid `sdk.dir` (Studio usually creates this)
- [ ] Real `safeher_android/app/google-services.json` (not the `.example` file)
- [ ] Emulator **or** physical Android 8.0+ (API 26+) device
- [ ] Runtime grants: microphone, notifications, location (when using SOS/maps/AI)

### REQUIRED for physical-phone + backend

- [ ] Laptop and phone on the **same Wi-Fi**
- [ ] Laptop LAN IPv4 (not 10.0.2.2, not 127.0.0.1)
- [ ] `DEBUG_API_BASE_URL=http://<YOUR_LAN_IP>:8000/` in `local.properties`
- [ ] Uvicorn `--host 0.0.0.0 --port 8000`
- [ ] Windows Firewall inbound TCP 8000 allowed

### REQUIRED for FCM / backend push

- [ ] Firebase project access
- [ ] Backend `firebase-credentials.json` (Admin SDK) and `FIREBASE_CREDENTIALS_PATH`

### OPTIONAL

- [ ] Redis
- [ ] `MAPS_API_KEY`
- [ ] Meta WhatsApp tokens
- [ ] Twilio Verify credentials
- [ ] Release keystore (`keystore.properties` + JKS)

### PRODUCTION ONLY (not this guide)

- [ ] Production `.env` from a secret store
- [ ] Approved WhatsApp templates
- [ ] DNS for `api.safeher.app` / `safeher.app`

---

## 7. SAFE SECURITY RULES

### NEVER COMMIT

- Passwords and database URLs with real passwords
- API keys (OpenAI, Google, Maps, Firebase client keys, Meta, Twilio)
- Private keys and PEM files
- Firebase Admin / service-account JSON (`firebase-credentials.json`, `*adminsdk*.json`, `*service-account*.json`)
- Production database credentials
- JWT `SECRET_KEY` values
- Filled `.env` files
- `local.properties` (machine SDK path + optional LAN URL + Maps key)
- `google-services.json` (contains a Google API key; gitignored)
- Signing keystores (`*.jks`, `*.keystore`) and `keystore.properties`
- User recordings / `safeher_ai/data/` datasets

Root `.gitignore` already ignores `.env`, `local.properties`, `google-services.json`, `firebase-credentials.json`, venvs, `build/`, and `safeher_ai/data/`.

### DO COMMIT (templates only)

- `safeher_backend/.env.example`
- `safeher_backend/.env.production.example`
- `safeher_backend/firebase-credentials.json.example`
- `safeher_android/local.properties.example`
- `safeher_android/keystore.properties.example`
- `safeher_android/app/google-services.json.example`

Never paste real secret values into this Markdown, the PDF, README, or chat logs.

---

## 8. Configuration files table

| File | Required? | Used by | Where to put it | How to obtain it | Commit to Git? |
|------|-----------|---------|-----------------|------------------|----------------|
| `safeher_backend/.env` | Yes (runtime) | Backend | `safeher_backend/.env` | Copy `.env.example`; fill locally | **NO** |
| `safeher_backend/.env.example` | Template | Humans / this guide | Already in repo | In Git | YES |
| `safeher_backend/.env.production.example` | Template | Production ops | Already in repo | In Git | YES |
| `safeher_backend/firebase-credentials.json` | Required for FCM; optional for login-only | Firebase Admin | Path in `FIREBASE_CREDENTIALS_PATH` (default `./firebase-credentials.json`) | Firebase Console: Project settings > Service accounts > Generate new private key | **NO** |
| `safeher_backend/firebase-credentials.json.example` | Template | Humans | Already in repo | In Git | YES |
| `safeher_android/local.properties` | Yes | Gradle | `safeher_android/local.properties` | Copy example; Studio writes `sdk.dir` | **NO** |
| `safeher_android/local.properties.example` | Template | Humans | Already in repo | In Git | YES |
| `safeher_android/app/google-services.json` | Yes (Gradle Google Services + FCM) | Android | `safeher_android/app/google-services.json` | Firebase Console download, or teammate via a private channel | **NO** |
| `safeher_android/app/google-services.json.example` | Template | Humans | Already in repo | In Git | YES |
| `safeher_android/keystore.properties` | Release only | Gradle signing | `safeher_android/keystore.properties` | Copy example; private keystore | **NO** |
| `yamnet_distress_quant.tflite` | Yes (on-device AI) | Android assets / Gradle `syncTfliteAsset` | Tracked copies under assets, `safeher_ai/models/final/`, `safeher_backend/app/ai/audio_model/` | Already in Git | YES (model binary, not a secret) |
| `yamnet_distress.tflite` | Optional (non-quant) | Training artifacts | `safeher_ai/models/final/` | In Git | YES |
| Alembic versions `001`-`008` | Yes | DB schema | `safeher_backend/alembic/versions/` | In Git | YES |
| `safeher_backend/docker-compose.p0.yml` | Optional | Redis / Postgres | `safeher_backend/` | In Git | YES |
| CI secrets | CI only | GitHub Actions | Workflow env in `.github/workflows/ci.yml` uses dummy `SECRET_KEY` and test DB | In Git (dummy values) | YES (dummy only) |

`google-services.json` is **not** safe to publish on GitHub in this project: it is gitignored and contains a restricted Google API key. Share it privately. The `.example` file is placeholders only.

Observed local Firebase project id (from a private local file, not committed): `safeher-4521a`. Teammates need Console access to that project **or** their own Firebase project with matching Android application ids. **REQUIRES EXTERNAL ACCOUNT.**

`oauth_client` arrays in the observed local `google-services.json` were empty. SHA-1 / SHA-256 for Google Sign-In are **NOT VERIFIED** as required for the current phone+password/OTP login path.

---

## 9. Backend setup (VS Code)

### 9.1 Open the project

1. Install VS Code.
2. File > Open Folder > select `safeher_backend` (not the monorepo root, unless you prefer a multi-root workspace).
3. Select Python 3.11 as the interpreter after the venv exists.

### 9.2 Virtual environment (Windows PowerShell)

Commands below match README / CI style. README uses `.venv` inside `safeher_backend`. Either `.venv` or `venv311` is fine; this guide uses `.venv` as the documented default.

```powershell
cd safeher_backend
py -3.11 -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If `py -3.11` is missing, install Python 3.11 from python.org and retry. Wrong major versions are a common `ModuleNotFoundError` / wheel source.

`requirements.txt` pins FastAPI `0.115.6`, uvicorn `0.34.0`, SQLAlchemy `2.0.36`, Alembic `1.14.0`, pytest `8.3.4`, firebase-admin, redis, psycopg2-binary, numpy `1.26.4`.

### 9.3 Configure `.env`

```powershell
copy .env.example .env
```

Then edit `.env`. **Do not invent production passwords.** Placeholders from `.env.example`:

```
DATABASE_URL=postgresql://postgres:password@localhost:5432/safeher_db
SECRET_KEY=change-this-to-a-random-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REDIS_URL=redis://localhost:6379
ENVIRONMENT=development
DEBUG=true
OTP_PROVIDER=mock
OTP_ALLOW_DEV_SHORTCUT=true
AI_AUTO_SOS_ENABLED=false
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
CORS_ALLOWED_ORIGINS=
```

- `DATABASE_URL` user/password/db **must match the Postgres role you actually created**. The example uses user `postgres`, password `password`, db `safeher_db`, host `localhost`, port `5432`. Those are **template values**, not a guarantee your machine uses them.
- Optional Docker compose Postgres uses user `safeher`, password `safeher_dev_only_change_me`, db `safeher_db` (see section 10).
- Development CORS is `*` when `ENVIRONMENT=development` (VERIFIED in `app/main.py`).
- `TrustedHostMiddleware` is **off** unless production-like (`_PROD`).

### 9.4 Firebase Admin (backend)

1. Firebase Console > Project settings > Service accounts > Generate new private key.
2. Save as `safeher_backend/firebase-credentials.json` (gitignored).
3. Leave `FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json` or set an absolute path.
4. Do **not** commit this file. The `.example` file is a shape-only placeholder.

### 9.5 Start the API

**Local-only testing** (browser/Swagger on the same PC; Android emulator can still use `10.0.2.2` which maps to the host). Default uvicorn bind without `--host` is 127.0.0.1:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

**Physical Android device testing** (phone must reach the laptop). Bind all interfaces:

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

README also documents:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

(equivalent if the venv Scripts directory is on PATH).

**Verify Swagger**

- Open `http://127.0.0.1:8000/docs`
- Liveness: `GET http://127.0.0.1:8000/api/v1/ping/` should return `"status": "ok"` and `"ai_auto_sos_enabled": false`
- Readiness: `GET http://127.0.0.1:8000/api/v1/ping/ready` requires PostgreSQL (`database=ok` or HTTP 503)

Do **not** send a real emergency alert while verifying setup.

---

## 10. Database setup (PostgreSQL)

Alembic reads `DATABASE_URL` from settings (`alembic/env.py`). `alembic.ini` has an empty `sqlalchemy.url`; do not put passwords there.

There is **no** automatic user seed. Register a user through the app or `POST /api/v1/auth/register`. Model-version seed exists only for AI dataset admin endpoints (`ensure_seed_model_versions`) and is **not** required for login.

### Option A -- local PostgreSQL (manual)

Install PostgreSQL 16 (version 16 VERIFIED in CI). In `psql` or pgAdmin, create a database. Example using the **template** credentials from `.env.example` (replace if your install uses a different postgres password):

```sql
CREATE DATABASE safeher_db;
```

If you create a dedicated user (optional; **do not invent production passwords**):

```sql
CREATE USER safeher WITH PASSWORD '<YOUR_PASSWORD>';
GRANT ALL PRIVILEGES ON DATABASE safeher_db TO safeher;
```

Then set:

```
DATABASE_URL=postgresql://<YOUR_USER>:<YOUR_PASSWORD>@localhost:5432/safeher_db
```

Windows default superuser is often `postgres`. The password is whatever you chose at install time (**REQUIRES MANUAL SETUP**).

### Option B -- Docker (optional)

From `safeher_backend`:

```powershell
docker compose -f docker-compose.p0.yml --profile with-db up -d
```

Compose values (VERIFIED in `docker-compose.p0.yml`):

- user: `safeher`
- password: `safeher_dev_only_change_me` (dev-only sample in compose; change if you expose the port)
- database: `safeher_db`
- port: `5432`

Matching URL:

```
DATABASE_URL=postgresql://safeher:safeher_dev_only_change_me@localhost:5432/safeher_db
```

Redis-only:

```powershell
docker compose -f docker-compose.p0.yml up -d
```

### Migrations (required)

From `safeher_backend` with venv active and `.env` loaded:

```powershell
alembic upgrade head
```

Tracked revisions (VERIFIED filenames):

| Revision file | Purpose |
|---------------|---------|
| `001_create_users.py` | users |
| `002_create_alerts.py` | alerts / contacts related schema |
| `003_create_helpers.py` | helpers |
| `004_add_user_is_verified.py` | `is_verified` |
| `005_add_user_fcm_token.py` | FCM token column |
| `006_ai_dataset_and_model_versions.py` | AI dataset tables |
| `007_uniqueness_alerts_contacts.py` | uniqueness constraints |
| `008_ai_feedback_events.py` | AI feedback events |

Exact live column lists: **NOT VERIFIED** in this guide beyond migration filenames; inspect the migration files if you need a schema dump.

CI uses database `safeher_test` with user/password `safeher` -- that is for GitHub Actions only.

---

## 11. Firebase / Google configuration

### Android application ids (VERIFIED)

| Variant | Application id |
|---------|----------------|
| Release | `com.safeher.app` |
| Debug | `com.safeher.app.debug` (`applicationIdSuffix = ".debug"`) |

Register **both** Android apps in Firebase if you run debug installs.

### `google-services.json`

- **Required** at `safeher_android/app/google-services.json`
- Used by the Google Services Gradle plugin and Firebase (FCM, Crashlytics plugin is applied)
- **Do not commit**
- Download from Firebase Console for this project, or receive it through a private team channel
- Copying `google-services.json.example` to `google-services.json` is **not** sufficient for a working Firebase connection

### Backend Admin SDK

- File: `firebase-credentials.json` (private key -- **never commit**)
- Env: `FIREBASE_CREDENTIALS_PATH`
- Needed for server-side FCM

### Auth in this codebase

App login is **phone + password** via FastAPI (`/api/v1/auth/register`, `/login`, `/send-otp`, `/verify-otp`). It is not Firebase Auth email/password. Firebase on Android is used for messaging (and Crashlytics), not as the primary user table.

### SHA-1 / SHA-256

**NOT VERIFIED** as required for current OTP/password login. Add debug/release SHA fingerprints in Firebase if you later enable Google Sign-In or restricted API keys that demand them.

### Google Maps

`MAPS_API_KEY` in `local.properties` is injected as `BuildConfig.MAPS_API_KEY` and a manifest placeholder. Empty key: app still builds; maps tiles fail.

---

## 12. Android setup (Android Studio)

### 12.1 Open the project

Open the folder **`safeher_android`**, not the monorepo root (unless you add it as a module later). Wait for Gradle sync.

### 12.2 `local.properties`

```powershell
cd safeher_android
copy local.properties.example local.properties
```

Set:

```
sdk.dir=C:\\Users\\<YourUser>\\AppData\\Local\\Android\\Sdk
MAPS_API_KEY=<YOUR_KEY_OR_LEAVE_EMPTY>
```

Android Studio usually overwrites/creates `sdk.dir` automatically.

**Physical device extra line:**

```
DEBUG_API_BASE_URL=http://<YOUR_LAPTOP_LAN_IPV4>:8000/
```

**CURRENT MACHINE EXAMPLE ONLY -- DO NOT USE AS A PERMANENT VALUE:** `http://192.168.1.17:8000/`

Find your IPv4 (Windows PowerShell):

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.PrefixOrigin -ne 'WellKnown' } | Format-Table IPAddress, InterfaceAlias
```

Use the Wi-Fi adapter address (often `192.168.x.x` or `10.x.x.x`). Do **not** use `127.0.0.1` (that is the phone itself). Do **not** use `10.0.2.2` on a physical phone (that alias exists only inside the Android emulator).

After changing `DEBUG_API_BASE_URL`, **Rebuild** the app so `BuildConfig` regenerates.

### 12.3 `google-services.json`

Place the real file at `safeher_android/app/google-services.json`. Gradle sync fails or Firebase init fails without it.

### 12.4 Sync / build

In Android Studio: File > Sync Project with Gradle Files, then Run.

CLI (from `safeher_android`, JDK on PATH):

```powershell
.\gradlew.bat assembleDebug
```

Unit tests:

```powershell
.\gradlew.bat testDebugUnitTest
```

`JAVA_HOME` should point at JDK 17+ (Android Studio JBR is acceptable). **NOT VERIFIED** that every machine already has `JAVA_HOME` set.

### 12.5 Permissions (VERIFIED in `AndroidManifest.xml`)

Install-time / declared:

- `INTERNET`, `ACCESS_NETWORK_STATE`
- `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`, `ACCESS_BACKGROUND_LOCATION`
- `RECORD_AUDIO`
- `POST_NOTIFICATIONS`
- `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_LOCATION`, `FOREGROUND_SERVICE_MICROPHONE`
- `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`

Runtime (grant on device): microphone, notifications (API 33+), location (and background location if the OS prompts for SOS tracking).

Foreground services:

- `LocationForegroundService` -- `foregroundServiceType=location`
- `AudioMonitorService` -- `foregroundServiceType=microphone`

### 12.6 Emulator vs physical device

See sections 16--18 of the run procedure.

USB debugging on a physical phone: Settings > Developer options > USB debugging. Authorize the PC RSA prompt. `adb devices` should show `device`, not `unauthorized` or `offline`.

---

## 13. AI / SafeHer model setup (as implemented)

| Item | Value | Status |
|------|-------|--------|
| Production on-device model | `yamnet_distress_quant.tflite` | VERIFIED |
| Android asset name | `AiModelAssets.AUDIO_MODEL` | VERIFIED |
| Format | TensorFlow Lite (quantized) | VERIFIED |
| Bundled in APK? | Yes. Gradle copies into `app/src/main/assets/` if missing (`syncTfliteAsset`) | VERIFIED |
| Downloaded at runtime? | No | VERIFIED |
| Retrain required to run app? | **No** | VERIFIED |
| Training dataset required for inference? | **No** (`safeher_ai/data/` gitignored) | VERIFIED |
| Sample rate / window | 16 kHz mono, 1 second / 16000 samples (implementation in audio engine) | VERIFIED in Stage 3 audio pipeline comments/code |
| Movement TFLite | **Not** on-device (`movement_model.tflite` not a required RC1 asset) | VERIFIED |
| Speech sklearn | **Not** on-device; phrase catalog + optional Android SpeechRecognizer | VERIFIED |
| Auto SOS | `AI_AUTO_SOS_ENABLED=false` (Android BuildConfig + backend settings) | VERIFIED |
| Confirm-first | Backend `CONFIRMATION_WINDOW_SECONDS=30`; Android confirm-first popup | VERIFIED window setting; UI path exists in app services |
| Backend copy of model | `safeher_backend/app/ai/audio_model/yamnet_distress_quant.tflite` | VERIFIED tracked |
| Non-quant sibling | `safeher_ai/models/final/yamnet_distress.tflite` | VERIFIED tracked |

Python training extras (`safeher_ai/requirements_training.txt`) are **optional**. Backend `numpy` is pinned for server-side helpers; on-device inference uses Android TensorFlow Lite `2.16.1` (`libs.versions.toml`).

Do **not** replace the production TFLite as part of setup.

Logcat filter for live AI (if Stage 3A is present in the checked-out code): tag `SAFEHER_AI`. If that tag is absent on an older commit, use `AudioMonitorService` / `TfliteAudioInferenceEngine`.

---

## 14. Complete run procedure (fresh machine)

### STEP 1 -- Install prerequisites

Install Git, Python 3.11, PostgreSQL 16, Android Studio (SDK 35). Optional: Redis, Docker Desktop.

### STEP 2 -- Clone repository

```powershell
git clone https://github.com/Ghige/SAFEHER.git
cd SAFEHER
```

If the repository is private, authenticate with GitHub (browser, PAT, or SSH). **NOT VERIFIED** which auth method your org requires.

### STEP 3 -- Open backend in VS Code

Open folder `SAFEHER\safeher_backend`.

### STEP 4 -- Create Python virtual environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\activate
```

### STEP 5 -- Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### STEP 6 -- Configure `.env`

```powershell
copy .env.example .env
```

Set `DATABASE_URL` and `SECRET_KEY`. Keep `AI_AUTO_SOS_ENABLED=false`, `OTP_PROVIDER=mock`, `OTP_ALLOW_DEV_SHORTCUT=true` for local mock OTP.

### STEP 7 -- Configure PostgreSQL

Create database `safeher_db` (or match your URL). Then:

```powershell
alembic upgrade head
```

### STEP 8 -- Configure Firebase / backend credentials

Place Admin SDK JSON if you need FCM. Skip only if you accept no push from backend.

### STEP 9 -- Start backend

Emulator / same-PC:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

Physical phone:

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### STEP 10 -- Verify Swagger

Browse `http://127.0.0.1:8000/docs` and `http://127.0.0.1:8000/api/v1/ping/`.

### STEP 11 -- Open Android project in Android Studio

Open `SAFEHER\safeher_android`.

### STEP 12 -- Configure `local.properties`

Copy the example; confirm `sdk.dir`. For a physical phone, set `DEBUG_API_BASE_URL` to **your** LAN URL.

### STEP 13 -- Configure `google-services.json`

Place the real file in `safeher_android/app/`.

### STEP 14 -- Sync Gradle

Android Studio: Sync Project with Gradle Files.

### STEP 15 -- Build Android project

Run `app` (debug) or `.\gradlew.bat assembleDebug`.

### STEP 16 -- Run emulator

Create an AVD (API 26+, Google APIs). Cold boot. Run the `app` configuration. Default debug URL `http://10.0.2.2:8000/` reaches uvicorn on the PC **if** `DEBUG_API_BASE_URL` is unset. If you set a LAN override, the emulator will also use that LAN IP; the PC must listen on `0.0.0.0`.

### STEP 17 -- Run physical Android device

Enable USB debugging, accept RSA, `adb devices` = `device`. Install the **debug** variant (`com.safeher.app.debug`).

### STEP 18 -- Configure physical-device backend URL

1. Discover LAN IPv4 on the laptop.
2. Set `DEBUG_API_BASE_URL=http://<LAN>:8000/` (trailing slash recommended; Gradle normalizes).
3. Rebuild/reinstall.
4. Start uvicorn with `--host 0.0.0.0 --port 8000`.
5. Confirm phone Wi-Fi (not mobile data only, unless you have a verified routing path -- **NOT VERIFIED** for cellular).

### STEP 19 -- Test registration / login / profile

1. Register with a phone number + password (API `POST /api/v1/auth/register`).
2. Send OTP, then verify. With mock + shortcut, OTP `123456` is accepted (`otp_service.py`, `OTP_ALLOW_DEV_SHORTCUT=true`).
3. Login (`POST /api/v1/auth/login`).
4. Open Profile in the app.

Password rules: follow in-app validation (unit tests mention length checks). Exact UX copy: **NOT VERIFIED** beyond code.

### STEP 20 -- Test SafeHer AI

1. Grant microphone + notifications.
2. Start AI / audio monitoring in the app (AudioMonitorService).
3. Confirm the foreground notification appears.
4. You should **not** get an automatic SOS (`AI_AUTO_SOS_ENABLED=false`). Confirm-first popup may appear on sustained distress; dismiss/confirm as designed.
5. Do not play loud distress audio in public without warning.

### STEP 21 -- Test SOS flow

1. Grant location.
2. Add at least one emergency contact if the UI requires it for dispatch.
3. Use **manual SOS** if you need to exercise `/api/v1/alerts/trigger`.
4. Real WhatsApp delivery needs Meta credentials -- otherwise expect backend logs without a live message. **Do not send a real emergency to real contacts.**

### STEP 22 -- Troubleshooting

See section 15.

---

## 15. Troubleshooting

### Backend / Python

| Symptom | What to check |
|---------|----------------|
| `ModuleNotFoundError` | Venv not activated; `pip install -r requirements.txt` not run; opened wrong folder |
| Wrong Python | `python --version` must be 3.11.x |
| pip / wheel failure | Use 3.11, upgrade pip, avoid 3.13 unless **NOT VERIFIED** |
| Postgres connection failure | Service running; `DATABASE_URL` user/password/db/port; `alembic upgrade head`; `ping/ready` |
| Firebase Admin errors | Missing JSON or bad `FIREBASE_CREDENTIALS_PATH` |
| Port 8000 in use | Another uvicorn; change port and URLs together |

### Android / Gradle

| Symptom | What to check |
|---------|----------------|
| Gradle sync failure | Network for Maven; JDK; wrapper 9.3.0 download |
| Missing `google-services.json` | File must be exactly `app/google-services.json` |
| Android SDK missing | SDK Manager: Platform 35 |
| `sdk.dir` missing | `local.properties` |
| TFLite missing | Tracked model should copy via `syncTfliteAsset`; check assets |

### Device / network

| Symptom | What to check |
|---------|----------------|
| Device not detected | USB cable, drivers, `adb kill-server` then `adb devices` |
| `unauthorized` | Unlock phone, accept debugging RSA |
| `offline` | Replug, revoke USB debugging authorizations |
| Network error in app | Backend down; wrong base URL; cleartext blocked (should not happen on debug) |
| Emulator cannot reach API | Use `10.0.2.2` **or** LAN override + `0.0.0.0`; not `127.0.0.1` inside emulator unless that is intended |
| Phone cannot reach API | **10.0.2.2 does not work on a physical phone.** Use laptop LAN IP. Phone and PC on same Wi-Fi. Uvicorn `0.0.0.0`. Windows Firewall inbound 8000. Disable guest-Wi-Fi AP isolation if the AP blocks client-to-client. |
| Windows Firewall | Allow Python/uvicorn TCP 8000 inbound on Private networks |

**10.0.2.2** = emulator alias for the host loopback.

**Physical phone** = developer laptop LAN IPv4.

### Permissions / AI

| Symptom | What to check |
|---------|----------------|
| No mic capture | `RECORD_AUDIO` denied; OEM permission drawer |
| No notification | `POST_NOTIFICATIONS` on API 33+ |
| FGS killed | Battery optimization; `FOREGROUND_SERVICE_MICROPHONE` |
| TFLite load failure | Asset missing; Logcat `TfliteAudioInferenceEngine` |
| AI never auto-alerts | Expected: auto SOS is **off** |

Logcat filter examples:

```
package:com.safeher.app.debug
tag:SAFEHER_AI
tag:okhttp.OkHttpClient
```

---

## 16. Auth, OTP, and CORS (local)

- Register/login: FastAPI JWT (`SECRET_KEY`, `ALGORITHM=HS256`).
- Mock OTP: stored code **or** `123456` when `OTP_ALLOW_DEV_SHORTCUT=true`.
- Production/staging **refuse** mock OTP (`production_guards.py`).
- Dev CORS: allow all origins.
- Do not enable `AI_AUTO_SOS_ENABLED` for setup.

---

## 17. Tests you can run locally

Backend (venv, Postgres not always required for every test -- many tests use the app with env from CI; **NOT VERIFIED** that every test passes without Postgres on every machine):

```powershell
cd safeher_backend
.\.venv\Scripts\activate
pytest
```

CI equivalent env is in `.github/workflows/ci.yml` (`DATABASE_URL` to `safeher_test`, `OTP_PROVIDER=mock`, `AI_AUTO_SOS_ENABLED=false`).

Android:

```powershell
cd safeher_android
.\gradlew.bat testDebugUnitTest
```

This guide does **not** claim a clean-machine installation was tested unless a later report says so.

---

## 18. Related documents

| Document | Use |
|----------|-----|
| `docs/SAFEHER_DEVELOPER_SETUP.pdf` | Printable copy of this guide |
| `README.md` | Short index |
| `TEAM_HANDOVER.pdf` | Older short handover |
| `PRODUCTION_SETUP.md` | Production DNS / hosting |
| `safeher_backend/.env.example` | Env names |
| `safeher_ai/README.md` | Retrain only |

---

## 19. Verification notes (authoring)

Checked against repository files: Gradle versions, SDK levels, package name, `.env.example` keys, Alembic filenames, uvicorn module path `app.main:app`, ping routes, OTP shortcut, gitignore entries, TFLite names, debug/release URLs, compose Postgres sample, CI Python 3.11.

Not executed as a blank-PC install. Android Studio exact version, OEM USB drivers, and live Firebase Console IAM were **NOT VERIFIED**.
