# SafeHer Android Changelog

## Task 10 — Production Hardening (2026-08-02)

> **Scope:** Audit, optimize, secure, and stabilize the Android app for production release. No new user-facing features. No backend API changes.

### Audit Summary

Full project review covered: duplicate code, dead code, navigation, coroutines, DataStore, Hilt, Retrofit/OkHttp, FGS, WorkManager, security, Maps, release build, crash handling, and Play Store readiness.

### Files Created

- `app/src/main/res/xml/network_security_config.xml` — HTTPS-only in release
- `app/src/debug/res/xml/network_security_config.xml` — cleartext allowed for debug emulator
- `app/src/main/res/xml/data_extraction_rules.xml` — exclude encrypted token prefs from backup
- `app/src/main/res/xml/backup_rules.xml` — legacy backup exclusion rules
- `core/network/RepositoryApiCall.kt` — shared API error wrapper (deduplicated 7 repositories)
- `services/NotificationChannelManager.kt` — create FGS channels once at app init
- `keystore.properties.example` — release signing template

### Files Modified

| Area | Changes |
|------|---------|
| **Security** | `allowBackup=false`; token prefs excluded from backup; cleartext disabled in release; JWT in-memory cache (`SecureTokenStore`); `commit()` for token writes; backend URL hidden in release Security screen |
| **Network** | Removed `runBlocking` from `AuthInterceptor` and `UnauthorizedInterceptor` |
| **Release** | Expanded `proguard-rules.pro` (Maps, Compose, WorkManager, Hilt); conditional release signing from `keystore.properties` |
| **Performance** | Removed unused deps (Room, Coil, Lottie, SplashScreen lib); deduplicated repository `apiCall` helpers |
| **AI hardening** | `AiMonitoringCoordinator` respects SettingsStore audio/movement/sensitivity toggles; mic FGS only when models available + audio enabled |
| **WorkManager** | `LocationWorker` — network constraint, exponential backoff, unique work name |
| **Maps** | `LocationMap` graceful fallback when `MAPS_API_KEY` missing |
| **Crash handling** | Release uncaught exception guard in `SafeHerApp` (no PII/token logging) |
| **Dead code** | Removed unused `PlaceholderScreen`; splash uses `Route.HOME` |
| **Gradle** | `keystore.properties` gitignored |

### Build & Test Results

| Command | Result |
|---------|--------|
| `./gradlew assembleRelease` | **SUCCESS** (R8 + shrinkResources) |
| `./gradlew assembleDebug` | **SUCCESS** |
| `./gradlew testDebugUnitTest` | **119/119 PASS** |

### Security Fixes

- Cleartext HTTP blocked in release builds
- App backup disabled; encrypted JWT prefs excluded from device transfer
- No tokens logged in release crash handler
- OkHttp interceptors no longer block worker threads
- Backend URL not exposed in release Security screen

### Known Blockers (Production)

- **Release keystore** — create `keystore.properties` from example before Play upload
- **TFLite models** — still missing from `assets/`; AI inference remains stubbed
- **FCM / push** — no client-side push stack; notification preference toggles stored locally only
- **Crash reporting** — no Crashlytics/Sentry integrated yet
- **Background location** — not declared in manifest; Play data-safety declaration needed
- **Adaptive icon** — still using notification drawable as launcher icon
- **Certificate pinning** — not implemented

---

## Task 9 — Settings & Security (2026-08-02)

> **Scope:** Production-ready Settings module — user preferences, privacy, security, permissions, notifications, AI preferences, and app information. No backend API changes. Local DataStore for preferences without backend support. Reuses `SessionCleanupManager` for logout.

### Files Created

**Feature (`feature/settings/`)**
- `SettingsScreen.kt`, `SettingsViewModel.kt`, `SettingsUiState.kt`, `SettingsEvent.kt`
- `AboutScreen.kt`, `PrivacyPolicyScreen.kt`, `TermsScreen.kt`
- `PermissionScreen.kt`, `NotificationSettingsScreen.kt`, `SecurityScreen.kt`, `BatteryOptimizationScreen.kt`

**Components (`feature/settings/components/`)**
- `SettingsCard.kt`, `SettingsItem.kt`, `PermissionStatusCard.kt`
- `TogglePreference.kt`, `SectionHeader.kt`, `LoadingSettings.kt`

**Data layer**
- `domain/model/SettingsModels.kt` — `AppThemeMode`, `AiSensitivity`, `PermissionDisplayStatus`, `PermissionStatuses`, `SecurityInfo`
- `domain/repository/SettingsRepository.kt`, `data/repository/SettingsRepositoryImpl.kt`
- `core/datastore/SettingsStore.kt`
- `services/BatteryOptimizationManager.kt`

**Tests**
- `SettingsRepositoryImplTest.kt` (8 tests)
- `SettingsViewModelTest.kt` (5 tests)

### Files Modified
- `Route.kt` — `SETTINGS`, `SETTINGS_PERMISSIONS`, `SETTINGS_NOTIFICATIONS`, `SETTINGS_SECURITY`, `SETTINGS_ABOUT`, `SETTINGS_PRIVACY`, `SETTINGS_TERMS`, `SETTINGS_BATTERY`
- `DashboardNavigation.kt` — Settings quick action, sub-screen navigation, logout hook
- `RepositoryModule.kt` — `SettingsRepository` DI binding
- `MainActivity.kt` — theme mode from `SettingsStore` (system / light / dark)
- `strings.xml` — settings, privacy, security, permission strings

### Screens
| Screen | Purpose |
|--------|---------|
| Settings (hub) | Account, AI, notifications, permissions, appearance, about |
| Permissions | Location, microphone, notifications, background location + runtime requests |
| Notifications | Master toggle + SOS / helper / AI notification prefs |
| Security | JWT, session, verified phone, app version, backend URL |
| Battery | Optimization status + guide to disable restriction |
| About | Version, developer, privacy, terms, licenses |
| Privacy Policy | Location, mic, contacts, AI, data storage explanations |
| Terms | Usage terms and emergency disclaimer |

### DataStore Keys (`SettingsStore`)
| Key | Type | Default |
|-----|------|---------|
| `notifications_enabled` | Boolean | true |
| `sos_notifications` | Boolean | true |
| `helper_notifications` | Boolean | true |
| `ai_notifications` | Boolean | true |
| `ai_audio_detection` | Boolean | true |
| `ai_movement_detection` | Boolean | true |
| `ai_sensitivity` | String | `"medium"` |
| `theme_mode` | String | `"system"` |
| `language` | String | `"en"` |

AI monitoring enabled remains in **AiSettingsStore** (`ai_monitoring_enabled`).

### Permissions Handled
- `ACCESS_FINE_LOCATION` / `ACCESS_COARSE_LOCATION` — status display + runtime request
- `RECORD_AUDIO` — status display + runtime request
- `POST_NOTIFICATIONS` — status display + runtime request (API 33+)
- Background location — status only (not declared in manifest; shows NOT_REQUESTED / DENIED)
- Battery optimization — detect + open system settings
- `FOREGROUND_SERVICE` — manifest-only (no runtime prompt)

### Build & Test Results

| Command | Result |
|---------|--------|
| `./gradlew assembleDebug` | **SUCCESS** |
| `./gradlew testDebugUnitTest` | **119/119 PASS** |

### Known TODOs
- Language selector UI (DataStore key exists; no locale switching wired yet)
- Open-source licenses screen (placeholder item in About)
- `ACCESS_BACKGROUND_LOCATION` not in manifest — background location must be added before production background tracking
- Permanently-denied permission detection requires Activity `shouldShowRationale` (repository shows DENIED; PermissionScreen handles re-request)

---

## Task 8 — AI Monitoring (2026-08-02)

> **Scope:** Full AI Monitoring module with backend integration, lifecycle-aware monitoring services, and extension points for on-device TFLite models. No fake AI inference. No Task 9 Settings module.

### Pre-Implementation Audit

| Asset | Status |
|-------|--------|
| `yamnet_distress_quant.tflite` | **MISSING** — not in repo |
| `movement_model.tflite` | **MISSING** — not in repo |
| `movement_scaler.pkl` | **MISSING** — not in repo |
| `labels.txt` | **NOT REQUIRED** — audio model is single-sigmoid |
| TensorFlow Lite Gradle deps | **NOT ADDED** — pending model assets |
| `app/src/main/assets/` | **MISSING** |

Architecture built with `MissingAudioInferenceEngine` / `MissingMovementInferenceEngine` placeholders. Confidence scores come **only** from `POST /api/v1/ai/confidence` when real inference produces sensor scores.

