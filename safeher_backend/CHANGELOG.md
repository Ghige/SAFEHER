# SafeHer Backend — MVP Fix Changelog

## B-06 — Fix emergency contact `relationship` field (2026-08-01)

### Root cause
The SQLAlchemy model column is `relationship_type`, but `POST /users/contacts` passed
`relationship=` (invalid ORM kwarg → `TypeError`). `ContactResponse` could not read
`relationship` from the ORM because field names did not match.

### Files modified
- `app/api/v1/users.py` — use `relationship_type=payload.relationship` on create
- `app/schemas/user_schema.py` — `Field(validation_alias="relationship_type")` on `ContactResponse`

### API impact
None — JSON field remains `relationship` (Android contract unchanged).

### Migration impact
None.

### Risks
Low — localized mapping fix.

### Verification
- Pydantic unit check: `ContactResponse.model_validate` returns `relationship="Mother"`
- Live API: `POST /api/v1/users/contacts` → 201 with `relationship: "Mother"`
- Live API: `GET /api/v1/users/contacts` → same value in list

---

## B-12 — Authorize `GET /helpers/nearby` to alert owner (2026-08-01)

### Root cause
Any authenticated user could list helpers for any `alert_id` (IDOR), exposing helper
notification metadata for alerts they do not own.

### Files modified
- `app/api/v1/helpers.py` — verify `Alert.user_id == current_user.id` before returning helpers

### API impact
None for legitimate clients (only alert owner calls this endpoint). Other users receive **404**.

### Migration impact
None.

### Risks
Low.

### Verification
- TestClient: alert owner → 200; other user → 404

---

## B-13 — Authorize `POST /helpers/block/{id}` to alert owner (2026-08-01)

### Root cause
`block_helper()` ignored `alert_user_id` and cancelled any helper record by ID without
verifying the caller owns the alert.

### Files modified
- `app/services/helper_service.py` — verify alert ownership before block
- `app/api/v1/helpers.py` — return **403** for unauthorized block attempts

### API impact
None for alert owner. Non-owners receive **403** instead of silently succeeding.

### Migration impact
None.

### Risks
Low.

### Verification
- TestClient: non-owner block → 403; owner block → 204

---

## B-14 — Authorize `POST /helpers/respond/{alert_id}` (2026-08-01)

### Root cause
Any authenticated user could call respond; alert owners could respond to their own alert;
helpers could respond when not in `notified` status or when alert was inactive.

### Files modified
- `app/services/helper_service.py` — require active alert, notified helper record, block alert owner

### API impact
- Alert owner → **403**
- User not notified for this alert → **404**
- Valid notified helper → **200** (unchanged)

### Migration impact
None.

### Risks
Low — tightens helper respond path only.

### Verification
- TestClient: owner → 403; stranger → 404

---

## B-20 — Prevent duplicate active SOS alerts (2026-08-01)

### Root cause
`trigger_alert()` always created a new `active` alert even when the user already had one,
causing duplicate SOS records and repeated notifications.

### Files modified
- `app/services/alert_service.py` — reject trigger when `get_active_alert()` returns a row

### API impact
Second concurrent SOS while active → **400** `"An active alert already exists"` (client should cancel first).

### Migration impact
None.

### Risks
Low — matches Android client behavior (checks active alert before trigger).

---

## B-21 — City-based helper matching for MVP (2026-08-01)

### Root cause
`find_and_notify_helpers()` notified up to 5 arbitrary users (excluding the alert owner),
ignoring location entirely — wrong people received helper notifications.

### Files modified
- `app/services/helper_service.py` — notify only users in the same city as the alert owner;
  skip helper notification when alert user has no city

### API impact
None on endpoints. Helper notifications are now city-scoped until GPS/PostGIS (V2).

### Migration impact
None.

### Risks
Medium — users must set `city` on registration for helper matching to work.
Better than notifying random users nationwide.

---

## B-15 — Require phone verification for SOS mutations (2026-08-01)

### Root cause
Users received a JWT at registration before OTP verification and could trigger SOS,
cancel alerts, send location updates, and call AI SOS endpoints without a verified phone.

