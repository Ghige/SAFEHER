# SafeHer Production Setup Checklist

## DNS & hosting

| Host | Purpose |
|------|---------|
| `api.safeher.app` | FastAPI backend |
| `safeher.app/track` | Contact track page (`safeher_web/track/`) |

## Backend `.env` (required)

```env
DATABASE_URL=postgresql://...
SECRET_KEY=<random-64-char>
REDIS_URL=redis://...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+...
TRACK_BASE_URL=https://safeher.app/track
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
FIREBASE_DATABASE_URL=https://<project>.firebaseio.com
ENVIRONMENT=production
```

Run migrations: `alembic upgrade head`

## Twilio WhatsApp

- Sandbox: contacts must opt in to `+14155238886`
- Production: use approved WhatsApp Business templates (freeform `body=` is sandbox-only)

## Firebase Console

1. Register Android apps: `com.safeher.app` and `com.safeher.app.debug`
2. Download official `google-services.json` → replace workaround in `safeher_android/app/`
3. Enable Crashlytics and Cloud Messaging
4. Upload `firebase-credentials.json` for backend FCM + optional RTDB

## Android release

1. `local.properties`: `MAPS_API_KEY=...`
2. `keystore.properties` from `keystore.properties.example`
3. Copy `yamnet_distress_quant.tflite` → `app/src/main/assets/` (if not present)
4. `./gradlew assembleRelease`

## Redis (production)

Required for reliable dead-man switch with multiple workers. In-memory fallback is dev-only.

## Verify end-to-end

1. SOS trigger → WhatsApp received with track link
2. Open track link in browser → map updates
3. FCM token registered: check `users.fcm_token` after app login
4. Stop app pings → escalation WhatsApp + FCM push to user