### Files Created

**Feature (`feature/ai/`)**
- `AiMonitoringScreen.kt`, `AiMonitoringViewModel.kt`, `AiMonitoringUiState.kt`, `AiMonitoringEvent.kt`
- `AiStatusScreen.kt`, `AiSettingsScreen.kt`, `AiSettingsViewModel.kt`

**Components (`feature/ai/components/`)**
- `ConfidenceCard.kt`, `DetectionStatusChip.kt`, `AudioLevelIndicator.kt`, `MovementIndicator.kt`
- `AiToggleCard.kt`, `ListeningAnimation.kt`, `LoadingAi.kt`

**Services**
- `AudioMonitorService.kt` — foreground service (mic amplitude for UI, 500ms interval)
- `AudioMonitoringLauncher.kt`, `MovementMonitorService.kt`, `AiMonitoringCoordinator.kt`
- `AudioPermissionManager.kt`, `AiSensorState.kt`

**Inference extension points (`services/ai/`)**
- `AiModelAssets.kt`, `AudioInferenceEngine.kt`, `MovementInferenceEngine.kt`
- `MissingAudioInferenceEngine.kt`, `MissingMovementInferenceEngine.kt`

**Data layer**
- `domain/model/AiModels.kt`, `domain/repository/AiRepository.kt`, `data/repository/AiRepositoryImpl.kt`
- `data/remote/dto/AiDtos.kt`, `core/network/AiApi.kt`
- `core/datastore/AiSettingsStore.kt`, `di/AiInferenceModule.kt`

**Tests**
- `AiRepositoryImplTest.kt` (4 tests)
- `AiMonitoringViewModelTest.kt` (6 tests)

### Files Modified
- `Route.kt` — `AI`, `AI_STATUS`, `AI_SETTINGS` routes
- `DashboardNavigation.kt` — AI quick action, SOS countdown/active navigation from AI events
- `NetworkModule.kt`, `RepositoryModule.kt` — AI DI
- `SessionCleanupManager.kt`, `SafeHerApp.kt` — stop AI on logout/session expired; start coordinator
- `AndroidManifest.xml` — `RECORD_AUDIO`, `FOREGROUND_SERVICE_MICROPHONE`, `AudioMonitorService`
- `SessionCleanupManagerTest.kt` — AI cleanup verification
- `strings.xml` — AI strings

### APIs Integrated
| Method | Endpoint | Usage |
|--------|----------|-------|
| POST | `/api/v1/ai/confidence` | Backend-only confidence scores (never invented on device) |
| POST | `/api/v1/ai/audio-sos` | Fire SOS when action is `fire_immediately` (audio trigger) |
| POST | `/api/v1/ai/movement-sos` | Fire SOS for movement/fall when action is `fire_immediately` |

### SOS Flow
- `confirm_30s` → navigates to existing SOS countdown (no auto-fire)
- `fire_immediately` → calls `/audio-sos` or `/movement-sos`, restores active alert from backend
- SOS cancelled → disables AI monitoring
- Logout / session expired → `SessionCleanupManager` stops AI monitoring

### Permissions
- `RECORD_AUDIO` — runtime request with denied/permanently-denied handling + settings redirect
- `POST_NOTIFICATIONS` — existing app-wide flow (AI FGS notification)
- `FOREGROUND_SERVICE_MICROPHONE` — declared for API 34+

### Build & Test Results

| Command | Result |
|---------|--------|
| `./gradlew assembleDebug` | **SUCCESS** |
| `./gradlew testDebugUnitTest` | **106/106 PASS** |

### Known TODOs / Production Blockers
1. Bundle TFLite models in `app/src/main/assets/` and add TensorFlow Lite Gradle dependency
2. Implement `TfliteAudioInferenceEngine` and `TfliteMovementInferenceEngine`
3. Bind real engines in `AiInferenceModule` (replace `Missing*` implementations)
4. Without models, confidence UI stays empty — sensor indicators show raw mic/accelerometer levels only
5. Heart rate spike input not wired (backend field exists; no wearable integration yet)

---

## Task 7 — Helpers Module (2026-08-02)

> **Scope:** Full Helpers module integrating with backend nearby/respond/block APIs. Requires active SOS alert. No AI or Settings.

### Files Created

**Feature (`feature/helpers/`)**
- `HelpersScreen.kt`, `HelpersViewModel.kt`, `HelpersUiState.kt`, `HelpersEvent.kt`
- `HelperProfileScreen.kt`, `HelperProfileViewModel.kt`
- `HelperResponseDialog.kt` (+ `HelperBlockDialog`)
- `BlockedHelpersScreen.kt`

**Components (`feature/helpers/components/`)**
- `HelperCard.kt`, `DistanceBadge.kt`, `AvailabilityChip.kt`, `RespondButton.kt`
- `LoadingHelpers.kt`, `EmptyHelpersView.kt`

**Data layer**
- `domain/model/NearbyHelper.kt`
- `domain/repository/HelpersRepository.kt`
- `data/repository/HelpersRepositoryImpl.kt`
- `data/remote/dto/NearbyHelperDto.kt`, `HelperResponseDto.kt`, `HelperResponseRequestDto.kt`, `BlockedHelperDto.kt`
- `core/network/HelpersApi.kt`

**Tests**
- `HelpersRepositoryImplTest.kt` (5 tests)
- `HelpersViewModelTest.kt` (8 tests)

### Files Modified
- `core/ui/navigation/Route.kt` — `HELPERS`, `HELPER_PROFILE`, `HELPERS_BLOCKED` routes
- `core/network/NetworkModule.kt` — `provideHelpersApi()`
- `di/RepositoryModule.kt` — `bindHelpersRepository`
- `feature/dashboard/DashboardNavigation.kt` — helpers navigation, quick action wiring, top bar titles
- `res/values/strings.xml` — helpers strings

### APIs Integrated
| Method | Endpoint | Usage |
|--------|----------|-------|
| GET | `/api/v1/helpers/nearby?alert_id={uuid}` | Load nearby helpers for active SOS alert |
| POST | `/api/v1/helpers/respond/{alert_id}` | Accept helper response |
| POST | `/api/v1/helpers/block/{helper_id}` | Decline/block helper (204) |

### Screens Completed
- **HelpersScreen** — nearby list, refresh, retry, empty/no-alert states, offline banner, respond/block dialogs
- **HelperProfileScreen** — helper details, availability, notified time, block action
- **BlockedHelpersScreen** — blocked helpers list with empty state

### Build & Test Results

| Command | Result |
|---------|--------|
| `./gradlew assembleDebug` | **SUCCESS** |
| `./gradlew testDebugUnitTest` | **96/96 PASS** |

### Known TODOs
- Backend does not expose distance; UI shows static `"Nearby"` label until API adds coordinates/distance
- `HelperResponseRequestDto` unused — backend respond endpoint takes no body
- Blocked helpers list is session-scoped (from nearby response `cancelled` status); no dedicated blocked-list API
- Helper profile re-fetches via nearby API rather than a dedicated profile endpoint

---

## Task 6 Hardening — Live Location (2026-08-02)

> **Scope:** Conditional approval fixes for Task 6. No Task 7 work.

### Changes

**Priority 1 — Logout & notifications**
- `NotificationPermissionManager` + `NotificationPermissionEffect` — runtime `POST_NOTIFICATIONS` on Android 13+ when entering HOME
- `SessionCleanupManager` — centralized session teardown
- Logout order: stop tracking → clear active alert → clear JWT → navigate Login
- `ProfileViewModel.logout()` delegates cleanup to `RootViewModel` via `SessionCleanupManager`

**Priority 2 — Session expired**
- `UnauthorizedInterceptor` uses `SessionCleanupManager.performSessionExpired()`
- Order: stop FGS → clear active alert → clear JWT → navigate SessionExpired (existing NavGraph flow)

**Priority 3 — LocationWorker**
- Before retry POST, verifies `alert.isOngoing` and matching `alert_id`
- Cancels worker (no POST) if alert is no longer active

### Files Created
- `core/session/SessionCleanupManager.kt`
- `services/NotificationPermissionManager.kt`
- `core/ui/NotificationPermissionEffect.kt`

### Files Modified
- `core/ui/SafeHerAppRoot.kt` — `RootViewModel` uses `SessionCleanupManager`
- `feature/profile/ProfileViewModel.kt` — logout emits navigation only
- `core/network/UnauthorizedInterceptor.kt` — session expired cleanup
- `services/LocationWorker.kt` — ongoing alert guard
- `core/ui/navigation/NavGraph.kt` — notification permission effect on HOME