### Files modified
- `app/api/deps.py` — added `get_verified_user()` dependency
- `app/api/v1/alerts.py` — `trigger`, `cancel`, `ping` require verified user
- `app/api/v1/ai.py` — `audio-sos`, `movement-sos` require verified user
- `app/api/v1/location.py` — `update`, `track-link` require verified user

### API impact
Unverified users receive **403** on SOS/alert mutation endpoints. `/ai/confidence` and
read-only alert endpoints remain available with a valid JWT.

### Migration impact
None.

### Risks
Low — aligns with Android OTP flow (verify before emergency features).

### Verification
- TestClient: unverified trigger → 403; after OTP verify → 201

---

## B-16 — Rate limit fails closed on Redis errors (2026-08-01)

### Root cause
When Redis raised an error during a rate-limit check, `check_rate_limit()` returned
`True` (allow), bypassing auth/SOS throttling during Redis outages.

### Files modified
- `app/services/redis_service.py` — return `False` (deny) on Redis pipeline failures

### API impact
During Redis errors, auth/alert requests may receive **429** instead of being allowed through.
In-memory fallback (dev/single-worker) unchanged.

### Migration impact
None.

### Risks
Low — stricter during Redis outages; correct for MVP security.

### Verification
- Unit test: mocked Redis error → `check_rate_limit` returns `False`
- In-memory fallback still allows requests when Redis is entirely unavailable

---

## Swagger OAuth2 — Fix JWT Authorize flow (2026-08-01)

### Root cause
`OAuth2PasswordBearer` pointed at `POST /auth/login`, but Swagger's **Authorize**
button sends `application/x-www-form-urlencoded` data (`username`, `password`) per the
OAuth2 password grant. `/auth/login` expects JSON (`phone_number`, `password`), so
token exchange failed and no Bearer header was attached.

### Files modified
- `app/api/deps.py` — `tokenUrl` → `/api/v1/auth/token`
- `app/api/v1/auth.py` — added `POST /auth/token` (`OAuth2PasswordRequestForm`);
  extracted `_authenticate_user()`; kept JSON `/auth/login` for Android

### API impact
- **New:** `POST /api/v1/auth/token` (form: `username`=phone, `password`)
- **Unchanged:** `POST /api/v1/auth/login` (JSON body for mobile app)

### Swagger usage
1. Click **Authorize**
2. **username** = phone number (e.g. `9876543210`)
3. **password** = account password
4. Call protected endpoints — Bearer token attached automatically

### Verification
- OpenAPI `tokenUrl` = `/api/v1/auth/token`
- TestClient: form login → `GET /users/profile` → 200
- Swagger UI shows Token URL `/api/v1/auth/token` on Authorize dialog

---

## Layer 2 — A-01: Wire dead switch background scheduler (2026-08-02)

### Root cause
`check_dead_switches()` existed but was never called — dead man's switch escalation
could not run in production.

### Files modified
- `app/services/scheduler.py` — new async loop calling `check_dead_switches` every 60s
- `app/main.py` — FastAPI `lifespan` starts/stops scheduler on app boot/shutdown

### Migration impact
None.

### Verification
- `from app.main import app` succeeds
- Scheduler logs on startup when uvicorn runs

---

## Layer 2 — A-02: Treat escalated alerts as ongoing (2026-08-02)

### Root cause
After dead-switch escalation (`status=escalated`), `get_active_alert`, cancel, ping, and
location update only matched `status=active` — app lost ability to ping/cancel/track.

### Files modified
- `app/services/alert_service.py` — `ONGOING_ALERT_STATUSES = ("active", "escalated")`
- `app/services/location_service.py` — location updates allowed while escalated

### Migration impact
None.

### Verification
- Escalated alerts appear on `GET /alerts/active`; ping/cancel/location still work

---

## Layer 2 — A-03: Require emergency contacts before SOS (2026-08-02)

### Root cause
Backend allowed SOS with zero contacts — WhatsApp notifications went nowhere while
Android already blocked this client-side.

