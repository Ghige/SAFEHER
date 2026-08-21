"""
SafeHer — Dataset Preparation V2

Purpose:
    Prepare the downloaded SafeHer audio dataset correctly.

What it does:
    1. Finds WAV files recursively under data/raw/distress and data/raw/normal
    2. Converts/resamples every source recording to 16 kHz mono
    3. Splits each recording into 1-second chunks
    4. Removes near-silent chunks
    5. Keeps source recording identity so train/val/test do not leak chunks
    6. Creates train/val/test CSV manifests
    7. Does NOT augment validation/test data

Important:
    Augmentation should be applied only to training data later.
"""

from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
import librosa
import soundfile as sf
from sklearn.model_selection import train_test_split
from tqdm import tqdm

SAMPLE_RATE = 16000
CHUNK_SECONDS = 1
CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_SECONDS

RAW_ROOT = Path("safeher_ai/data/raw")
DISTRESS_ROOT = RAW_ROOT / "distress"
NORMAL_ROOT = RAW_ROOT / "normal"

PROCESSED_ROOT = Path("safeher_ai/data/processed_v2")
PROCESSED_DISTRESS = PROCESSED_ROOT / "distress"
PROCESSED_NORMAL = PROCESSED_ROOT / "normal"

SPLITS_ROOT = Path("safeher_ai/data/splits_v2")

SILENCE_THRESHOLD = 0.005

TRAIN_RATIO = 0.75
VAL_RATIO = 0.15
TEST_RATIO = 0.10

RANDOM_STATE = 42


def stable_id(path: Path) -> str:
    """
    Stable ID based on the relative source path.
    This avoids relying on speaker IDs in filenames.
    """
    rel = path.relative_to(RAW_ROOT).as_posix()
    return hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]


def load_audio(path: Path) -> np.ndarray:
    """
    Load any supported WAV as mono float32 at 16 kHz.
    """
    audio, _ = librosa.load(
        str(path),
        sr=SAMPLE_RATE,
        mono=True
    )

    audio = audio.astype(np.float32)

    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.9

    return audio


def split_chunks(audio: np.ndarray):
    """
    Split recording into 1-second chunks.
    Near-silent chunks are removed.
    """
    chunks = []

    for start in range(0, len(audio), CHUNK_SAMPLES):
        chunk = audio[start:start + CHUNK_SAMPLES]

        if len(chunk) < CHUNK_SAMPLES:
            chunk = np.pad(
                chunk,
                (0, CHUNK_SAMPLES - len(chunk))
            )

        rms = float(np.sqrt(np.mean(chunk ** 2)))

        if rms < SILENCE_THRESHOLD:
            continue

        chunks.append(chunk)

    return chunks


def category_from_path(path: Path, root: Path) -> str:
    """
    Preserve the immediate subdirectory as category.

    Examples:
        distress/Screaming/file.wav -> Screaming
        normal/ESC-50-master/file.wav -> ESC-50-master
        normal/Traffic/file.wav -> Traffic

    Files directly under the class folder receive '__root__'.
    """
    rel = path.relative_to(root)

    if len(rel.parts) >= 2:
        return rel.parts[0]

    return "__root__"


def process_class(
    root: Path,
    label: int,
    output_root: Path
):
    class_name = "distress" if label == 1 else "normal"

    files = sorted(root.rglob("*.wav"))

    print()
    print("=" * 60)
    print(f"{class_name.upper()} SOURCE FILES: {len(files)}")
    print("=" * 60)

    records = []

    for wav_path in tqdm(files, desc=f"Preparing {class_name}"):

        try:
            audio = load_audio(wav_path)
            chunks = split_chunks(audio)

            source_id = stable_id(wav_path)
            category = category_from_path(wav_path, root)

            source_stem = wav_path.stem

            source_output_dir = output_root / category
            source_output_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            for chunk_idx, chunk in enumerate(chunks):

                output_name = (
                    f"{class_name}_"
                    f"{source_id}_"
                    f"c{chunk_idx:04d}.wav"
                )

                output_path = source_output_dir / output_name

                sf.write(
                    str(output_path),
                    chunk,
                    SAMPLE_RATE,
                    subtype="PCM_16"
                )

                records.append({
                    "filepath": str(output_path),
                    "label": label,
                    "class": class_name,
                    "category": category,
                    "source_id": source_id,
                    "source": str(wav_path.relative_to(RAW_ROOT)),
                    "source_name": source_stem,
                    "chunk_idx": chunk_idx,
                    "duration_sec": 1.0,
                    "sample_rate": SAMPLE_RATE,
                    "channels": 1,
                })

        except Exception as exc:
            print(
                f"\nWARNING: skipped {wav_path}: {exc}"
            )

    print(
        f"{class_name}: generated "
        f"{len(records)} 1-second chunks"
    )

    return records


