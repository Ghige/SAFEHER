# SafeHer — AI Training Pipeline

Complete pipeline from raw audio → on-device TFLite model.

---

## Folder Structure

```
safeher_ai/
│
├── data/
│   ├── raw/
│   │   ├── distress/          ← DROP YOUR DISTRESS FILES HERE (label = 1)
│   │   ├── normal/            ← DROP YOUR NORMAL FILES HERE  (label = 0)
│   │   └── noise/             ← DROP BACKGROUND NOISE HERE   (no label)
│   │
│   ├── processed/             ← pipeline fills this (chunked + augmented)
│   └── splits/                ← pipeline fills this (train/val/test CSVs)
│
├── models/
│   ├── checkpoints/           ← saved during training
│   └── final/
│       ├── yamnet_distress.tflite        ← copy to app after training
│       └── yamnet_distress_quant.tflite  ← smaller, recommended for prod
│
├── training/
│   ├── 00_convert_audio.py    ← Step 0: MP3/M4A → WAV
│   ├── 01_prepare_dataset.py  ← Step 1: chunk + augment + split
│   ├── 02_train_model.py      ← Step 2: fine-tune YAMNet
│   ├── 03_evaluate_model.py   ← Step 3: test accuracy + confusion matrix
│   └── 04_export_tflite.py    ← Step 4: export for Android
│
├── logs/                      ← training logs + TensorBoard
├── evaluation/                ← evaluation reports
└── requirements_training.txt
```

---

## Labeling — How It Works

**Folder = Label. That's it.**

```
data/raw/distress/  →  label 1  (danger)
data/raw/normal/    →  label 0  (safe)
data/raw/noise/     →  augmentation only (no label)
```

Read `data/raw/LABELING_GUIDE.md` for full naming conventions.

---

## File Naming Convention

```
[source]_[language]_[type]_[speaker_id]_[take].wav

Examples:
  vol_mr_scream_spk01_t1.wav    → volunteer, Marathi, screaming
  vol_hi_whisper_spk02_t1.wav   → volunteer, Hindi, whispered distress
  hnd_hi_conv_spk200_t1.wav     → hindi-asr-benchmark, normal speech
  sel_xx_auto_loc01_t1.wav      → self-recorded auto noise
```

---

## Steps to Run

### Setup (one time)
```bash
pip install -r requirements_training.txt
```

### Step 0 — Convert audio formats (if you have MP3/M4A/OGG)
```bash
cd training
python 00_convert_audio.py
```

### Step 1 — Prepare dataset (chunk + augment + split)
```bash
python 01_prepare_dataset.py
```
Output:
```
DATASET SUMMARY
  Distress samples  : 850
  Normal samples    : 620
  Total             : 1470
  Unique speakers   : 12
  Train  : 1102
  Val    : 220
  Test   : 148
✅ Ready — run: python 02_train_model.py
```

### Step 2 — Train the model
```bash
python 02_train_model.py
```
Takes 30-90 minutes depending on dataset size and GPU.
Saves best model to `models/final/`

### Step 3 — Evaluate
```bash
python 03_evaluate_model.py --model models/final/safeher_audio_YYYYMMDD_HHMM.keras
```
Check that Recall >= 0.85 before proceeding.

### Step 4 — Export to TFLite
```bash
python 04_export_tflite.py --model models/final/safeher_audio_YYYYMMDD_HHMM.keras
```

### Step 5 — Copy to app
```bash
cp models/final/yamnet_distress_quant.tflite ../app/ai/audio_model/yamnet_distress.tflite
```

Done. The app's `inference.py` loads this file automatically.

---

## Minimum Dataset Before Training

| Folder       | Minimum | Good  | Great  |
|-------------|---------|-------|--------|
| distress/   | 100     | 200   | 350+   |
| normal/     | 150     | 300   | 500+   |
| noise/      | 10      | 20    | 30+    |

With 8x augmentation: 100 distress raw → ~800 training samples.

---

## What to Check in Evaluation

| Metric    | Minimum | Target | Meaning |
|-----------|---------|--------|---------|
| Recall    | 0.80    | 0.90+  | % of real distress caught |
| Precision | 0.70    | 0.85+  | % of alerts that were real |
| AUC       | 0.85    | 0.92+  | Overall separation quality |

**Recall is the most important metric for SafeHer.**
Missing real distress is catastrophically worse than a false alarm.
The confirmation window handles false alarms. Nothing handles missed emergencies.

---

## Connecting to the App

The TFLite file connects directly to your existing code:

```
inference.py
  MODEL_PATH = "yamnet_distress.tflite"   ← this file
  predict_distress(audio_chunk) → score 0-100

audio_monitor.py
  score > DISTRESS_THRESHOLD (50)
  → confirmation window
  → SOSEvent → alert_service → WhatsApp + Firebase
```

No other changes needed after replacing the .tflite file.