### Files modified
- `app/services/alert_service.py` — reject trigger when no active emergency contacts

### API impact
`POST /alerts/trigger` without contacts → **400** `"Add at least one emergency contact..."`

---

## Layer 2 — A-04: Validate alert trigger schema (2026-08-02)

### Files modified
- `app/schemas/alert_schema.py` — `TriggerType` literal enum, coord range/pairing, DECIMAL→float

### API impact
Invalid `trigger_type` → **422**; lat/lng must be paired and in valid ranges.

---

## Layer 2 — A-05: Alert API integration tests (2026-08-02)

### Files modified
- `tests/test_alerts_api.py` — verify auth, contacts, trigger/cancel/ping/history flows

---

## Layer 2 — A-06: Production config template + runtime deps (2026-08-02)

### Files modified
- `.env.example` — documents all Alerts-layer env vars
- `requirements.txt` — added twilio, firebase-admin, redis, pydantic-settings, pytest, httpx
- `app/services/alert_constants.py` — breaks circular import for ongoing statuses

---

## Layer 3 — L-01: Validate location update coordinates (2026-08-02)

### Root cause
`LocationUpdate` accepted any float for latitude/longitude; invalid GPS values could be stored.

### Files modified
- `app/schemas/alert_schema.py` — `Field(..., ge=-90, le=90)` / `ge=-180, le=180`

### API impact
Out-of-range coords → **422** (Pydantic validation). Valid payloads unchanged.

### Verification
- `tests/test_location_api.py::test_location_update_rejects_invalid_coordinates` → PASS

---

## Layer 3 — L-02: Hide live coords after alert ends (2026-08-02)

### Root cause
`GET /location/live` returned last known coordinates even for cancelled/resolved alerts,
leaking location after SOS ended.

### Files modified
- `app/api/v1/location.py` — redact lat/lng/maps_embed when status ∉ `ONGOING_ALERT_STATUSES`

### API impact
Contacts still get **200** with `status` field; coords are `null` when alert is not ongoing.
Backward compatible — clients should already handle null coords.

### Verification
- `tests/test_location_api.py::test_live_hides_coords_after_cancel` → PASS

---

## Layer 3 — L-03: Track link only for ongoing alerts (2026-08-02)

### Root cause
`GET /location/track-link/{alert_id}` worked on cancelled alerts, allowing new tracking
links after SOS ended.

### Files modified
- `app/api/v1/location.py` — require `Alert.status.in_(ONGOING_ALERT_STATUSES)`

### API impact
Cancelled/resolved alerts → **404** `"No active alert found"` (was 200).

### Verification
- `tests/test_location_api.py::test_track_link_not_available_after_cancel` → PASS

---

## Layer 3 — L-04: Rate limit location updates (2026-08-02)

### Root cause
`POST /location/update` had no rate limiting; rapid GPS spam could overload DB/Firebase.

### Files modified
- `app/api/v1/location.py` — per-user Redis/in-memory limit via `check_rate_limit`

### API impact
Excess updates → **429** `"Too many location updates."` (same limit as alerts).

### Verification
- Rate limit helper wired; existing alert rate-limit tests still pass

---

## Layer 3 — L-05: Location API integration tests (2026-08-02)

### Files modified
- `tests/test_location_api.py` — 7 tests covering update, auth, coords, track-link, live view

### Verification
- `pytest tests/test_location_api.py tests/test_alerts_api.py` → **11 passed**

---

## Layer 4 — H-01: Allow helper respond on escalated alerts (2026-08-02)

### Root cause
`helper_respond()` only accepted `status == "active"`, blocking helpers after dead-switch
escalation even though the SOS is still in progress.

### Files modified
- `app/services/helper_service.py` — use `ONGOING_ALERT_STATUSES` (`active`, `escalated`)

### API impact
Helpers can respond during escalated alerts. Cancelled/resolved still → **404**.

### Verification
- `tests/test_helpers_api.py::test_helper_respond_on_escalated_alert` → PASS

---

## Layer 4 — H-02: Approve helper only during ongoing alert (2026-08-02)