### Tests Added/Updated
- `SessionCleanupManagerTest.kt` (2 tests)
- `LocationWorkerTest.kt` (2 tests)
- `ProfileViewModelTest.kt` — logout no longer calls `authRepository.logout()` directly

### Build & Test Results

| Command | Result |
|---------|--------|
| `./gradlew assembleDebug` | **SUCCESS** |
| `./gradlew testDebugUnitTest` | **83/83 PASS** |

---

## Task 6 — Live Location (2026-08-02)

> **Scope:** Full live location module with Google Maps, runtime permissions, foreground service background tracking during active SOS, tracking link generation, and backend location updates. No Helpers, AI, or Settings.

### Files Created

**Feature (`feature/location/`)**
- `LocationScreen.kt`, `LocationViewModel.kt`, `LocationUiState.kt`, `LocationEvent.kt`
- `TrackLocationScreen.kt`, `LocationPermissionScreen.kt`, `LocationSettingsScreen.kt`

**Components (`feature/location/components/`)**
- `LocationMap.kt`, `CurrentLocationCard.kt`, `TrackingStatusChip.kt`
- `PermissionCard.kt`, `LoadingLocation.kt`

**Services (`services/`)**
- `LocationForegroundService.kt` — foreground service with persistent notification
- `LocationTrackingService.kt` — start/stop tracking orchestration
- `LocationTrackingCoordinator.kt` — observes active SOS alert, auto-starts/stops service
- `LocationProvider.kt` — fused GPS with balanced accuracy (7s interval)
- `LocationPermissionManager.kt` — permission/GPS settings helpers
- `LocationWorker.kt` — WorkManager retry for offline updates

**Data layer**
- `domain/model/LocationModels.kt`
- `domain/repository/LocationRepository.kt`
- `data/repository/LocationRepositoryImpl.kt`
- `data/remote/dto/LocationUpdateRequestDto.kt`, `LocationUpdateResponseDto.kt`
- `data/remote/dto/TrackLinkResponseDto.kt`, `LiveLocationResponseDto.kt`
- `core/network/LocationApi.kt`

**Tests**
- `LocationViewModelTest.kt` (6 tests)
- `LocationRepositoryImplTest.kt` (3 tests)

### Files Modified

- `core/ui/navigation/Route.kt` — `LOCATION`, `LOCATION_PERMISSION`, `LOCATION_SETTINGS`, `LOCATION_TRACK`
- `feature/dashboard/DashboardNavigation.kt` — live location navigation from quick action
- `core/network/NetworkModule.kt` — `LocationApi` provider
- `di/RepositoryModule.kt` — bind `LocationRepository`
- `SafeHerApp.kt` — Hilt WorkManager, `LocationTrackingCoordinator` startup
- `core/ui/SafeHerAppRoot.kt` — stop tracking on logout
- `AndroidManifest.xml` — Maps API key, FGS permissions, location service, WorkManager init
- `res/values/strings.xml` — location copy

### APIs Integrated

| Endpoint | Method | Usage |
|----------|--------|-------|
| `/api/v1/location/update` | POST | Background FGS updates every 7s during active SOS |
| `/api/v1/location/track-link/{alert_id}` | GET | Generate shareable tracking URL |
| `/api/v1/location/live?token=...` | GET | Public live location (repository ready) |

Uses backend `alert_id` from SOS module — never client-generated IDs. Updates only sent while alert is `active` or `escalated`.

### Screens Completed

| Screen | Features |
|--------|----------|
| **LocationScreen** | Google Map, current marker, follow user, permission flow, tracking status |
| **TrackLocationScreen** | Live map during SOS, share/open tracking link |
| **LocationPermissionScreen** | Runtime permission request, denied/permanent denied handling |
| **LocationSettingsScreen** | Open GPS settings, open app settings |

### Architecture

- `LocationTrackingCoordinator` observes `AlertSessionManager.activeAlert` — auto-starts FGS on SOS, stops on cancel
- `LocationForegroundService` posts location every 7s (balanced accuracy, battery-optimized)
- `LocationWorker` retries failed updates when offline
- Logout via `RootViewModel` stops tracking immediately
- Permission verified before every GPS read and backend update

### Permissions

- `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`
- `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_LOCATION`
- `POST_NOTIFICATIONS`

### Build & Test Results

| Command | Result |
|---------|--------|
| `./gradlew assembleDebug` | **SUCCESS** |
| `./gradlew testDebugUnitTest` | **79/79 PASS** |

### Known TODOs (Task 7+)

- [ ] Helpers module
- [ ] `ACCESS_BACKGROUND_LOCATION` for Android 10+ background when screen off
- [ ] In-app WebView for public live tracking page
- [ ] Geofencing / safe zone alerts
- [ ] Room offline queue for location updates
- [ ] Instrumented UI tests for map and permission flow
- [ ] Link from ActiveAlertScreen to TrackLocationScreen

---

## Task 5 — SOS Module (2026-08-02)

> **Scope:** Full SOS emergency alert flow — countdown, trigger, active alert with heartbeat, cancel, history, and auto-restore after app restart. No Helpers, AI, Settings, or Live Location.

### Files Created

**Feature (`feature/sos/`)**
- `SOSScreen.kt`, `SOSViewModel.kt`, `SOSUiState.kt`, `SOSEvent.kt`
- `CountdownScreen.kt`, `ActiveAlertScreen.kt`, `AlertHistoryScreen.kt`, `AlertHistoryViewModel.kt`
- `EmergencyCountdown.kt`, `CancelSOSDialog.kt`, `SosViewModelScope.kt`
- `util/SosLocationHelper.kt`

**Components (`feature/sos/components/`)**
- `SOSButton.kt`, `CountdownCircle.kt`, `ActiveAlertCard.kt`, `AlertHistoryCard.kt`
- `EmergencyStatusChip.kt`, `LoadingSOS.kt`

**Data layer**
- `domain/model/SafetyAlert.kt`
- `domain/repository/AlertRepository.kt`
- `data/repository/AlertRepositoryImpl.kt`
- `data/remote/dto/TriggerAlertRequestDto.kt`, `AlertResponseDto.kt`, `PingResponseDto.kt`, `AlertHistoryDto.kt`
- `core/network/AlertsApi.kt`
- `core/datastore/ActiveAlertStore.kt`
- `core/session/AlertSessionManager.kt` (60s heartbeat)

**Tests**
- `SOSViewModelTest.kt` (9 tests)
- `AlertHistoryViewModelTest.kt` (3 tests)
- `AlertRepositoryImplTest.kt` (7 tests)

### Files Modified

- `core/ui/navigation/Route.kt` — `SOS`, `SOS_COUNTDOWN`, `SOS_ACTIVE`, `SOS_HISTORY` routes
- `feature/dashboard/DashboardNavigation.kt` — SOS navigation, auto-restore on app start
- `core/network/NetworkModule.kt` — `AlertsApi` provider
- `di/RepositoryModule.kt` — bind `AlertRepository`
- `AndroidManifest.xml` — location permissions for optional trigger coordinates
- `res/values/strings.xml` — SOS copy

### APIs Integrated

| Endpoint | Method | Repository |
|----------|--------|------------|
| `/api/v1/alerts/trigger` | POST | `AlertRepository.triggerAlert()` |
| `/api/v1/alerts/cancel/{alert_id}` | POST | `AlertRepository.cancelAlert(alertId)` |
| `/api/v1/alerts/ping/{alert_id}` | POST | `AlertRepository.pingAlert(alertId)` |
| `/api/v1/alerts/active` | GET | `AlertRepository.getActiveAlert()` |
| `/api/v1/alerts/history` | GET | `AlertRepository.getHistory()` |

Uses backend `alert_id` UUID from trigger response for ping and cancel — never client-generated IDs.

### Screens Completed

| Screen | Features |
|--------|----------|
| **SOSScreen** | Animated SOS button, offline banner, view history, active alert shortcut |
| **CountdownScreen** | 5-second countdown with cancel, animated circle |
| **ActiveAlertScreen** | Active alert card, 60s heartbeat, cancel SOS dialog |
| **AlertHistoryScreen** | Pull-to-refresh history list, empty/error states |

### Architecture

- Activity-scoped `SOSViewModel` shared across SOS flow
- `AlertSessionManager` persists active alert ID and runs 60s heartbeat
- Auto-restore active alert on app start via `GET /alerts/active`
- Optional GPS coordinates on trigger when location permission granted
- Backend validation errors surfaced (no contacts, duplicate alert, unverified, rate limit, offline)

