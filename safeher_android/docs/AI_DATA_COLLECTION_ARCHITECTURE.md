# SafeHer AI Data Collection — Future Architecture (RC1)

**Status:** Design only. No cloud upload in RC1. No background uploads. User must explicitly opt in.

## Purpose

When an SOS is triggered, optionally capture sensor evidence locally to improve future AI models (movement classifier, audio distress detection). Data stays on-device until the user explicitly exports or uploads in a future release.

## Trigger

```
SOS triggered (manual / AI / shake)
        │
        ▼
AiDataCollectionCoordinator.onSosTriggered(alertId)
        │
        ├── SettingsStore.aiDataCollectionEnabled == false → no-op
        └── enabled → start local capture session
```

## Opt-In (required)

| Setting | Storage | Default |
|---------|---------|---------|
| `ai_data_collection_enabled` | DataStore (`SettingsStore`) | `false` |
| Shown in Settings → AI → "Help improve SafeHer" with clear privacy copy | | |

User must enable before any capture. No pre-checked boxes. No capture during normal monitoring.

## Data Captured (optional, on SOS only)

| Stream | Source | Format | Duration |
|--------|--------|--------|----------|
| Accelerometer | `SensorManager` | CSV or binary float32 `[t, ax, ay, az]` @ 10 Hz | 30 s pre + 60 s post |
| Gyroscope | `SensorManager` | CSV or binary float32 `[t, gx, gy, gz]` @ 10 Hz | 30 s pre + 60 s post |
| Microphone snippet | `AudioRecord` | WAV PCM 16 kHz mono | max 10 s, only if mic permission granted |

Pre-buffer: ring buffer always running **only while** opt-in is enabled **and** app is in foreground or active alert — never 24/7 in RC1 design.

## Local Storage

```
/data/data/com.safeher.app/files/ai_datasets/
  sos_{alertId}_{timestamp}/
    manifest.json       # alertId, triggerType, coords, device, consent version
    accelerometer.csv
    gyroscope.csv
    audio.wav           # optional
```

- Encrypted at rest via app-private storage (no SD card).
- Max total size cap (e.g. 50 MB); oldest sessions pruned on low storage.
- No PII in filenames beyond alert UUID.

## Privacy Constraints (RC1 design)

1. No automatic cloud upload.
2. No upload without explicit user action (future: "Export for research" or "Share with SafeHer team").
3. Microphone snippet only on SOS, never continuous recording for dataset purposes.
4. User can delete all captured data from Settings.
5. Consent version stored in `manifest.json` for audit trail.

## Future Pipeline (post-RC1)

```
Local session
      │
      ▼ (user taps Export)
Encrypted zip + checksum
      │
      ▼ (future API, not in RC1)
POST /api/v1/ai/datasets/upload  ← backend frozen for RC1
      │
      ▼
S3 / secure storage → training pipeline (safeher_ai/)
```

## Android Components (to implement later)

| Component | Role |
|-----------|------|
| `AiDataCollectionCoordinator` | Orchestrates SOS-triggered capture |
| `SensorRingBuffer` | Pre-SOS rolling window for accel/gyro |
| `SosDatasetWriter` | Writes manifest + files atomically |
| `AiDatasetStore` | Index of local sessions, delete/export |

## RC1 Action

- This document only.
- No new Gradle dependencies.
- No new permissions beyond existing SOS/AI permissions.
- Wire `AiDataCollectionCoordinator` in a future sprint after RC1 field testing.