### Root cause
`approve_helper()` did not check alert status; identity could be revealed after cancel.

### Files modified
- `app/services/helper_service.py` — reject when status ∉ `ONGOING_ALERT_STATUSES`

### API impact
Approve on cancelled alert → **404** `"Active alert not found"`.

### Verification
- `tests/test_helpers_api.py::test_approve_rejected_after_cancel` → PASS

---

## Layer 4 — H-03: Require verified user for helper mutations (2026-08-02)

### Root cause
`POST /approve`, `/block`, `/respond`, and blocklist mutations used `get_current_user`,
allowing unverified accounts to interact with the helper flow.

### Files modified
- `app/api/v1/helpers.py` — `get_verified_user` on mutation endpoints

### API impact
Unverified users → **403** on helper mutations (matches Alerts/Location layer).

### Verification
- `tests/test_helpers_api.py::test_helper_mutations_require_verified_user` → PASS

---

## Layer 4 — H-04: Typed response for helper respond (2026-08-02)

### Root cause
`POST /helpers/respond` returned a raw SQLAlchemy model without `response_model`,
producing an inconsistent JSON contract for Android.

### Files modified
- `app/api/v1/helpers.py` — `response_model=HelperResponse`, identity fields redacted

### API impact
Response shape now matches `GET /nearby` helper objects. No breaking change for clients
already reading `status` field.

### Verification
- `tests/test_helpers_api.py::test_helper_respond_and_approve` → PASS

---

## Layer 4 — H-05: Helpers API integration tests (2026-08-02)

### Files modified
- `tests/test_helpers_api.py` — 14 tests (nearby, respond, approve, block, blocklist, auth)
- `tests/conftest.py` — shared rate-limit fixture to prevent test flakes

### Verification
- `pytest tests/test_helpers_api.py tests/test_location_api.py tests/test_alerts_api.py` → **25 passed**

---

## Layer 5 — AI-01: Validate AI SOS payloads (2026-08-02)

### Root cause
AI endpoints accepted out-of-range scores and unpaired GPS coordinates, allowing
invalid fusion input and inconsistent alert records.

### Files modified
- `app/api/v1/ai.py` — `Field(ge=0, le=100)` on scores; lat/lng range + pairing mixin

### API impact
Invalid scores or unpaired coords → **422**. Valid payloads unchanged.

### Verification
- `tests/test_ai_api.py::test_ai_invalid_score_rejected` → PASS
- `tests/test_ai_api.py::test_ai_unpaired_coordinates_rejected` → PASS

---

## Layer 5 — AI-02: Surface trigger failures in AI SOS response (2026-08-02)

### Root cause
When `trigger_alert()` failed (duplicate SOS, no contacts), AI endpoints returned
`alert: null` with `fire_immediately` fusion — Android could not distinguish failure.

### Files modified
- `app/services/ai_alert_service.py` — add `trigger_error` field on ValueError

### API impact
Additive field: `{ "fusion": {...}, "alert": null, "trigger_error": "..." }`.
Backward compatible — clients checking `alert` still work.

### Verification
- `tests/test_ai_api.py::test_duplicate_ai_sos_returns_trigger_error` → PASS
- `tests/test_ai_api.py::test_ai_sos_without_contacts_returns_trigger_error` → PASS

---

## Layer 5 — AI-03: Rate limit AI SOS endpoints (2026-08-02)

### Root cause
`POST /ai/audio-sos` and `/movement-sos` had no rate limiting; rapid calls could
spam the alert pipeline (mitigated by duplicate-alert guard but still abusive).

### Files modified
- `app/api/v1/ai.py` — per-user limit via `check_rate_limit` (same as alerts)

### API impact
Excess AI SOS calls → **429** `"Too many AI SOS requests."`

### Verification
- Rate limit wired; full regression suite passes

---

## Layer 5 — AI-04: AI API integration tests (2026-08-02)

### Files modified
- `tests/test_ai_api.py` — 11 tests (audio/movement SOS, fusion tiers, auth, errors)

### Verification
- `pytest tests/test_ai_api.py` + layers 2–4 regression → **36 passed**