### Build & Test Results

| Command | Result |
|---------|--------|
| `./gradlew assembleDebug` | **SUCCESS** |
| `./gradlew testDebugUnitTest` | **70/70 PASS** |

### Known TODOs (Task 6+)

- [ ] Live Location module (Maps)
- [ ] Foreground service for heartbeat when app backgrounded
- [ ] Runtime location permission request flow before SOS
- [ ] SOS hold-to-trigger gesture (currently tap → countdown)
- [ ] Push notification when alert escalates
- [ ] Room cache for alert history offline
- [ ] Instrumented UI tests for SOS flow
- [ ] Lottie animation on SOS button

---

## Task 4 — Emergency Contacts (2026-08-02)

> **Scope:** Full CRUD for emergency contacts (list, add, delete). Max 5 contacts. UUID-based deletion. No SOS, Helpers, AI, Maps, or Settings.

### Files Created

**Feature (`feature/contacts/`)**
- `ContactsScreen.kt`, `ContactsViewModel.kt`, `ContactsUiState.kt`, `ContactsEvent.kt`
- `AddContactScreen.kt`, `AddContactViewModel.kt`
- `DeleteContactDialog.kt`, `EmptyContactsView.kt`
- `util/ContactValidator.kt`

**Components (`feature/contacts/components/`)**
- `ContactCard.kt`, `ContactItem.kt`, `AddContactButton.kt`
- `RelationshipChip.kt`, `PriorityBadge.kt`, `LoadingContacts.kt`

**Data layer**
- `domain/model/EmergencyContact.kt`
- `domain/repository/ContactsRepository.kt`
- `data/repository/ContactsRepositoryImpl.kt`
- `data/remote/dto/ContactDto.kt`, `CreateContactRequestDto.kt`, `DeleteContactResponseDto.kt`
- `core/network/ContactsApi.kt`

**Tests**
- `ContactValidatorTest.kt` (5 tests)
- `ContactsViewModelTest.kt` (5 tests)
- `AddContactViewModelTest.kt` (3 tests)
- `ContactsRepositoryImplTest.kt` (4 tests)

### Files Modified

- `core/ui/navigation/Route.kt` — `CONTACTS`, `ADD_CONTACT` routes
- `feature/dashboard/DashboardNavigation.kt` — contacts navigation from quick action
- `core/network/NetworkModule.kt` — `ContactsApi` provider
- `di/RepositoryModule.kt` — bind `ContactsRepository`
- `res/values/strings.xml` — contacts copy

### APIs Integrated

| Endpoint | Method | Repository |
|----------|--------|------------|
| `/api/v1/users/contacts` | GET | `ContactsRepository.getContacts()` |
| `/api/v1/users/contacts` | POST | `ContactsRepository.addContact()` |
| `/api/v1/users/contacts/{contact_id}` | DELETE | `ContactsRepository.deleteContact(uuid)` |

Deletion uses backend UUID (`contact.id`), never phone number.

### Screens Completed

| Screen | Features |
|--------|----------|
| **ContactsScreen** | List with cards, pull-to-refresh, FAB add, empty state, offline banner, delete dialog |
| **AddContactScreen** | Name, phone, relationship, ring priority slider (1–5), validation, save |
| **DeleteContactDialog** | Confirmation before remove |

### Architecture

- MVVM + `StateFlow` / `SharedFlow` events
- Shimmer loading, error + retry, offline detection
- Max 5 contacts enforced client-side (FAB disabled) + backend 400 message surfaced
- Auto-refresh contacts list after successful add via `SavedStateHandle`

### Build & Test Results

| Command | Result |
|---------|--------|
| `./gradlew assembleDebug` | **SUCCESS** |
| `./gradlew testDebugUnitTest` | **51/51 PASS** |

### Known TODOs (Task 5+)

- [ ] SOS module
- [ ] Edit contact (backend has no PUT endpoint)
- [ ] Reorder ring priority via drag-and-drop
- [ ] Room cache for offline contact list
- [ ] Contact picker from device address book
- [ ] Instrumented UI tests
- [ ] Lottie empty-state illustration

---

## Task 3 — Dashboard & Profile (2026-08-02)

> **Scope:** Home dashboard with profile card, quick-action placeholders, profile screen with logout. No Contacts, SOS, AI, Helpers, Live Location, or Settings implementation.

### Files Created

**Dashboard (`feature/dashboard/`)**
- `DashboardScreen.kt`, `DashboardViewModel.kt`, `DashboardUiState.kt`, `DashboardEvent.kt`, `DashboardNavigation.kt`
- `ComingSoonScreen` (inline in `DashboardNavigation.kt`)

**Profile (`feature/profile/`)**
- `ProfileScreen.kt`, `ProfileViewModel.kt`, `ProfileUiState.kt`

**Home components (`feature/home/components/`)**
- `HomeTopBar.kt`, `HomeBottomNavigation.kt`, `ProfileCard.kt`, `QuickActionCard.kt`, `StatusCard.kt`, `LoadingView.kt`, `ErrorView.kt`

**Data layer**
- `domain/model/UserProfile.kt`
- `domain/repository/UserRepository.kt`
- `data/repository/UserRepositoryImpl.kt`
- `data/remote/dto/UserProfileDto.kt`

**Tests**
- `DashboardViewModelTest.kt` (5 tests)
- `ProfileViewModelTest.kt` (4 tests)
- `UserRepositoryImplTest.kt` (3 tests)

### Files Modified

- `core/network/SafeHerApi.kt` — added `GET /api/v1/users/profile`
- `di/RepositoryModule.kt` — bind `UserRepository`
- `core/ui/navigation/Route.kt` — `HOME`, `COMING_SOON` routes
- `core/ui/navigation/NavGraph.kt` — `DashboardNavigation` replaces placeholder
- `res/values/strings.xml` — dashboard, profile, error, quick-action strings

### APIs Integrated

| Endpoint | Method | Repository |
|----------|--------|------------|
| `/api/v1/users/profile` | GET | `UserRepository.getProfile()` |

Verification status merged from local `UserPreferences.isPhoneVerified` (not in API response).

### Screens Completed

| Screen | Status |
|--------|--------|
| Dashboard | ✅ Profile card, welcome, verification status, 6 quick-action cards |
| Profile | ✅ Name, phone, city, verification, logout |
| Coming Soon | ✅ Placeholder for Contacts, SOS, AI, Helpers, Live Location, Settings |

### Architecture

- Bottom navigation: Dashboard ↔ Profile
- Nested `NavHost` inside `DashboardNavigation` for tabs + coming-soon stack
- Shimmer loading, error + retry, offline banner via `NetworkMonitor`
- Logout clears JWT + DataStore via `AuthRepository.logout()`, navigates to Login with cleared back stack
- 401 handled by existing `UnauthorizedInterceptor` → `SessionExpiredScreen`

### Build & Test Results

| Command | Result |
|---------|--------|
| `./gradlew assembleDebug` | **SUCCESS** |
| `./gradlew testDebugUnitTest` | **34/34 PASS** |

### Known TODOs (Task 4+)

- [ ] Emergency Contacts module
- [ ] SOS module
- [ ] AI Protection module
- [ ] Helpers module
- [ ] Live Location / Maps module
- [ ] Settings module
- [ ] Backend `is_verified` in profile API (currently local DataStore only)
- [ ] Profile photo upload
- [ ] Pull-to-refresh on dashboard
- [ ] Instrumented UI tests
- [ ] Cached offline profile (Room) for last-known data

---

## Task 2 — Authentication Module (2026-08-02)

> **Scope:** Full auth flow — Splash → Onboarding → Login/Register → OTP → Home placeholder. JWT storage, session expiry, logout. No Dashboard or feature screens.

### Files Created

**Feature (`feature/auth/`)**
- `SplashScreen.kt`, `SplashViewModel.kt`
- `OnboardingScreen.kt`, `OnboardingViewModel.kt`
- `LoginScreen.kt`, `LoginViewModel.kt`
- `RegisterScreen.kt`, `RegisterViewModel.kt`
- `OtpScreen.kt`, `OtpViewModel.kt`
- `SessionExpiredScreen.kt`
- `util/AuthValidator.kt`

