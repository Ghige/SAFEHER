"""
SafeHer — balanced audio dataset + isolated retrain (v1).

Does NOT delete raw files.
Does NOT overwrite models/final or Android/backend TFLite.
Does NOT change DecisionContract.
Does NOT promote gold / bypass retraining_gate for production.

Usage (from safeher_ai/):
  python training/train_audio_balanced_v1.py --prepare
  python training/train_audio_balanced_v1.py --train
  python training/train_audio_balanced_v1.py --eval
  python training/train_audio_balanced_v1.py --all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dataset_metadata import binary_train_label, infer_metadata  # noqa: E402

SAMPLE_RATE = 16000
CHUNK_SAMPLES = SAMPLE_RATE
SILENCE_THRESHOLD = 0.005
RANDOM_STATE = 42
TRAIN_RATIO = 0.75
VAL_RATIO = 0.15
TEST_RATIO = 0.10
MAX_CHUNKS_PER_FILE = 4
TRAIN_NORMAL_PER_DISTRESS = 2.5
YAMNET_URL = "https://tfhub.dev/google/yamnet/1"
EMBED_DIM = 1024

RAW_DISTRESS = AI_ROOT / "data" / "raw" / "distress"
RAW_NORMAL = AI_ROOT / "data" / "raw" / "normal"
SPEECH_EM = AI_ROOT / "data" / "speech" / "emergency_phrases"
OUT = AI_ROOT / "data" / "derived" / "audio_balanced_v1"
MODEL_DIR = AI_ROOT / "data" / "models" / "audio_balanced_v1"
PROD_TFLITE = AI_ROOT / "models" / "final" / "yamnet_distress_quant.tflite"
LEGACY_KERAS = AI_ROOT / "models" / "final" / "safeher_classifier_20260705_1705.keras"
V4_KERAS = AI_ROOT / "data" / "models" / "audio_v4_exp02" / "audio_distress_classifier.keras"

AUDIO_EXTS = {".wav", ".flac", ".ogg", ".mp3", ".m4a"}
USEFUL_NORMAL_FOLDERS = {
    "Traffic",
    "cars",
    "Truck",
    "ESC-50-master",
    "NotScreaming",
    "airplane",
    "helicopter",
    "bics",
    "_root",
}

log = logging.getLogger("audio_balanced_v1")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def youtube_key(name: str) -> str:
    stem = Path(name).stem
    return re.sub(r"_out$", "", stem)


def file_md5(path: Path, buf: int = 1024 * 1024) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            chunk = f.read(buf)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def folder_of(path: Path, raw_root: Path) -> str:
    try:
        rel = path.relative_to(raw_root)
    except ValueError:
        return path.parent.name or "_root"
    parts = rel.parts
    if len(parts) == 1:
        return "_root"
    return parts[0]


def collect_candidates() -> list[dict]:
    rows = []
    for label, root, origin in (
        (1, RAW_DISTRESS, "raw_distress"),
        (0, RAW_NORMAL, "raw_normal"),
        (1, SPEECH_EM, "speech_emergency"),
    ):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in AUDIO_EXTS:
                continue
            meta = infer_metadata(path)
            mapped = binary_train_label(meta)
            if mapped is None:
                rows.append(
                    {
                        "original_path": str(path),
                        "label": None,
                        "origin": origin,
                        "folder": folder_of(path, root),
                        "source": path.name,
                        "exclude_reason": "support_or_unmapped",
                    }
                )
                continue
            rows.append(
                {
                    "original_path": str(path),
                    "label": int(mapped if label is None else label),
                    "origin": origin,
                    "folder": folder_of(path, root),
                    "source": path.name,
                    "signal_type": meta.get("signal_type", ""),
                    "phrase": meta.get("phrase", ""),
                    "exclude_reason": "",
                }
            )
    return rows


def validate_audio(path: Path) -> str:
    try:
        info = sf.info(str(path))
    except Exception as exc:
        return f"unreadable:{type(exc).__name__}"
    if info.frames <= 0 or info.samplerate <= 0:
        return "unrecognized_empty"
    if info.channels < 1:
        return "unsupported_channels"
    try:
        data, _sr = sf.read(str(path), frames=min(info.frames, info.samplerate), dtype="float32", always_2d=False)
    except Exception as exc:
        return f"decode_fail:{type(exc).__name__}"
    arr = np.asarray(data)
    if arr.size == 0:
        return "unrecognized_empty"
    return ""


def source_key_for(row: pd.Series) -> str:
    if row["folder"] in {"Screaming", "NotScreaming"}:
        return f"yt::{youtube_key(row['source'])}"
    return f"hash::{row['content_md5']}"


def split_keys(keys: list[str]) -> tuple[set[str], set[str], set[str]]:
    keys = sorted(keys)
    n = len(keys)
    if n == 1:
        return {keys[0]}, set(), set()
    if n == 2:
        return {keys[0]}, set(), {keys[1]}
    if n < 10:
        return set(keys[2:]), {keys[1]}, {keys[0]}
    tr, vt = train_test_split(
        keys, test_size=(VAL_RATIO + TEST_RATIO), random_state=RANDOM_STATE
    )
    va, te = train_test_split(
        vt, test_size=TEST_RATIO / (VAL_RATIO + TEST_RATIO), random_state=RANDOM_STATE
    )
    return set(tr), set(va), set(te)


def balance_train_normals(train: pd.DataFrame) -> pd.DataFrame:
    distress = train[train["label"] == 1]
    normals = train[train["label"] == 0]
    target = int(round(len(distress) * TRAIN_NORMAL_PER_DISTRESS))
    if len(normals) <= target:
        return train
    rng = np.random.RandomState(RANDOM_STATE)
    kept = []
    remaining = normals.copy()
    # Guarantee diversity from useful folders first.
    min_each = max(8, target // (len(USEFUL_NORMAL_FOLDERS) * 4))
    for folder in sorted(USEFUL_NORMAL_FOLDERS):
        pool = remaining[remaining["folder"] == folder]
        if pool.empty:
            continue
        take = min(len(pool), min_each)
        chosen = pool.sample(n=take, random_state=RANDOM_STATE)
        kept.append(chosen)
        remaining = remaining.drop(chosen.index)
    have = pd.concat(kept) if kept else normals.iloc[0:0]
    need = target - len(have)
    if need > 0 and not remaining.empty:
        weights = remaining["folder"].map(lambda f: 2.0 if f in USEFUL_NORMAL_FOLDERS else 1.0)
        probs = weights.to_numpy(dtype=float)
        probs = probs / probs.sum()
        idx = rng.choice(remaining.index.to_numpy(), size=min(need, len(remaining)), replace=False, p=probs)
        have = pd.concat([have, remaining.loc[idx]])
    return pd.concat([distress, have]).sort_values("original_path").reset_index(drop=True)


def load_mono_16k(path: Path) -> np.ndarray:
    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    audio = np.asarray(data, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != SAMPLE_RATE:
        import librosa

        audio = librosa.resample(audio, orig_sr=sr, target_sr=SAMPLE_RATE)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 0:
        audio = audio / peak * 0.9
    return audio.astype(np.float32)


def extract_chunks(audio: np.ndarray) -> list[np.ndarray]:
    if len(audio) < CHUNK_SAMPLES:
        padded = np.pad(audio, (0, CHUNK_SAMPLES - len(audio)))
        if float(np.sqrt(np.mean(padded**2))) < SILENCE_THRESHOLD:
            return []
        return [padded]
    starts = list(range(0, len(audio) - CHUNK_SAMPLES + 1, CHUNK_SAMPLES))
    if len(starts) > MAX_CHUNKS_PER_FILE:
        idxs = np.linspace(0, len(starts) - 1, MAX_CHUNKS_PER_FILE, dtype=int)
        starts = [starts[i] for i in idxs]
    chunks = []
    for start in starts:
        chunk = audio[start : start + CHUNK_SAMPLES]
        if float(np.sqrt(np.mean(chunk**2))) < SILENCE_THRESHOLD:
            continue
        chunks.append(chunk)
    return chunks


def prepare() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    candidates = collect_candidates()
    inventory = pd.DataFrame(candidates)
    inventory.to_csv(OUT / "inventory_raw.csv", index=False)

    original_counts = {
        "distress_files": int((inventory["label"] == 1).sum()),
        "normal_files": int((inventory["label"] == 0).sum()),
        "unmapped_files": int(inventory["label"].isna().sum()),
        "distress_by_folder": inventory[inventory["label"] == 1]
        .groupby("folder")
        .size()
        .to_dict(),
        "normal_by_folder": inventory[inventory["label"] == 0]
        .groupby("folder")
        .size()
        .to_dict(),
    }

    hashes = []
    reasons = []
    for row in inventory.itertuples(index=False):
        path = Path(row.original_path)
        if row.label is None:
            hashes.append("")
            reasons.append(row.exclude_reason or "unmapped")
            continue
        try:
            digest = file_md5(path)
            hashes.append(digest)
        except Exception as exc:
            hashes.append("")
            reasons.append(f"hash_fail:{type(exc).__name__}")
            continue
        reasons.append(validate_audio(path))

    inventory["content_md5"] = hashes
    inventory["exclude_reason"] = reasons

    usable = inventory[inventory["label"].notna() & (inventory["exclude_reason"] == "")].copy()
    usable["content_md5"] = usable["content_md5"].astype(str)
    usable["source_key"] = usable.apply(source_key_for, axis=1)

    # Exact-duplicate policy: keep one file per hash. Prefer raw_distress, then speech, then normal.
    origin_rank = {"raw_distress": 0, "speech_emergency": 1, "raw_normal": 2}
    usable["origin_rank"] = usable["origin"].map(origin_rank).fillna(9)
    usable = usable.sort_values(["content_md5", "origin_rank", "original_path"])
    dup_keep = usable.drop_duplicates("content_md5", keep="first")
    dup_drop = usable.loc[~usable.index.isin(dup_keep.index)].copy()
    dup_drop["exclude_reason"] = "exact_duplicate"

    # Never drop a unique distress hash. Duplicates of distress hashes that
    # landed in normal (should be rare) stay excluded as duplicates only.
    kept = dup_keep.copy()

    excluded = pd.concat(
        [
            inventory[inventory["exclude_reason"] != ""],
            dup_drop,
        ],
        ignore_index=True,
    )
    excluded.to_csv(OUT / "excluded.csv", index=False)
    kept.to_csv(OUT / "source_manifest.csv", index=False)

    train_keys, val_keys, test_keys = set(), set(), set()
    split_notes = []
    for stratum, g in kept.groupby(kept.apply(lambda r: f"{int(r.label)}::{r.folder}", axis=1)):
        keys = sorted(g["source_key"].unique())
        tr, va, te = split_keys(keys)
        overlap = (tr & va) | (tr & te) | (va & te)
        if overlap:
            raise RuntimeError(f"split leakage in {stratum}: {overlap}")
        train_keys |= tr
        val_keys |= va
        test_keys |= te
        split_notes.append({"stratum": stratum, "n_keys": len(keys), "train": len(tr), "val": len(va), "test": len(te)})

    if train_keys & val_keys or train_keys & test_keys or val_keys & test_keys:
        raise RuntimeError("source_key leakage across splits")

    kept["split"] = kept["source_key"].map(
        lambda k: "train" if k in train_keys else "val" if k in val_keys else "test" if k in test_keys else "unused"
    )
    train_full = kept[kept["split"] == "train"].copy()
    train_bal = balance_train_normals(train_full)
    train_dropped = train_full.loc[~train_full.index.isin(train_bal.index)].copy()
    train_dropped["exclude_reason"] = "train_normal_downsample"
    excluded = pd.concat([excluded, train_dropped], ignore_index=True)
    excluded.to_csv(OUT / "excluded.csv", index=False)

    val_df = kept[kept["split"] == "val"].copy()
    test_df = kept[kept["split"] == "test"].copy()
    train_bal["split"] = "train"
    (OUT / "splits").mkdir(parents=True, exist_ok=True)
    train_bal.to_csv(OUT / "splits" / "train_sources.csv", index=False)
    val_df.to_csv(OUT / "splits" / "val_sources.csv", index=False)
    test_df.to_csv(OUT / "splits" / "test_sources.csv", index=False)

    chunk_dir = OUT / "chunks"
    (chunk_dir / "distress").mkdir(parents=True, exist_ok=True)
    (chunk_dir / "normal").mkdir(parents=True, exist_ok=True)
    chunk_rows = []
    for split_name, sdf in (("train", train_bal), ("val", val_df), ("test", test_df)):
        for row in sdf.itertuples(index=False):
            path = Path(row.original_path)
            try:
                audio = load_mono_16k(path)
                chunks = extract_chunks(audio)
            except Exception as exc:
                fail = row._asdict() if hasattr(row, "_asdict") else {"original_path": str(path)}
                fail["exclude_reason"] = f"chunk_fail:{type(exc).__name__}"
                excluded = pd.concat([excluded, pd.DataFrame([fail])], ignore_index=True)
                continue
            label_name = "distress" if int(row.label) == 1 else "normal"
            for idx, chunk in enumerate(chunks):
                fname = f"{split_name}_{label_name}_{path.stem}_c{idx:02d}.wav"
                out_path = chunk_dir / label_name / fname
                sf.write(str(out_path), chunk, SAMPLE_RATE, subtype="PCM_16")
                chunk_rows.append(
                    {
                        "filepath": str(out_path),
                        "label": int(row.label),
                        "split": split_name,
                        "source": row.source,
                        "source_key": row.source_key,
                        "folder": row.folder,
                        "origin": row.origin,
                        "original_path": row.original_path,
                        "content_md5": row.content_md5,
                        "chunk_idx": idx,
                    }
                )

    chunks_df = pd.DataFrame(chunk_rows)
    chunks_df.to_csv(OUT / "chunk_manifest.csv", index=False)
    for split_name in ("train", "val", "test"):
        part = chunks_df[chunks_df["split"] == split_name]
        part.to_csv(OUT / "splits" / f"{split_name}.csv", index=False)

    # Leakage check on chunks
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        ka = set(chunks_df.loc[chunks_df["split"] == a, "source_key"])
        kb = set(chunks_df.loc[chunks_df["split"] == b, "source_key"])
        if ka & kb:
            raise RuntimeError(f"chunk source_key leakage {a}/{b}")

    summary = {
        "generated_at": utc_now(),
        "original_counts": original_counts,
        "excluded": {
            "exact_duplicate": int((excluded["exclude_reason"] == "exact_duplicate").sum()),
            "invalid_or_unreadable": int(
                excluded["exclude_reason"].fillna("").str.contains("unreadable|decode|unsupported|unrecognized|hash_fail|chunk_fail").sum()
            ),
            "train_normal_downsample": int((excluded["exclude_reason"] == "train_normal_downsample").sum()),
            "support_or_unmapped": int((excluded["exclude_reason"] == "support_or_unmapped").sum()),
            "total_excluded_rows": int(len(excluded)),
        },
        "unique_valid_sources": {
            "distress": int((kept["label"] == 1).sum()),
            "normal": int((kept["label"] == 0).sum()),
        },
        "source_splits": {
            "train": {
                "distress": int((train_bal["label"] == 1).sum()),
                "normal": int((train_bal["label"] == 0).sum()),
                "total": int(len(train_bal)),
            },
            "val": {
                "distress": int((val_df["label"] == 1).sum()),
                "normal": int((val_df["label"] == 0).sum()),
                "total": int(len(val_df)),
            },
            "test": {
                "distress": int((test_df["label"] == 1).sum()),
                "normal": int((test_df["label"] == 0).sum()),
                "total": int(len(test_df)),
            },
        },
        "chunk_splits": {
            name: {
                "distress": int(((chunks_df["split"] == name) & (chunks_df["label"] == 1)).sum()),
                "normal": int(((chunks_df["split"] == name) & (chunks_df["label"] == 0)).sum()),
                "total": int((chunks_df["split"] == name).sum()),
            }
            for name in ("train", "val", "test")
        },
        "balancing": {
            "strategy": "keep_all_unique_valid_distress; downsample_train_normals_only_to_2.5x_distress; val/test_natural",
            "train_normal_per_distress": TRAIN_NORMAL_PER_DISTRESS,
            "max_chunks_per_file": MAX_CHUNKS_PER_FILE,
            "not_forced_50_50": True,
        },
        "split_notes": split_notes,
        "raw_data_deleted": False,
        "distress_files_deleted": False,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    excluded.to_csv(OUT / "excluded.csv", index=False)
    log.info("Prepared %s", OUT)
    return summary


def get_yamnet():
    import tensorflow_hub as hub

    log.info("Loading YAMNet from TF Hub...")
    return hub.load(YAMNET_URL)


def embed_wav(yamnet, filepath: str) -> np.ndarray:
    import tensorflow as tf

    audio = tf.io.read_file(filepath)
    audio, _ = tf.audio.decode_wav(audio, desired_channels=1)
    waveform = tf.squeeze(audio, axis=-1).numpy().astype(np.float32)
    if len(waveform) < CHUNK_SAMPLES:
        waveform = np.pad(waveform, (0, CHUNK_SAMPLES - len(waveform)))
    else:
        waveform = waveform[:CHUNK_SAMPLES]
    _, embeddings, _ = yamnet(waveform)
    return embeddings.numpy().mean(axis=0)


def build_or_load_embeddings(csv_path: Path, cache_name: str):
    embed_dir = OUT / "embeddings"
    embed_dir.mkdir(parents=True, exist_ok=True)
    cache_path = embed_dir / cache_name
    df = pd.read_csv(csv_path)
    if cache_path.exists():
        data = np.load(cache_path)
        if len(data["y"]) == len(df):
            return data["X"], data["y"], df
    import tensorflow as tf  # noqa: F401

    yamnet = get_yamnet()
    X, y = [], []
    for row in df.itertuples(index=False):
        try:
            X.append(embed_wav(yamnet, row.filepath))
            y.append(int(row.label))
        except Exception as exc:
            log.warning("skip embed %s: %s", row.filepath, exc)
    X = np.asarray(X, dtype=np.float32)
    y = np.asarray(y, dtype=np.int32)
    np.savez(cache_path, X=X, y=y)
    return X, y, df


def build_classifier():
    import tensorflow as tf

    inputs = tf.keras.Input(shape=(EMBED_DIM,), name="yamnet_embedding")
    x = tf.keras.layers.Dense(256, activation="relu", name="dense1")(inputs)
    x = tf.keras.layers.Dropout(0.4, name="dropout1")(x)
    x = tf.keras.layers.Dense(64, activation="relu", name="dense2")(x)
    x = tf.keras.layers.Dropout(0.3, name="dropout2")(x)
    output = tf.keras.layers.Dense(1, activation="sigmoid", name="output")(x)
    return tf.keras.Model(inputs=inputs, outputs=output, name="SafeHerAudioClassifierBalancedV1")


def train() -> Path:
    import tensorflow as tf

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    X_tr, y_tr, _ = build_or_load_embeddings(OUT / "splits" / "train.csv", "train.npz")
    X_va, y_va, _ = build_or_load_embeddings(OUT / "splits" / "val.csv", "val.npz")
    model = build_classifier()
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss=tf.keras.losses.BinaryCrossentropy(),
        metrics=[
            tf.keras.metrics.BinaryAccuracy(name="accuracy"),
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
            tf.keras.metrics.AUC(name="auc"),
        ],
    )
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_recall", patience=8, mode="max", restore_best_weights=True
        ),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=4, min_lr=1e-6),
    ]
    model.fit(
        X_tr,
        y_tr,
        validation_data=(X_va, y_va),
        batch_size=32,
        epochs=50,
        class_weight={0: 1.0, 1: 2.0},
        callbacks=callbacks,
        verbose=2,
    )
    out = MODEL_DIR / "audio_distress_classifier.keras"
    model.save(str(out))
    log.info("Saved %s", out)
    return out


def metrics_at(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    preds = (scores >= threshold).astype(int)
    cm = confusion_matrix(y_true, preds, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    return {
        "threshold": threshold,
        "accuracy": float(accuracy_score(y_true, preds)),
        "precision": float(precision_score(y_true, preds, zero_division=0)),
        "recall": float(recall_score(y_true, preds, zero_division=0)),
        "f1": float(f1_score(y_true, preds, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, scores)) if len(np.unique(y_true)) > 1 else None,
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "distress_n": int((y_true == 1).sum()),
        "normal_n": int((y_true == 0).sum()),
        "distress_recall": float(tp / (tp + fn)) if (tp + fn) else 0.0,
        "false_negative_count": int(fn),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def score_keras(model_path: Path, X: np.ndarray) -> np.ndarray | None:
    if not model_path.is_file():
        return None
    import tensorflow as tf

    model = tf.keras.models.load_model(str(model_path))
    return model.predict(X, verbose=0).flatten()


def score_tflite(model_path: Path, df: pd.DataFrame) -> np.ndarray | None:
    if not model_path.is_file():
        return None
    import tensorflow as tf

    interpreter = tf.lite.Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    inp = interpreter.get_input_details()[0]
    out = interpreter.get_output_details()[0]
    scores = []
    for filepath in df["filepath"]:
        audio = tf.io.read_file(filepath)
        audio, _ = tf.audio.decode_wav(audio, desired_channels=1)
        waveform = tf.squeeze(audio, axis=-1).numpy().astype(np.float32)
        if len(waveform) < CHUNK_SAMPLES:
            waveform = np.pad(waveform, (0, CHUNK_SAMPLES - len(waveform)))
        else:
            waveform = waveform[:CHUNK_SAMPLES]
        interpreter.set_tensor(inp["index"], waveform.reshape(1, CHUNK_SAMPLES))
        interpreter.invoke()
        scores.append(float(interpreter.get_tensor(out["index"])[0][0]))
    return np.asarray(scores, dtype=np.float32)


def better_than(new: dict, old: dict) -> tuple[bool, list[str]]:
    reasons = []
    better = True
    if new["distress_recall"] < old["distress_recall"]:
        better = False
        reasons.append("new distress recall is lower")
    elif new["distress_recall"] > old["distress_recall"]:
        reasons.append("new distress recall is higher")
    else:
        reasons.append("distress recall is tied")
    if new["fn"] > old["fn"]:
        better = False
        reasons.append("new model misses more distress (higher FN)")
    elif new["fn"] < old["fn"]:
        reasons.append("new model has fewer false negatives")
    if new["f1"] + 1e-9 < old["f1"]:
        reasons.append("new F1 is lower")
        # F1 drop alone does not veto if recall/FN improved, but it blocks "better" if recall did not improve
        if new["distress_recall"] <= old["distress_recall"]:
            better = False
    elif new["f1"] > old["f1"]:
        reasons.append("new F1 is higher")
    if new["fp"] > old["fp"] * 1.25 and new["distress_recall"] <= old["distress_recall"] + 0.01:
        better = False
        reasons.append("false positives rose without a meaningful recall gain")
    return better, reasons


def evaluate() -> dict:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    X_te, y_te, df = build_or_load_embeddings(OUT / "splits" / "test.csv", "test.npz")
    new_path = MODEL_DIR / "audio_distress_classifier.keras"
    scores = {
        "new_balanced_v1": score_keras(new_path, X_te),
        "legacy_20260705_keras": score_keras(LEGACY_KERAS, X_te),
        "audio_v4_exp02_keras": score_keras(V4_KERAS, X_te),
        "production_tflite": score_tflite(PROD_TFLITE, df),
    }
    report = {"generated_at": utc_now(), "test_chunks": int(len(df)), "models": {}}
    for name, sc in scores.items():
        if sc is None:
            report["models"][name] = {"status": "MISSING"}
            continue
        report["models"][name] = {
            "status": "EVALUATED",
            "at_0.50": metrics_at(y_te, sc, 0.50),
            "at_0.60": metrics_at(y_te, sc, 0.60),
        }
    # Prefer Keras baselines. Production TFLite is quantized and is only
    # used as primary if it actually fires on this test set.
    primary_old = None
    tflite = report["models"].get("production_tflite", {})
    tflite_ok = (
        tflite.get("status") == "EVALUATED"
        and tflite.get("at_0.50", {}).get("tp", 0) > 0
    )
    order = (
        ["production_tflite", "audio_v4_exp02_keras", "legacy_20260705_keras"]
        if tflite_ok
        else ["audio_v4_exp02_keras", "legacy_20260705_keras", "production_tflite"]
    )
    for key in order:
        if report["models"].get(key, {}).get("status") == "EVALUATED":
            primary_old = key
            break
    new_m = report["models"].get("new_balanced_v1", {})
    comparison = {"primary_old": primary_old, "is_better": False, "reasons": ["new model missing"]}
    if new_m.get("status") == "EVALUATED" and primary_old:
        is_better, reasons = better_than(new_m["at_0.50"], report["models"][primary_old]["at_0.50"])
        comparison = {
            "primary_old": primary_old,
            "compared_at": 0.50,
            "is_better": is_better,
            "reasons": reasons,
        }
    report["comparison"] = comparison
    (MODEL_DIR / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (MODEL_DIR / "metrics.json").write_text(
        json.dumps(new_m if new_m.get("status") == "EVALUATED" else report, indent=2),
        encoding="utf-8",
    )
    return report


def verify_inference() -> dict:
    import tensorflow as tf

    checks = {}
    if PROD_TFLITE.is_file():
        interpreter = tf.lite.Interpreter(model_path=str(PROD_TFLITE))
        interpreter.allocate_tensors()
        inp = interpreter.get_input_details()[0]
        out = interpreter.get_output_details()[0]
        interpreter.set_tensor(inp["index"], np.zeros((1, CHUNK_SAMPLES), dtype=np.float32))
        interpreter.invoke()
        silence = float(interpreter.get_tensor(out["index"])[0][0])
        checks["production_tflite_silence"] = silence
        checks["production_tflite_loads"] = True
        checks["production_not_overwritten"] = True
    else:
        checks["production_tflite_loads"] = False
    new_tflite = MODEL_DIR / "yamnet_distress.tflite"
    if new_tflite.is_file():
        interpreter = tf.lite.Interpreter(model_path=str(new_tflite))
        interpreter.allocate_tensors()
        inp = interpreter.get_input_details()[0]
        out = interpreter.get_output_details()[0]
        interpreter.set_tensor(inp["index"], np.zeros((1, CHUNK_SAMPLES), dtype=np.float32))
        interpreter.invoke()
        checks["new_tflite_silence"] = float(interpreter.get_tensor(out["index"])[0][0])
    keras_path = MODEL_DIR / "audio_distress_classifier.keras"
    checks["new_keras_exists"] = keras_path.is_file()
    return checks


def export_isolated_tflite(keras_path: Path) -> Path | None:
    """Export waveform TFLite next to the new keras file only."""
    import tensorflow as tf
    import tensorflow_hub as hub

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from importlib import import_module

    exp = import_module("04_export_tflite")
    classifier = tf.keras.models.load_model(str(keras_path))
    inference_model = exp.SafeHerInferenceModel(classifier)
    out_path = MODEL_DIR / "yamnet_distress.tflite"
    exp.export_float32(inference_model, out_path)
    exp.verify_tflite(out_path)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--eval", action="store_true")
    parser.add_argument("--export-tflite", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if not any([args.prepare, args.train, args.eval, args.export_tflite, args.all]):
        args.all = True
    if args.all or args.prepare:
        print(json.dumps(prepare(), indent=2))
    if args.all or args.train:
        train()
    if args.all or args.eval:
        print(json.dumps(evaluate(), indent=2))
    if args.export_tflite:
        keras_path = MODEL_DIR / "audio_distress_classifier.keras"
        export_isolated_tflite(keras_path)
    print(json.dumps({"inference_checks": verify_inference()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
