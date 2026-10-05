# SafeHer

SafeHer is a personal-safety platform that combines an Android app, FastAPI backend, multi-signal AI (distress audio + emergency phrases + movement → Safety Decision Engine), Firebase messaging, and WhatsApp emergency-contact alerts with a live location track page.

This repository is the team handover of the SafeHer monorepo (**source, models, and docs**). Large training datasets and local secrets are **not** included.

---

## Start here (complete fresh-machine setup)

**The complete developer setup / handover guide** (clone GitHub, configure every required file, run FastAPI in VS Code, run Android in Android Studio, connect the phone/emulator to the backend, troubleshooting, security rules):

- **PDF (print / share):** [`docs/SAFEHER_DEVELOPER_SETUP.pdf`](docs/SAFEHER_DEVELOPER_SETUP.pdf)
- **Markdown (source of truth):** [`docs/SAFEHER_DEVELOPER_SETUP.md`](docs/SAFEHER_DEVELOPER_SETUP.md)

Regenerate the PDF after editing the Markdown:

```bash
pip install fpdf2
python scripts/generate_developer_setup_pdf.py
```

A shorter older onboarding PDF still exists as **TEAM_HANDOVER.pdf**. Use the `docs/SAFEHER_DEVELOPER_SETUP.*` files as the full setup path.

---

## Project structure

```
SAFEHER/
├── docs/                # Complete developer setup guide (PDF + Markdown)
├── safeher_android/     # Kotlin + Jetpack Compose Android app
├── safeher_backend/     # FastAPI API, auth, alerts, location, AI endpoints
├── safeher_ai/          # YAMNet training / export pipeline + model artifacts
├── safeher_web/         # Static emergency contact track page
├── PRODUCTION_SETUP.md  # Production DNS / Firebase / WhatsApp checklist
├── TEAM_HANDOVER.pdf    # Short team onboarding PDF
└── README.md            # This file
```

Regenerate the short handover PDF with:

```bash
pip install fpdf2
python scripts/generate_handover_pdf.py
```

**Not in Git (keep locally / share privately):**

| Path | Reason |
|------|--------|
| `safeher_ai/data/` | Large audio datasets (~10 GB) |
| `venv311/`, `venv/`, `.venv/`, root `safeher/` | Python virtualenvs |
| `.env`, `*adminsdk*.json`, `google-services.json`, keystores | Secrets / private keys |
| `build/`, `.gradle/`, `node_modules/` | Generated artifacts |

Store `safeher_ai/data/` on Drive/OneDrive/S3 and share with the team separately. Extract into `safeher_ai/data/` to retrain.

---

## Prerequisites

- Python 3.11+ (backend + AI)
- Android Studio (Ladybug+ recommended), JDK 17
- PostgreSQL
- Redis (recommended for production dead-man switch)
- Firebase project (Auth/FCM; optional RTDB)
- Meta WhatsApp Cloud API (or Twilio if you re-enable Twilio env vars)
- Google Maps API key (Android maps)

---

## Environment variable setup

### Backend

```bash
cd safeher_backend
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
```

Fill placeholders only in `.env` (never commit it):

- `DATABASE_URL`, `SECRET_KEY`, `REDIS_URL`
- `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`, `META_WABA_ID` (+ template names)
- `FIREBASE_CREDENTIALS_PATH` → local path to your Admin SDK JSON (rename/copy to `firebase-credentials.json`)
- `FIREBASE_DATABASE_URL`
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` (if used)
- `TRACK_BASE_URL`, `API_BASE_URL`

See `safeher_backend/.env.example` and `PRODUCTION_SETUP.md`.

### Android

1. Place Firebase `google-services.json` in `safeher_android/app/` (not committed).
2. Copy `local.properties.example` → `local.properties` and set `sdk.dir` + `MAPS_API_KEY`.
3. For release: create `keystore.properties` from `keystore.properties.example`.

---

## Firebase setup

1. Create/use Firebase project; register Android apps (`com.safeher.app`, debug variant if used).
2. Download `google-services.json` into `safeher_android/app/`.
3. Create a service account; download Admin SDK JSON for the backend; point `FIREBASE_CREDENTIALS_PATH` at it.
4. Enable Cloud Messaging (and Crashlytics if desired).

---

## Twilio / WhatsApp setup

Current backend messaging is oriented around **Meta WhatsApp Cloud API** (`META_*` env vars). Configure approved message templates for alerts/cancel in production.

`PRODUCTION_SETUP.md` also documents Twilio-style variables if you use that path. Sandbox vs production template rules apply — freeform WhatsApp bodies are sandbox-only.

---

## Backend setup & run

```bash
cd safeher_backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
# Ensure PostgreSQL + Redis are running and .env is filled
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: `http://localhost:8000/docs`

