"""
SafeHer — Step 1: Dataset Preparation & Augmentation
======================================================

What this does:
  1. Reads all WAV files from data/raw/distress/ and data/raw/normal/
  2. Splits every file into 1-second chunks (what the model expects)
  3. Normalizes audio levels
  4. Augments distress chunks 8x using background noise, pitch, speed
  5. Saves everything to data/processed/
  6. Creates data/splits/ with train/val/test CSV manifests
  7. Prints a final summary

Run AFTER 00_convert_audio.py:
    pip install librosa soundfile numpy pandas scikit-learn tqdm
    python 01_prepare_dataset.py
"""

import os
import numpy as np
import librosa
import soundfile as sf
import pandas as pd
from pathlib import Path
from tqdm import tqdm
from sklearn.model_selection import train_test_split

# Local imports
try:
    from dataset_metadata import infer_metadata, binary_train_label
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from dataset_metadata import infer_metadata, binary_train_label

# ── Config ────────────────────────────────────────────────────────────────────

SAMPLE_RATE   = 16000   # Must match inference.py
CHUNK_SECONDS = 1
CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_SECONDS

RAW_DISTRESS_DIR = Path("data/raw/distress")
RAW_NORMAL_DIR   = Path("data/raw/normal")
RAW_NOISE_DIR    = Path("data/raw/noise")
SPEECH_EMERGENCY_DIR = Path("data/speech/emergency_phrases")
SPEECH_NORMAL_DIR = Path("data/speech/normal")
PROCESSED_DIR    = Path("data/processed")
SPLITS_DIR       = Path("data/splits")
METADATA_DIR     = Path("data/metadata")

# Augmentation noise levels (how loud background is mixed in)
NOISE_LEVELS = [0.10, 0.20, 0.35]

# Split ratios
TRAIN_RATIO = 0.75
VAL_RATIO   = 0.15
TEST_RATIO  = 0.10

# Drop chunks below this RMS energy (silence)
SILENCE_THRESHOLD = 0.005


# ── Audio utilities ───────────────────────────────────────────────────────────

def load_audio(path):
    audio, _ = librosa.load(str(path), sr=SAMPLE_RATE, mono=True)
    return audio.astype(np.float32)


def normalize(audio):
    peak = np.abs(audio).max()
    if peak > 0:
        audio = audio / peak * 0.9
    return audio


def split_chunks(audio):
    chunks = []
    for start in range(0, len(audio), CHUNK_SAMPLES):
        chunk = audio[start : start + CHUNK_SAMPLES]
        if len(chunk) < CHUNK_SAMPLES:
            chunk = np.pad(chunk, (0, CHUNK_SAMPLES - len(chunk)))
        if np.sqrt(np.mean(chunk ** 2)) < SILENCE_THRESHOLD:
            continue
        chunks.append(chunk)
    return chunks


def save_wav(chunk, path):
    sf.write(str(path), chunk, SAMPLE_RATE, subtype="PCM_16")