**Data layer**
- `data/remote/dto/LoginRequestDto.kt`, `RegisterRequestDto.kt`, `SendOtpRequestDto.kt`, `OtpVerifyRequestDto.kt`, `TokenResponseDto.kt`, `MessageResponseDto.kt`
- `data/repository/AuthRepositoryImpl.kt`
- `domain/repository/AuthRepository.kt`

**Network / session**
- `core/network/SafeHerApi.kt`
- `core/network/ApiErrorParser.kt`
- `core/network/UnauthorizedInterceptor.kt`
- `core/session/AuthSessionManager.kt`

**DI**
- `di/RepositoryModule.kt`

**Tests**
- `test/.../feature/auth/util/AuthValidatorTest.kt`
- `test/.../feature/auth/LoginViewModelTest.kt`
- `test/.../feature/auth/RegisterViewModelTest.kt`
- `test/.../data/repository/AuthRepositoryImplTest.kt`

### Files Modified (foundation wiring only)

- `core/ui/navigation/Route.kt` — auth routes
- `core/ui/navigation/NavGraph.kt` — full auth graph + session observer
- `core/ui/SafeHerAppRoot.kt` — `RootViewModel`, logout on placeholder
- `core/datastore/UserPreferences.kt` — `isPhoneVerified` flag
- `core/network/NetworkModule.kt` — `SafeHerApi`, `UnauthorizedInterceptor`
- `core/network/RetrofitClient.kt` — 401 interceptor in OkHttp chain
- `res/values/strings.xml` — auth copy

### APIs Integrated

| Endpoint | Method | Repository |
|----------|--------|------------|
| `/api/v1/auth/register` | POST | `AuthRepository.register()` |
| `/api/v1/auth/login` | POST | `AuthRepository.login()` |
| `/api/v1/auth/send-otp` | POST | `AuthRepository.sendOtp()` |
| `/api/v1/auth/verify-otp` | POST | `AuthRepository.verifyOtp()` |

### Architecture

- **MVVM:** Each screen owns a `@HiltViewModel` with `StateFlow<UiState>` + `SharedFlow<Event>`
- **Validation:** Centralized in `AuthValidator` (phone regex, password min 6, OTP 6 digits)
- **Token storage:** `SecureTokenStore` (EncryptedSharedPreferences)
- **Session prefs:** `UserPreferences` (onboarding, phone, verification flag)
- **401 handling:** `UnauthorizedInterceptor` → `AuthSessionManager.onSessionExpired()` → `SessionExpiredScreen`
- **Auto-login:** Splash checks token + verification → Home or OTP
- **Logout:** Clears token + prefs → Login

### Navigation Flow

```
Splash → Onboarding (first launch) → Login
       → Login (returning user)
       → OTP (token exists, unverified)
       → Placeholder/Home (verified session)
       → SessionExpired (401 detected)
Register → OTP → Placeholder
Login → OTP (if unverified) or Placeholder
```

### Test Results

| Suite | Result |
|-------|--------|
| `./gradlew assembleDebug` | **SUCCESS** |
| `./gradlew testDebugUnitTest` | **22/22 PASS** |
| Backend live API (local) | **Partial** — `test_login_wrong_password` ✓ (401); register/login blocked by local bcrypt/passlib env issue (not Android) |
| Repository contract tests | **5/5 PASS** — token save, verify flag, OTP message, logout |

### Remaining Authentication TODOs

- [ ] Lottie splash/success animations when assets available
- [ ] Branded design-system components (Phase 3 buttons/fields) — currently Material 3 defaults
- [ ] Refresh token support (backend returns 501 on `/auth/refresh`)
- [ ] Instrumented UI tests for auth flow on device
- [ ] Live backend E2E verification when server + DB are running (`OTP_PROVIDER=mock`, OTP=`123456`)
- [ ] Phone number country-code picker UX

---

## Task 1 — Foundation Rebuild (2026-08-02)

> **Scope:** Recreated `app/src/` from scratch after source tree was confirmed missing. No feature screens, no authentication — compile-only foundation with a placeholder UI.

### Files Created

**Application**
- `app/src/main/AndroidManifest.xml`
- `app/src/main/java/com/safeher/app/SafeHerApp.kt`
- `app/src/main/java/com/safeher/app/MainActivity.kt`

**Design system (`core/designsystem/`)**
- `Color.kt`, `Typography.kt`, `Shape.kt`, `Theme.kt`

**UI & navigation (`core/ui/`)**
- `SafeHerAppRoot.kt` — root composable + `PlaceholderScreen` ("SafeHer")
- `navigation/Route.kt` — `Route.PLACEHOLDER`
- `navigation/NavGraph.kt` — single-route NavHost

**Network (`core/network/`)**
- `NetworkModule.kt` — Hilt module (Moshi, OkHttp, RetrofitClient)
- `RetrofitClient.kt` — Retrofit builder using `BuildConfig.BASE_URL`
- `AuthInterceptor.kt` — attaches `Authorization: Bearer` from `SecureTokenStore`
- `ApiErrorBody.kt` — Moshi DTO for FastAPI `{ "detail": "..." }`
- `NetworkMonitor.kt` — `ConnectivityManager` → `Flow<Boolean>`

**DataStore (`core/datastore/`)**
- `SecureTokenStore.kt` — EncryptedSharedPreferences for JWT
- `UserPreferences.kt` — DataStore (onboarding flag, user phone)

**DI**
- `di/AppModules.kt` — root Hilt module (network bindings in `NetworkModule`)

**Resources**
- `res/values/strings.xml`, `colors.xml`, `themes.xml`, `dimens.xml`
- `res/drawable/ic_notification.xml`

**Gradle**
- `gradle/libs.versions.toml` — version catalog (recreated)

### Dependencies (via `libs.versions.toml` + `app/build.gradle.kts`)

| Category | Libraries |
|----------|-----------|
| UI | Compose BOM, Material 3, Navigation Compose, Activity Compose, Splash Screen |
| DI | Hilt, Hilt Navigation Compose, Hilt Work |
| Network | Retrofit, Moshi (+ KSP codegen), OkHttp, Logging Interceptor |
| Storage | DataStore Preferences, Room, Security Crypto |
| Async | Coroutines (Android + Play Services) |
| Other | Timber, Coil, Lottie, WorkManager, Play Services Location/Maps, Maps Compose |

### Architecture

```
app/
├── SafeHerApp.kt          @HiltAndroidApp
├── MainActivity.kt        @AndroidEntryPoint → SafeHerTheme → SafeHerAppRoot
├── core/
│   ├── designsystem/      Material 3 theme tokens
│   ├── ui/                Root composable + Navigation Compose
│   ├── network/           Retrofit + Moshi + OkHttp + AuthInterceptor
│   └── datastore/         SecureTokenStore + UserPreferences
└── di/                    AppModules (Hilt)
```

- **Pattern:** MVVM-ready foundation (ViewModels deferred to Task 2+)
- **Package:** `com.safeher.app`
- **Debug API:** `http://10.0.2.2:8000/` (emulator → host)
- **Release API:** `https://api.safeher.app/`

### Compile Status

| Command | Result |
|---------|--------|
| `./gradlew assembleDebug` | **SUCCESS** (Gradle 9.3.0, AGP 8.7.3, Kotlin 2.0.21) |
| APK | `app/build/outputs/apk/debug/app-debug.apk` |

### Launch Verification

- Build compiles and packages successfully.
- Placeholder screen displays centered **"SafeHer"** text via `Route.PLACEHOLDER`.
- **Device launch:** not verified in this session — no emulator/device connected via `adb devices`. Install with:
  ```bash
  adb install app/build/outputs/apk/debug/app-debug.apk
  ```

### Known TODOs (Task 3+)

- [x] ~~Authentication flow (Login, Register, OTP)~~ — **Task 2 complete**
- [ ] API service interfaces + backend DTOs (remaining 15 DTOs)
- [ ] Repository layer + domain models
- [ ] Feature screens (SOS, Maps, Contacts, Helpers, AI, Settings)
- [ ] Design system components (buttons, text fields, cards — Phase 3 artifacts)
- [ ] Room database entities
- [ ] 401 auto-logout interceptor
- [ ] `AiSosResponseDto.trigger_error` field (backend Layer 5 gap)
- [ ] Lottie assets, branded launcher icon
- [ ] Unit + instrumentation tests

---

## Phase 10 - Background Protection & Emergency Notifications