def split_sources(df: pd.DataFrame):

    source_table = (
        df[
            [
                "source_id",
                "label",
                "class"
            ]
        ]
        .drop_duplicates("source_id")
        .reset_index(drop=True)
    )

    train_sources, remaining_sources = train_test_split(
        source_table,
        test_size=VAL_RATIO + TEST_RATIO,
        random_state=RANDOM_STATE,
        stratify=source_table["label"]
    )

    remaining_labels = remaining_sources["label"].values

    val_fraction_of_remaining = (
        TEST_RATIO / (VAL_RATIO + TEST_RATIO)
    )

    val_sources, test_sources = train_test_split(
        remaining_sources,
        test_size=val_fraction_of_remaining,
        random_state=RANDOM_STATE,
        stratify=remaining_labels
    )

    train_ids = set(train_sources["source_id"])
    val_ids = set(val_sources["source_id"])
    test_ids = set(test_sources["source_id"])

    train_df = df[df["source_id"].isin(train_ids)].copy()
    val_df = df[df["source_id"].isin(val_ids)].copy()
    test_df = df[df["source_id"].isin(test_ids)].copy()

    return (
        train_df.reset_index(drop=True),
        val_df.reset_index(drop=True),
        test_df.reset_index(drop=True)
    )


def print_summary(name, df):

    print()
    print(f"===== {name.upper()} =====")
    print("Chunks:", len(df))
    print("Sources:", df["source_id"].nunique())
    print("Distress:", int((df["label"] == 1).sum()))
    print("Normal:", int((df["label"] == 0).sum()))

    print("\nCategories:")

    counts = (
        df.groupby(
            ["class", "category"]
        )
        .size()
        .sort_values(ascending=False)
    )

    print(counts.to_string())


def main():

    print("=" * 60)
    print("SafeHer — Dataset Preparation V2")
    print("=" * 60)

    PROCESSED_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    SPLITS_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    distress_records = process_class(
        DISTRESS_ROOT,
        1,
        PROCESSED_DISTRESS
    )

    normal_records = process_class(
        NORMAL_ROOT,
        0,
        PROCESSED_NORMAL
    )

    records = distress_records + normal_records

    if not records:
        raise RuntimeError(
            "No WAV files were processed."
        )

    df = pd.DataFrame(records)

    manifest_path = PROCESSED_ROOT / "manifest.csv"
    df.to_csv(
        manifest_path,
        index=False
    )

    print_summary("all data", df)

    train_df, val_df, test_df = split_sources(df)

    train_df.to_csv(
        SPLITS_ROOT / "train.csv",
        index=False
    )

    val_df.to_csv(
        SPLITS_ROOT / "val.csv",
        index=False
    )

    test_df.to_csv(
        SPLITS_ROOT / "test.csv",
        index=False
    )

    print_summary("train", train_df)
    print_summary("validation", val_df)
    print_summary("test", test_df)

    # Leakage check
    train_ids = set(train_df["source_id"])
    val_ids = set(val_df["source_id"])
    test_ids = set(test_df["source_id"])

    assert train_ids.isdisjoint(val_ids)
    assert train_ids.isdisjoint(test_ids)
    assert val_ids.isdisjoint(test_ids)

    print()
    print("=" * 60)
    print("✅ DATASET PREPARATION COMPLETE")
    print("=" * 60)

    print("Manifest:")
    print(f"  {manifest_path}")

    print("Splits:")
    print(f"  {SPLITS_ROOT / 'train.csv'}")
    print(f"  {SPLITS_ROOT / 'val.csv'}")
    print(f"  {SPLITS_ROOT / 'test.csv'}")

    print()
    print("Source leakage check: PASSED")
    print()
    print("IMPORTANT:")
    print("Validation/test are NOT augmented.")
    print("Training augmentation will be handled separately.")


if __name__ == "__main__":
    main()