def load_noise_chunk(noise_dir):
    files = list(noise_dir.glob("*.wav"))
    if not files:
        return np.zeros(CHUNK_SAMPLES, dtype=np.float32)
    path  = np.random.choice(files)
    noise = load_audio(path)
    if len(noise) >= CHUNK_SAMPLES:
        start = np.random.randint(0, len(noise) - CHUNK_SAMPLES)
        noise = noise[start : start + CHUNK_SAMPLES]
    else:
        noise = np.tile(noise, (CHUNK_SAMPLES // len(noise)) + 1)[:CHUNK_SAMPLES]
    return normalize(noise).astype(np.float32)


# ── Augmentation ──────────────────────────────────────────────────────────────

def augment(chunk, noise_dir):
    """
    Returns 8 versions of one chunk:
      aug_0 = original
      aug_1 = + light noise   (10%)
      aug_2 = + medium noise  (20%)
      aug_3 = + heavy noise   (35%)
      aug_4 = pitch shift up  +2 semitones  (higher voice)
      aug_5 = pitch shift down -2 semitones (lower voice)
      aug_6 = speed up 1.1x   (panic)
      aug_7 = slow down 0.9x  (suppressed)
    """
    versions = [chunk.copy()]

    for level in NOISE_LEVELS:
        noise  = load_noise_chunk(noise_dir)
        mixed  = normalize((1 - level) * chunk + level * noise)
        versions.append(mixed)

    for steps in [2, -2]:
        try:
            shifted = librosa.effects.pitch_shift(chunk, sr=SAMPLE_RATE, n_steps=steps)
            versions.append(normalize(shifted))
        except Exception:
            versions.append(chunk.copy())

    for rate in [1.1, 0.9]:
        try:
            stretched = librosa.effects.time_stretch(chunk, rate=rate)[:CHUNK_SAMPLES]
            if len(stretched) < CHUNK_SAMPLES:
                stretched = np.pad(stretched, (0, CHUNK_SAMPLES - len(stretched)))
            versions.append(normalize(stretched))
        except Exception:
            versions.append(chunk.copy())

    return versions


# ── Processing ────────────────────────────────────────────────────────────────

def process_class(raw_dir, out_dir, label, do_augment, noise_dir):
    label_name = "distress" if label == 1 else "normal"
    out_dir.mkdir(parents=True, exist_ok=True)

    wav_files = sorted(raw_dir.rglob("*.wav")) if raw_dir.exists() else []
    if not wav_files:
        print(f"  !! No WAV files in {raw_dir}")
        return []

    print(f"\n  [{label_name.upper()}]  {len(wav_files)} source files")
    records = []

    for wav_path in tqdm(wav_files, desc=f"  {label_name}"):
        try:
            meta = infer_metadata(wav_path)
            # Skip RAVDESS/SUPPORT from binary training target (keep metadata for analysis)
            mapped = binary_train_label(meta)
            if mapped is None:
                continue
            use_label = mapped if label is None else label

            audio   = normalize(load_audio(wav_path))
            chunks  = split_chunks(audio)
            speaker = meta.get("participant_id") or "spk000"

            for c_idx, chunk in enumerate(chunks):
                versions = augment(chunk, noise_dir) if do_augment else [chunk]

                for a_idx, version in enumerate(versions):
                    fname     = f"{label_name}_{wav_path.stem}_c{c_idx:03d}_a{a_idx}.wav"
                    save_path = out_dir / fname
                    save_wav(version, save_path)
                    records.append({
                        "filepath":  str(save_path),
                        "label":     use_label,
                        "source":    wav_path.name,
                        "speaker":   speaker,
                        "chunk_idx": c_idx,
                        "aug_idx":   a_idx,
                        "signal_type": meta.get("signal_type", ""),
                        "language": meta.get("language", ""),
                        "phrase": meta.get("phrase", ""),
                        "emotion": meta.get("emotion", ""),
                        "class_name": meta.get("class", ""),
                        "source_dataset": meta.get("source", ""),
                        "participant_id": meta.get("participant_id", speaker),
                        "session_id": meta.get("session_id", ""),
                        "original_path": str(wav_path),
                    })

        except Exception as e:
            print(f"\n  XX Skipped {wav_path.name}: {e}")

    print(f"     -> {len(records)} processed samples")
    return records


# ── Train / Val / Test split ──────────────────────────────────────────────────

def split_dataset(df):
    """
    Split by SOURCE FILE not by chunk — prevents data leakage.
    Chunks from the same recording never appear in both train and test.
    """
    sources    = df["source"].unique()
    src_labels = df.groupby("source")["label"].first().loc[sources].values

    src_train, src_valtest = train_test_split(
        sources, test_size=(VAL_RATIO + TEST_RATIO),
        random_state=42, stratify=src_labels
    )
    vt_labels = df.groupby("source")["label"].first().loc[src_valtest].values
    src_val, src_test = train_test_split(
        src_valtest,
        test_size=TEST_RATIO / (VAL_RATIO + TEST_RATIO),
        random_state=42, stratify=vt_labels
    )

    return (
        df[df["source"].isin(src_train)].reset_index(drop=True),
        df[df["source"].isin(src_val)].reset_index(drop=True),
        df[df["source"].isin(src_test)].reset_index(drop=True),
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  SafeHer — Dataset Preparation Pipeline (multi-signal)")
    print("=" * 55)

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    # Existing distress/normal trees (DO NOT delete Screaming/)
    distress_records = process_class(RAW_DISTRESS_DIR, PROCESSED_DIR / "distress", 1, False, RAW_NOISE_DIR)
    normal_records   = process_class(RAW_NORMAL_DIR,   PROCESSED_DIR / "normal",   0, False, RAW_NOISE_DIR)

    # New speech layouts (additive)
    speech_emergency = process_class(SPEECH_EMERGENCY_DIR, PROCESSED_DIR / "distress", 1, False, RAW_NOISE_DIR)
    speech_normal = process_class(SPEECH_NORMAL_DIR, PROCESSED_DIR / "normal", 0, False, RAW_NOISE_DIR)

    all_records = distress_records + normal_records + speech_emergency + speech_normal

    if not all_records:
        print("\n  XX No audio files found. Add WAV files to data/raw/ or data/speech/ first.")
        return

    df = pd.DataFrame(all_records)
    df.to_csv(PROCESSED_DIR / "manifest.csv", index=False)
    df.to_csv(METADATA_DIR / "sources_manifest.csv", index=False)

    splits_ok = False
    try:
        train_df, val_df, test_df = split_dataset(df)
        train_df.to_csv(SPLITS_DIR / "train.csv", index=False)
        val_df.to_csv(SPLITS_DIR   / "val.csv",   index=False)
        test_df.to_csv(SPLITS_DIR  / "test.csv",  index=False)
        splits_ok = True
    except ValueError as e:
        print(f"\n  !! Split failed (need more files): {e}")

    # Summary
    n_distress = len(df[df["label"] == 1])
    n_normal   = len(df[df["label"] == 0])
    n_speakers = df["speaker"].nunique()
    n_phrase = len(df[df.get("signal_type", pd.Series(dtype=str)) == "emergency_phrase"]) if "signal_type" in df.columns else 0

    print("\n" + "=" * 55)
    print("  DATASET SUMMARY")
    print("=" * 55)
    print(f"  Distress samples  : {n_distress}")
    print(f"  Normal samples    : {n_normal}")
    print(f"  Emergency phrase  : {n_phrase}")
    print(f"  Total             : {len(df)}")
    print(f"  Unique speakers   : {n_speakers}")

    if splits_ok:
        print(f"\n  Train  : {len(train_df)}")
        print(f"  Val    : {len(val_df)}")
        print(f"  Test   : {len(test_df)}")

    print()
    if n_distress < 200:
        print(f"  !! {n_distress} distress samples — target 800+ before training")
    else:
        print("  OK — run: python 02_train_model.py")
    if n_speakers < 5:
        print(f"  !! Only {n_speakers} speakers — collect from more volunteers")
    print("  Note: RAVDESS/emotional clips are SUPPORT only (excluded from binary labels).")
    print("=" * 55)


if __name__ == "__main__":
    main()
