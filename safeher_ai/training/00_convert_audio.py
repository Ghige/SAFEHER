"""
SafeHer — Step 0: Audio Format Converter
=========================================

Run this BEFORE the pipeline if you have MP3, M4A, FLAC, or OGG files.
Converts everything in data/raw/ to 16kHz mono WAV in-place.

Why: The pipeline only reads WAV. Volunteers may send WhatsApp voice notes
(.opus), M4A, or MP3 — this handles all of them.

Usage:
    pip install librosa soundfile tqdm
    python 00_convert_audio.py

What it does:
    Scans data/raw/distress/, data/raw/normal/, data/raw/noise/
    Converts any non-WAV file to WAV (16kHz mono)
    Keeps original file untouched, saves converted as .wav
    Skips files already in WAV format
"""

import os
import librosa
import soundfile as sf
from pathlib import Path
from tqdm import tqdm

SAMPLE_RATE = 16000
RAW_DIRS = [
    Path("data/raw/distress"),
    Path("data/raw/normal"),
    Path("data/raw/noise"),
]
SUPPORTED = {".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".aiff"}


def convert_file(src_path: Path) -> bool:
    """Convert one audio file to 16kHz mono WAV. Returns True if converted."""
    out_path = src_path.with_suffix(".wav")
    if out_path.exists():
        return False  # already converted

    try:
        audio, _ = librosa.load(str(src_path), sr=SAMPLE_RATE, mono=True)
        sf.write(str(out_path), audio, SAMPLE_RATE, subtype="PCM_16")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {src_path.name} — {e}")
        return False


def main():
    print("=" * 50)
    print("  SafeHer — Audio Format Converter")
    print("=" * 50)

    total_found = 0
    total_converted = 0

    for raw_dir in RAW_DIRS:
        if not raw_dir.exists():
            continue

        non_wav = [
            f for f in raw_dir.iterdir()
            if f.suffix.lower() in SUPPORTED
        ]

        if not non_wav:
            print(f"\n  ✅ {raw_dir.name}/ — all files already WAV")
            continue

        print(f"\n  📁 {raw_dir.name}/ — {len(non_wav)} files to convert")
        total_found += len(non_wav)

        for f in tqdm(non_wav, desc=raw_dir.name):
            if convert_file(f):
                total_converted += 1

    print(f"\n  Done. Converted {total_converted}/{total_found} files.")
    print("  Now run: python 01_prepare_dataset.py")


if __name__ == "__main__":
    main()
