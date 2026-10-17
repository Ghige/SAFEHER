# SafeHer AI Data Collection

**Status:** Metadata-only cloud feedback is implemented. Raw WAV upload is retired (HTTP 410). AI predictions never become GOLD automatically. Retraining is never automatic.

See repository root:

- `CONTINUOUS_AI_DATA_PIPELINE.md`
- `AI_FEEDBACK_DATA_SCHEMA.md`
- `AI_DATA_REVIEW_POLICY.md`
- `AI_RETRAINING_GATES.md`

Opt-in remains **off by default** (`Help improve AI`). Consent version: `privacy-v2-metadata-only`.

The older RC1 local-WAV capture design below is **not** the production path. Do not upload microphone recordings.

## Legacy RC1 notes (not implemented as a WAV pipeline)

Local SOS sensor capture remains a future, separately consented feature. It must not contradict the in-app privacy policy (no raw microphone upload unless a compliant extra consent exists).