---

## Android setup & run

1. Open `safeher_android/` in Android Studio.
2. Add `google-services.json` and `local.properties` (see above).
3. Sync Gradle; run the `app` configuration on a device/emulator.
4. Point the app at your backend base URL (debug builds typically use LAN IP / emulator `10.0.2.2:8000` — check existing BuildConfig / network config in the project).
5. Copy exported TFLite into assets if needed (see AI section / `PRODUCTION_SETUP.md`).

```bash
cd safeher_android
.\gradlew assembleDebug
```

---

## Web setup & run

`safeher_web/track/` is a static contact track page.

- Locally, the backend can serve it at `http://localhost:8000/track/` when the monorepo layout is intact.
- Production: host `track/index.html` on `safeher.app` with rewrite so `/track` keeps the query `token=`.

Details: `safeher_web/README.md`.

---

## AI pipeline setup & run

Code and trained artifacts live under `safeher_ai/`. Datasets are **not** in Git.

```bash
cd safeher_ai
pip install -r requirements_training.txt
# Place dataset under data/raw/{distress,normal,noise}/ if retraining
cd training
python 00_convert_audio.py
python 01_prepare_dataset.py
python 02_train_model.py
python 03_evaluate_model.py
python 04_export_tflite.py
```

Copy `models/final/yamnet_distress_quant.tflite` (or the non-quant model) into the Android app assets as documented in `PRODUCTION_SETUP.md` / Android docs.

Full labeling notes: `safeher_ai/README.md`.

---

## How to test the system

1. Start Postgres, Redis, backend (`uvicorn`).
2. Run Android app; register/login; grant mic/location permissions.
3. Trigger SOS / AI distress path → WhatsApp to emergency contacts with track link.
4. Open track link → map updates while alert is active; cancels when alert cancelled.
5. Confirm FCM token saved after login; stop pings to exercise dead-man escalation (needs Redis in multi-worker prod).
6. Backend: `cd safeher_backend && pytest`

---

## Current known limitations

- Large training audio under `safeher_ai/data/` must be shared outside Git.
- WhatsApp production requires approved templates and correct Meta app configuration.
- Maps tiles need a valid `MAPS_API_KEY` in `local.properties`.
- Redis in-memory fallback is for development; use Redis in production.
- Dataset class balance may be skewed (more normal than distress) — review before shipping model updates.
- `data/raw/noise/` may be missing locally; pipeline expects it for augmentation.

---

## Team handover instructions

1. Clone this repo; do **not** commit secrets.
2. Follow **[`docs/SAFEHER_DEVELOPER_SETUP.pdf`](docs/SAFEHER_DEVELOPER_SETUP.pdf)** (or the Markdown) end to end.
3. Obtain privately: backend `.env` values, Firebase Admin JSON, `google-services.json`, Maps key, WhatsApp tokens, and optionally `safeher_ai/data/`.
4. Read `PRODUCTION_SETUP.md` before production DNS/hosting changes.
5. Rotate any credentials that were ever shared in chat, screenshots, or old commits.

**Never commit:** `.env`, Firebase Admin SDK JSON, `google-services.json`, keystores, `local.properties` with machine paths/keys, or raw user recordings without consent/license review.
