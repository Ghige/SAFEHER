# Audio AI — Field Test Checklist (RC1)

Use this checklist before enabling audio AI for production users.

## Prerequisites

- `yamnet_distress_quant.tflite` in `app/src/main/assets/` (from `safeher_ai/models/final/`)
- Microphone permission granted
- AI Monitoring turned **ON** from the AI tab
- Device online for backend fusion (`POST /api/v1/ai/confidence`)

## Threshold alignment

Android TFLite produces a **0–100 distress score**. Backend `confidence_scorer.py` applies:

| Tier | Score | Action |
|------|-------|--------|
| Noise floor | below 60 | Ignored |
| Silent vibration | 40–59 | Haptic only |
| 30s countdown | 60–79 | SOS countdown |
| Immediate SOS | 80+ | Auto-trigger |

Constants live in `AiScoreThresholds.kt` — keep in sync with backend.

## Test matrix

1. **Silence / quiet room** — score should stay below 60; no countdown.
2. **Normal conversation** — should not reach 60 consistently.
3. **Recorded distress sample** (safe playback via speaker, not live harm) — score should rise; note peak value.
4. **Crowded street noise** — watch for false positives; tune backend tiers if needed.
5. **Background app** — inference pauses; mic FGS stops when monitoring OFF.
6. **Monitoring OFF** — no mic foreground service notification.

## Pass criteria

- Model loads (`AI Status` → On-device models: **Ready**)
- Distress sample produces score at least 60 once
- Quiet baseline stays below 60
- No SOS trigger from silence alone
- Confidence card updates every ~3s while monitoring in foreground

## Fail actions

- If model missing: copy asset, rebuild, reinstall
- If scores always 0: check mic permission and 16 kHz buffer in `AudioMonitorService`
- If false positives: raise backend tiers in `confidence_scorer.py` (requires backend approval)

## Log tags (debug builds)

Filter Logcat: `TfliteAudioInferenceEngine`, `AiMonitoringCoordinator`, `AudioMonitorService`
