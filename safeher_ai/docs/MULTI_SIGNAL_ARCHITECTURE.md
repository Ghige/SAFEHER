# SafeHer Multi-Signal AI Architecture

Evolves SafeHer from single-audio / volume-gated decisions to:

```
Audio ──► Distress/Scream Model ──┐
      ──► Emergency Phrase Detect─┼──► Safety Decision Engine ──► Existing SOS flow
Movement ► Movement Model ────────┘         LOW / MEDIUM / HIGH
```

## Rules

- Volume/RMS is a **feature**, never sole SOS trigger.
- Quiet "help me" can escalate via **phrase_score**.
- Loud normal speech without distress/phrase must **not** SOS.
- Movement-only (running, transit) must **not** auto SOS.
- RAVDESS = emotional **support** data — not auto-labelled emergency.
- Existing TFLite distress model + SOS/WhatsApp/location flow are **preserved**.

## Key modules

| Layer | Path |
|-------|------|
| SDE (server) | `safeher_backend/app/ai/safety_decision_engine.py` |
| Phrase detect | `safeher_backend/app/ai/speech_phrase_detector.py` |
| Compat scorer | `safeher_backend/app/ai/confidence_scorer.py` |
| SDE (Android) | `.../services/ai/SafetyDecisionEngine.kt` |
| Phrase (Android) | `EmergencyPhraseDetector.kt` + `EmergencyPhraseCatalog.kt` |
| Risk gate | `AudioRiskEvaluator.kt` (volume not required for HIGH) |
| Dataset meta | `safeher_ai/training/dataset_metadata.py` |
| Speech layout | `safeher_ai/data/speech/` + `docs/SPEECH_DATASET.md` |

## Thresholds

All risk thresholds are **TEMPORARY development defaults** in `SafetyDecisionConfig` / Kotlin constants — tune with validation data; do not treat as final product accuracy.

## On-device ASR

Phrase detection currently scores a **transcript** (`AudioHybridPipeline.latestTranscript`). Wire ASR later without changing the SDE contract.

## Remaining work

- Collect real phrase + normal-speech hard negatives
- Optional on-device ASR
- Enable movement model when TFLite + scaler are ready (`AiFeatureFlags.MOVEMENT_AI_ENABLED`)
- Background/wallet always-on monitoring (still foreground-gated)
- Retrain with multi-signal metadata; never claim synthetic movement accuracy as real-world