### Files Created
- `domain/model/ProtectionModels.kt` — ProtectionState, BackgroundSession, NotificationPreference, EmergencyNotification
- `core/notification/NotificationChannels.kt`, `SafeHerNotifier.kt`, `NotificationActionReceiver.kt`
- `core/protection/SafeHerForegroundService.kt`, `BatteryOptimizationHelper.kt`
- `core/work/BackgroundSyncWorker.kt` (+ BackgroundSyncScheduler)
- `data/repository/ProtectionRepositoryImpl.kt`
- `feature/protection/ProtectionViewModel.kt`, `ProtectionCenterScreen.kt`, `ProtectionScreens.kt`
- `res/drawable/ic_notification.xml`
- Tests: ProtectionRepositoryImplTest, ProtectionViewModelTest (+ channel/mode tests)

### Files Modified
- `UserPreferences.kt` — protection + notification preference keys
- `AppConstants.kt` — channels, notification IDs, work names, actions
- `Repositories.kt` — ProtectionRepository; pending counts on Location/AI
- `LocationRepositoryImpl.kt` / `AiRepositoryImpl.kt` — pendingUpdateCount / pendingAnalysisCount
- `AppModules.kt` — bind ProtectionRepository
- `SafeHerApp.kt` — create channels + schedule periodic sync
- `AndroidManifest.xml` — FGS location service, notification receiver
- `Route.kt` / `SafeHerAppRoot.kt` — Protection Center under Settings
- SOS / Maps / LiveTracking / AI / Dashboard integrations
- Icon registry (+ Notifications, Sync)
- Related unit tests updated for new constructor deps

### APIs Integrated
- No new backend endpoints — reuses location flush, AI flush, contact refresh, alert cancel via existing repositories

### Architecture Decisions
- FGS runs **only** for SOS or Live Tracking; stops immediately on session end
- SOS cancel now also `stopSharing()` + `stopSession()` (fixes Phase 8 gap)
- AI high-confidence shows heads-up notification + in-app confirm — never auto SOS
- WorkManager sync requires network; flushes location + AI queues and refreshes contacts
- Battery optimization: educate + open settings; no aggressive ignore-request
- Lock-screen privacy via `sensitiveLockScreen` preference (VISIBILITY_PRIVATE)

### Notification Flow
1. Channels: SOS (HIGH), Tracking (DEFAULT), AI (HIGH), General (LOW)
2. SOS/Tracking → persistent FGS notification with actions (Open / Cancel SOS / Share / Call)
3. AI warning → auto-cancel heads-up → opens AI confirmation path
4. Notification actions handled by `NotificationActionReceiver` (Hilt)

### Foreground Service Design
- Type: `location` (Android 10+)
- START_STICKY + restart on task removed if session still active
- 1s ticker updates elapsed time without logging coordinates

### Testing
- ProtectionRepositoryImplTest — sync flush, start/stop SOS session, queue size
- ProtectionViewModelTest / NotificationSettingsViewModelTest
- Phase10ProtectionTests — FGS extras, notification actions/channels, BackgroundSyncWorker success/retry
- Channel ID + ProtectionMode unit checks
- Updated SOS / Maps / Live / AI / Dashboard tests for new deps

### Remaining Work
- Instrumentation tests for FGS on device/API 34
- Dead-switch ping worker using `DEAD_SWITCH_PING_INTERVAL_SECONDS`
- Richer notification icons / deep-link routing from `route_hint`

### Build Status
- `assembleDebug`: **SUCCESS**
- `testDebugUnitTest`: **SUCCESS** (103 tests)

## Phase 9 - AI Engine & Smart Emergency Detection

### Files Created
- `domain/model/AiModels.kt` — `DetectionResult`, `AIConfidence`, `AudioAnalysis`, `DetectionHistory`, `RiskLevel`, recommendations
- `core/audio/AudioAmplitudeMonitor.kt` — mic amplitude sampling (no raw audio persistence)
- `data/repository/AiRepositoryImpl.kt` — confidence/analyze, local history, offline queue
- `feature/ai/AIViewModel.kt`, `AISafetyScreen.kt`, `AIStatusCard.kt`
- `feature/ai/AudioDetectionViewModel.kt`, `AudioDetectionScreen.kt`
- `feature/ai/DetectionHistoryScreen.kt`
- Tests: `AiRepositoryImplTest`, `AIViewModelTest`, `AudioDetectionViewModelTest` (+ mic permission)

### Files Modified
- `domain/repository/Repositories.kt` — expanded `AiRepository` (analyze, history, status, flush)
- `data/repository/RepositoriesImpl.kt` — removed inline `AiRepositoryImpl`
- `core/utils/AppConstants.kt` — AI thresholds / listen duration
- `core/ui/navigation/Route.kt` — `AiAudio`, `AiHistory`
- `core/ui/SafeHerAppRoot.kt` — wired AI screens
- `feature/home/DashboardViewModel.kt` + `DashboardScreen.kt` — AI status, risk, last detection, Quick Start AI
- `AndroidManifest.xml` — `RECORD_AUDIO`
- Dashboard tests updated for `AiRepository`

### APIs Integrated
- `POST /api/v1/ai/confidence` — primary scoring path (never fires alerts)
- `POST /api/v1/ai/audio-sos` — available via repository; **not** called from confirmation UI (avoids server auto-fire)
- `POST /api/v1/ai/movement-sos` — available via repository for future movement UI

**Client policy:** analysis uses `/confidence` only. Elevated scores show a full-screen confirmation; "Trigger SOS" navigates to Phase 6 SOS (still requires countdown). Never auto-triggers.

### Architecture Decisions
- On-device mic → amplitude score → `/confidence` → local `DetectionResult` history (metadata only).
- Backend audio/movement SOS endpoints exist but can fire alerts server-side — client avoids them until a dedicated confirmed path is designed.
- Offline: pending analyses queued and flushed via `NetworkMonitor`.
- Risk tiers mirror backend scorer (0–39 Low · 40–59 Medium · 60–79 High · 80+ Critical).
- Confirmation threshold = 60 (`AppConstants.AI_CONFIRMATION_THRESHOLD`).

### Testing
- AiRepositoryImplTest — analyze mapping, offline queue, confidence, monitoring flag
- AIViewModelTest — threshold confirm, dismiss, history search
- AudioDetectionViewModelTest — permission, listen gate, stop cleanup
- MicPermissionStateTest — state distinctness

### Remaining Work
- Production on-device ML / scream classifier (current score is amplitude heuristic).
- Movement / fall detection UI using `/ai/movement-sos` after explicit confirm.
- Persist detection history across process death (DataStore/Room).
- Optional: after SOS success, attach AI scores as metadata if backend supports it.

### Build Status
- `assembleDebug`: successful
- APK output: `app/build/outputs/apk/debug/app-debug.apk`

## Phase 8 - Maps & Live Location

### Files Created
- `app/src/main/java/com/safeher/app/domain/model/LocationModels.kt` — `UserLocation`, `TrackingSession`, `SafePlace`, `SafePlaceCategory`
- `app/src/main/java/com/safeher/app/core/location/DeviceLocationClient.kt` — FusedLocationProvider wrapper
- `app/src/main/java/com/safeher/app/data/repository/LocationRepositoryImpl.kt` — sharing session, path, offline queue, nearby POIs
- `app/src/main/java/com/safeher/app/feature/maps/MapsViewModel.kt`
- `app/src/main/java/com/safeher/app/feature/maps/MapsScreen.kt`
- `app/src/main/java/com/safeher/app/feature/maps/LiveTrackingViewModel.kt`
- `app/src/main/java/com/safeher/app/feature/maps/LiveTrackingScreen.kt`
- `app/src/main/java/com/safeher/app/feature/maps/LocationPermissionScreen.kt`
- `app/src/main/java/com/safeher/app/feature/maps/NearbySafePlacesScreen.kt` (+ `NearbySafePlacesViewModel`)
- `app/src/test/java/com/safeher/app/data/repository/LocationRepositoryImplTest.kt`
- `app/src/test/java/com/safeher/app/feature/maps/MapsViewModelTest.kt`
- `app/src/test/java/com/safeher/app/feature/maps/LiveTrackingViewModelTest.kt`
- `app/src/test/java/com/safeher/app/feature/maps/LocationPermissionStateTest.kt`

