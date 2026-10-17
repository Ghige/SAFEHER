# SafeHer Speech / Emergency Phrase Dataset Layout

See also: `data/speech/` on disk (audio files gitignored).

```
data/speech/
  emergency_phrases/{english,hindi,marathi}/<phrase>/*.wav
  normal/{english,hindi,marathi}/*.wav
data/raw/distress/Screaming/     # KEEP acoustic distress
data/raw/emotional/ravdess/      # SUPPORT only — not auto emergency
```

RAVDESS = emotional support. Normal speech = hard negatives. Never train only on emergency phrases.