### Files Modified
- `domain/repository/Repositories.kt` — expanded `LocationRepository` (observe, share, nearby, flush)
- `di/AppModules.kt` — binds dedicated `LocationRepositoryImpl`
- `data/repository/RepositoriesImpl.kt` — removed inline LocationRepositoryImpl
- `core/ui/navigation/Route.kt` — `LiveTracking`, `NearbyPlaces`
- `core/ui/SafeHerAppRoot.kt` — Maps / Live / Nearby navigation
- `feature/sos/SosViewModel.kt` — auto `startSharing(alertId)` after successful SOS
- `feature/home/DashboardViewModel.kt` + `DashboardScreen.kt` — GPS status, last update, Open Live Map
- `AndroidManifest.xml` — `ACCESS_BACKGROUND_LOCATION`, Maps API key meta-data
- `gradle/libs.versions.toml` — maps-compose, play-services-maps
- `app/build.gradle.kts` — maps deps; `MAPS_API_KEY` from `local.properties`
- `local.properties` — `MAPS_API_KEY` placeholder (not committed secrets)
- Dashboard / SOS tests updated for LocationRepository

### APIs Integrated
- `POST /api/v1/location/update` — upload coordinates when an active alert exists
- `GET /api/v1/location/track-link/{alertId}` — shareable track URL for live session

**Not invented (backend does not expose these):**
- `GET /location/current`, `POST /location/start-sharing`, `POST /location/stop-sharing`, `GET /location/tracking/{sessionId}`

Client-side `TrackingSession` + FusedLocation updates cover sharing; backend upload only when `alertId` is set.

### Architecture Decisions
- Live sharing is a client session; backend requires an active alert for `POST /location/update`.
- Nearby safe places use curated relative POIs (no Places API / backend yet).
- Google Maps key loaded from `local.properties` → BuildConfig + manifest placeholder (never hard-coded).
- Offline: pending location updates queued and flushed via `NetworkMonitor` when online.
- Battery: FusedLocationProvider, ~5s interval, tracking job cancelled on `stopSharing`.
- SOS: successful trigger starts sharing automatically and keeps updating while alert is active.
- Camera follow pauses when the user manually pans the map.

### Testing
- LocationRepositoryImplTest — current location, validation, track link, nearby, offline queue, start/stop
- MapsViewModelTest — permission, sharing confirm, traffic toggle, follow camera
- LiveTrackingViewModelTest — auto start, stop, follow camera
- LocationPermissionStateTest — granted / denied / permanently denied branching

### Remaining Work
- Add a real Google Maps API key in `local.properties` (`MAPS_API_KEY=...`) for map tiles on device.
- Backend Places / start-sharing endpoints if server-side session management is required later.
- Optional foreground location service for background sharing reliability.
- Instrumentation tests for permission launcher flows.

### Build Status
- `assembleDebug`: successful
- APK output: `app/build/outputs/apk/debug/app-debug.apk`

## Phase 7 - Emergency Contacts

### Files Created
- `app/src/main/java/com/safeher/app/domain/model/ContactModels.kt`
- `app/src/main/java/com/safeher/app/feature/contacts/util/ContactValidator.kt`
- `app/src/main/java/com/safeher/app/feature/contacts/ContactsViewModel.kt`
- `app/src/main/java/com/safeher/app/feature/contacts/ContactsScreen.kt`
- `app/src/main/java/com/safeher/app/feature/contacts/AddContactViewModel.kt`
- `app/src/main/java/com/safeher/app/feature/contacts/AddContactScreen.kt`
- `app/src/main/java/com/safeher/app/feature/contacts/ContactDetailsBottomSheet.kt`
- `app/src/test/java/com/safeher/app/feature/contacts/util/ContactValidatorTest.kt`
- `app/src/test/java/com/safeher/app/feature/contacts/ContactsViewModelTest.kt`

### Files Modified
- `domain/repository/Repositories.kt` — extracted `ContactRepository` from `UserRepository`
- `data/repository/RepositoriesImpl.kt` — added `ContactRepositoryImpl` (add/update/delete/setPrimary + Room cache)
- `di/AppModules.kt` — bound ContactRepository; logging reduced to BASIC (no phone bodies in logs)
- `core/ui/navigation/Route.kt` — `AddContact`, `EditContact`
- `core/ui/SafeHerAppRoot.kt` — wired Contacts / Add / Edit screens
- `feature/home/DashboardViewModel.kt` — uses ContactRepository for preview
- `feature/sos/SosViewModel.kt` + `SosScreen.kt` — blocks SOS when no contacts; navigates to Add Contact
- `AndroidManifest.xml` — `READ_CONTACTS`
- Tests updated for ContactRepository / SOS no-contact flow

### APIs Integrated
- `GET /api/v1/users/contacts`
- `POST /api/v1/users/contacts`
- `DELETE /api/v1/users/contacts/{id}`
- Edit / Set Primary use delete+create (backend has no PUT endpoint)

### Architecture Decisions
- Dedicated `ContactRepository` keeps contact logic out of `UserRepository` without duplicating Room/API.
- Backend max of 5 contacts enforced client-side via `AppConstants.MAX_EMERGENCY_CONTACTS` + validator.
- Contact picker only imports the single selected contact after runtime `READ_CONTACTS` grant.
- Dashboard still shows top 3 contacts via Room Flow — updates automatically.
- SOS requires ≥1 contact before confirmation sheet.

### Testing
- ContactValidatorTest (8)
- ContactsViewModelTest (4)
- ContactRepositoryImplTest (3)
- SosViewModelTest updated for no-contacts dialog

### Remaining Work
- Backend PUT `/contacts/{id}` would simplify edit/set-primary (currently delete+recreate).
- Optional encrypted Room fields for phone numbers at rest.
- Auto sync worker when connectivity returns (architecture ready via NetworkMonitor).

### Build Status
- `assembleDebug`: successful
- APK output: `app/build/outputs/apk/debug/app-debug.apk`

## Phase 6 - SOS Module

### Files Created
- `app/src/main/java/com/safeher/app/feature/sos/SosViewModel.kt`
- `app/src/main/java/com/safeher/app/feature/sos/SosScreen.kt`
- `app/src/test/java/com/safeher/app/feature/sos/SosViewModelTest.kt`

### Files Modified
- `app/src/main/AndroidManifest.xml` — added `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`, `POST_NOTIFICATIONS`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_LOCATION`, `VIBRATE` permissions
- `app/src/main/java/com/safeher/app/core/ui/SafeHerAppRoot.kt` — wired `SosScreen` replacing placeholder
- `gradle/libs.versions.toml` — added `play-services-location`, `kotlinx-coroutines-play-services`
- `app/build.gradle.kts` — added location dependencies

### Backend APIs Used
- `POST /api/v1/alerts/trigger` — via `AlertRepository.trigger()`
- `POST /api/v1/alerts/cancel/{alertId}` — via `AlertRepository.cancel()`
- `GET /api/v1/alerts/active` — via `AlertRepository.getActive()`
- `GET /api/v1/alerts/history` — via `AlertRepository.getHistory()`
- `POST /api/v1/location/update` — via `LocationRepository.updateLocation()`

### Features Added
- Confirmation bottom sheet before SOS trigger
- 5-second animated countdown with cancel option
- Haptic feedback during countdown and trigger
- Sending progress overlay
- Success screen with status checklist (SOS, location, contacts, police, hospital)
- Failure screen with retry
- SOS dashboard card with network/location/accuracy readiness
- Active alert display and cancel support
- SOS history list with color-coded status
- Empty history state
- Offline banner
- Location permission request flow (runtime)
- Tap debounce to prevent duplicate triggers
- Fused location provider (GPS) integration

### Tests Added
- `SosViewModelTest` — 8 tests: initial state, confirming, countdown, cancel, success, failure, debounce, cancel active alert

### Architecture Decisions
- Single `SosViewModel` manages full SOS lifecycle via `SosPhase` state machine (IDLE → CONFIRMING → COUNTDOWN → SENDING → SUCCESS/FAILURE)
- Full-screen overlays for countdown/sending/success/failure to prevent accidental navigation during emergency
- Haptic feedback via `Vibrator` / `VibratorManager` (best-effort)
- Location fetched via `FusedLocationProviderClient` with coroutine `await()` — fails silently, SOS proceeds without location
- Active alert check on screen open prevents stacking duplicates
- Reuses design system: `SafeHerDangerButton`, `SafeHerOutlinedButton`, `SafeHerEmergencyCard`, `SafeHerStatusCard`, `SafeHerShimmerCard`, `SafeHerTopAppBar`, `SafeHerIcon`, `SafeHerCircularLoader`, `SafeHerTextButton`, `SafeHerPrimaryButton`

### Remaining Work
- Foreground service for persistent SOS monitoring (Phase 12/13)
- WorkManager retry for offline queued SOS
- Sound/alarm during countdown when audio assets are available
- Notification channel creation for SOS alerts (Phase 12)

### Build Status
- `assembleDebug`: successful
- APK output: `app/build/outputs/apk/debug/app-debug.apk`

## Phase 5 - Home Dashboard

### Files Created
- `app/src/main/java/com/safeher/app/feature/home/DashboardViewModel.kt`
- `app/src/main/java/com/safeher/app/feature/home/DashboardScreen.kt`
- `app/src/main/java/com/safeher/app/feature/auth/session/SessionExpiredScreen.kt`
- `app/src/main/java/com/safeher/app/core/network/NetworkMonitor.kt`
- `app/src/test/java/com/safeher/app/feature/home/DashboardViewModelTest.kt`
- `app/src/test/java/com/safeher/app/data/repository/RepositoryTests.kt`

### Files Modified
- `app/src/main/java/com/safeher/app/core/ui/SafeHerAppRoot.kt` — wired Dashboard + navigation-ready placeholders for Sos/Contacts/Maps/Ai/Profile/Activity; Session Expired route
- `app/src/main/java/com/safeher/app/core/ui/navigation/Route.kt` — added `SessionExpired`
- `app/src/main/java/com/safeher/app/core/designsystem/component/Cards.kt` — added `SafeHerActionCard`; extended `SafeHerStatusCard` icon param and `SafeHerEmergencyCard` click
- `app/src/main/java/com/safeher/app/core/designsystem/component/Buttons.kt` — pulsed `SafeHerSosFab`
- `app/src/main/java/com/safeher/app/core/designsystem/icon/SafeHerIcons.kt` — Map/History/Mic/Hospital/Police/Wifi and related icons; AutoMirrored Back
- `app/src/main/java/com/safeher/app/core/datastore/UserPreferences.kt` — exposed `userPhone` Flow

### Dependencies Added
- None (reused existing Material Icons Extended, MockK, Coroutines Test)

### APIs Used
- `GET /api/v1/users/profile` — via `UserRepository.getProfile()`
- `GET /api/v1/users/contacts` — via `UserRepository.refreshContacts()` / `observeContacts()`
- `GET /api/v1/alerts/history` — via `AlertRepository.getHistory()`

### Architecture Decisions
- Dashboard lives in `feature/home` with a single ViewModel owning greeting, safety status, contacts preview, activity, tips, offline state, and logout.
- Extended the design system instead of duplicating cards/FAB (`SafeHerActionCard`, pulsed SOS FAB).
- Quick actions and bottom nav are navigation-ready; destinations show phase placeholders until later modules land.
- Offline UX uses `NetworkMonitor` + banner + cached DataStore name/Room contacts.
- Logout uses existing `SafeHerWarningDialog`; session-expired screen is ready for 401 wiring.
- Weather and nearby safe places use placeholders when backend data is unavailable.

### Remaining Work
- Phase 6 SOS flow (replace SOS placeholder / FAB target).
- Real maps, contacts, AI, and profile feature modules.
- Wire 401 interceptor to Session Expired route.
- Battery status from system APIs when permissions/policy allow.
- Weather API if product decides to add one.

### Build Status
- `assembleDebug`: successful
- APK output: `app/build/outputs/apk/debug/app-debug.apk`

## Phase 4 - Authentication Module

### Files Created
- `app/src/main/java/com/safeher/app/feature/auth/util/AuthValidator.kt`
- `app/src/main/java/com/safeher/app/feature/auth/splash/SplashViewModel.kt`
- `app/src/main/java/com/safeher/app/feature/auth/splash/SplashScreen.kt`
- `app/src/main/java/com/safeher/app/feature/auth/onboarding/OnboardingViewModel.kt`
- `app/src/main/java/com/safeher/app/feature/auth/onboarding/OnboardingScreen.kt`
- `app/src/main/java/com/safeher/app/feature/auth/login/LoginViewModel.kt`
- `app/src/main/java/com/safeher/app/feature/auth/login/LoginScreen.kt`
- `app/src/main/java/com/safeher/app/feature/auth/register/RegisterViewModel.kt`
- `app/src/main/java/com/safeher/app/feature/auth/register/RegisterScreen.kt`
- `app/src/main/java/com/safeher/app/feature/auth/otp/OtpViewModel.kt`
- `app/src/main/java/com/safeher/app/feature/auth/otp/OtpScreen.kt`
- `app/src/test/java/com/safeher/app/feature/auth/util/AuthValidatorTest.kt`
- `app/src/test/java/com/safeher/app/feature/auth/login/LoginViewModelTest.kt`
- `app/src/test/java/com/safeher/app/feature/auth/register/RegisterViewModelTest.kt`

### Files Modified
- `app/src/main/java/com/safeher/app/core/ui/SafeHerAppRoot.kt` — replaced showcase routes with full auth navigation graph

### APIs Integrated
- `POST /api/v1/auth/register` — via `AuthRepository.register()`
- `POST /api/v1/auth/login` — via `AuthRepository.login()`
- `POST /api/v1/auth/send-otp` — via `AuthRepository.sendOtp()`
- `POST /api/v1/auth/verify-otp` — via `AuthRepository.verifyOtp()`

### Architecture Decisions
- Each screen has its own ViewModel with `StateFlow<UiState>` + `SharedFlow<Event>` for one-shot navigation events.
- Centralised validation in `AuthValidator` — reused by all auth ViewModels and tested independently.
- Splash screen determines start destination (Onboarding → Login → Home) based on DataStore prefs and `SecureTokenStore`.
- Onboarding uses `HorizontalPager` (Material 3) and persists completion to DataStore.
- OTP screen uses `BasicTextField` with custom decoration for individual digit boxes, auto-submits on 6 digits.
- Register screen includes real-time password strength indicator.
- All screens reuse design system components (`SafeHerTextField`, `SafeHerPasswordField`, `SafeHerPhoneField`, `SafeHerLoadingButton`, `SafeHerGradientButton`, `SafeHerTopAppBar`, `SafeHerTextButton`, `SafeHerIcon`).
- Tests use MockK + kotlinx-coroutines-test (already in version catalog).

### Remaining Work
- Add Lottie animations for splash/success when JSON assets are available.
- Session expired screen and logout dialog (will be wired in Dashboard phase).
- 401 interceptor for auto-logout (will be added alongside refresh token support in Phase 5+).

### Build Status
- `assembleDebug`: successful
- APK output: `app/build/outputs/apk/debug/app-debug.apk`

## Phase 3 - Design System

### Files Created
- `app/src/main/java/com/safeher/app/core/designsystem/theme/ColorTokens.kt`
- `app/src/main/java/com/safeher/app/core/designsystem/theme/DesignTokens.kt`
- `app/src/main/java/com/safeher/app/core/designsystem/icon/SafeHerIcons.kt`
- `app/src/main/java/com/safeher/app/core/designsystem/animation/SafeHerAnimations.kt`
- `app/src/main/java/com/safeher/app/core/designsystem/component/Buttons.kt`
- `app/src/main/java/com/safeher/app/core/designsystem/component/TextFields.kt`
- `app/src/main/java/com/safeher/app/core/designsystem/component/Cards.kt`
- `app/src/main/java/com/safeher/app/core/designsystem/component/DialogsAndLoading.kt`
- `app/src/main/java/com/safeher/app/core/designsystem/component/AppChrome.kt`
- `app/src/main/java/com/safeher/app/core/designsystem/component/DesignSystemShowcaseScreen.kt`

### Files Modified
- `app/build.gradle.kts`
- `gradle/libs.versions.toml`
- `app/src/main/java/com/safeher/app/core/designsystem/theme/Theme.kt`
- `app/src/main/java/com/safeher/app/core/ui/SafeHerAppRoot.kt`

### Dependencies Added
- `com.airbnb.android:lottie-compose`

### Architecture Decisions
- Kept a single `:app` module and expanded the `core/designsystem` package instead of introducing extra UI modules prematurely.
- Built the design system around Material 3 with SafeHer-specific composition locals for spacing, radii, elevations, and extended semantic colors.
- Added a dedicated internal showcase screen so the component library can be validated visually before feature modules are implemented.
- Reused simple wrapper components instead of deep abstraction layers to keep the codebase approachable for a solo developer.

### Remaining Work
- Connect the design-system components to real feature flows beginning with Phase 4 authentication.
- Add branded Lottie JSON assets when motion direction is finalized.
- Replace the temporary Phase 3 showcase routes with real screen navigation as feature modules land.

### Build Status
- `assembleDebug`: successful
- APK output: `app/build/outputs/apk/debug/app-debug.apk`
