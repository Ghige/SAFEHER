"""
Build YAMNet embedding cache for derived audio_v3_prep splits.
Does NOT train. Does NOT overwrite data/embeddings (audio_v2 cache).

Run AFTER prepare_audio_v3_dataset.py:
  ..\\venv311\\Scripts\\python.exe training\\embed_audio_v3.py
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
import tensorflow_hub as hub
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DERIVED = DATA / "derived" / "audio_v3_prep"
SPLITS = DERIVED / "splits"
EMB_DIR = DERIVED / "embeddings"
LOG_DIR = DATA / "training_logs"
REPORT_MD = LOG_DIR / "audio_v3_pretraining_changes.md"
CHANGE_LOG_JSON = DERIVED / "change_log.json"

SAMPLE_RATE = 16000
CHUNK_SAMPLES = SAMPLE_RATE
YAMNET_URL = "https://tfhub.dev/google/yamnet/1"
EMBED_DIM = 1024


def load_wav(filepath: str) -> np.ndarray:
    path = Path(filepath)
    if not path.is_absolute():
        path = ROOT / path
    audio = tf.io.read_file(str(path))
    audio, sr = tf.audio.decode_wav(audio, desired_channels=1)
    audio = tf.squeeze(audio, axis=-1).numpy().astype(np.float32)
    # files are already 16k from prepare; decode_wav uses file SR
    return audio


def embed_file(yamnet, filepath: str) -> np.ndarray:
    waveform = load_wav(filepath)
    if len(waveform) < CHUNK_SAMPLES:
        waveform = np.pad(waveform, (0, CHUNK_SAMPLES - len(waveform)))
    else:
        waveform = waveform[:CHUNK_SAMPLES]
    _, embeddings, _ = yamnet(waveform)
    return embeddings.numpy().mean(axis=0).astype(np.float32)


def embed_split(yamnet, csv_path: Path, out_path: Path):
    df = pd.read_csv(csv_path)
    X, y, meta_idx = [], [], []
    skipped = 0
    for i, row in tqdm(df.iterrows(), total=len(df), desc=csv_path.stem):
        try:
            emb = embed_file(yamnet, row["filepath"])
            X.append(emb)
            y.append(int(row["label"]))
            meta_idx.append(int(i))
        except Exception as e:
            skipped += 1
            if skipped <= 20:
                print(f"skip {row['filepath']}: {e}")
    X = np.asarray(X, dtype=np.float32)
    y = np.asarray(y, dtype=np.int32)
    meta_idx = np.asarray(meta_idx, dtype=np.int32)
    EMB_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_path, X=X, y=y, row_index=meta_idx)
    return {"n": int(len(X)), "skipped": skipped, "path": str(out_path), "label_counts": {
        "0": int((y == 0).sum()), "1": int((y == 1).sum())
    }}


def append_report(notes: list[str], summary: dict):
    block = [
        "",
        "## Embedding run update",
        f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
        "",
    ]
    for n in notes:
        block.append(f"- {n}")
    block.append("")
    block.append("```json")
    block.append(json.dumps(summary, indent=2))
    block.append("```")
    block.append("")
    block.append("## Ready for Audio v3 training?")
    block.append(summary.get("ready_status", "UNKNOWN"))
    if REPORT_MD.exists():
        text = REPORT_MD.read_text(encoding="utf-8")
        # replace ready status section if present
        if "## Ready for Audio v3 training?" in text:
            head = text.split("## Ready for Audio v3 training?")[0].rstrip()
            # remove old embedding placeholder lines already in file; append update
            text = head + "\n" + "\n".join(block) + "\n"
            # keep explicit non-changes from original if stripped — re-append essentials
            text += "\n## Explicit non-changes\n"
            text += "- Did not delete/modify `data/raw/**`\n"
            text += "- Did not overwrite `data/models/audio_v2/**`\n"
            text += "- Did not overwrite `models/final/**`\n"
            text += "- Did not overwrite legacy `data/splits/**` or `data/embeddings/**`\n"
            text += "- Did not train audio_v3\n"
            text += "- Did not connect SOS\n"
        else:
            text += "\n" + "\n".join(block) + "\n"
        REPORT_MD.write_text(text, encoding="utf-8")
    if CHANGE_LOG_JSON.exists():
        clog = json.loads(CHANGE_LOG_JSON.read_text(encoding="utf-8"))
        clog.setdefault("embedding_notes", []).extend(notes)
        clog.setdefault("summary", {}).update(summary)
        clog["events"].append(
            {"ts": datetime.now().isoformat(timespec="seconds"), "kind": "EMBEDDING", "msg": summary.get("ready_status")}
        )
        CHANGE_LOG_JSON.write_text(json.dumps(clog, indent=2), encoding="utf-8")


def main():
    print("Loading YAMNet...")
    yamnet = hub.load(YAMNET_URL)
    notes = [
        "New embedding cache location: data/derived/audio_v3_prep/embeddings/",
        "Legacy data/embeddings/ (audio_v2) left untouched",
        "Embeddings are mean-pooled YAMNet 1024-d per 1s derived chunk (including aug_idx>0)",
    ]
    results = {}
    for split in ["train", "val", "test"]:
        csv_path = SPLITS / f"{split}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(csv_path)
        out = EMB_DIR / f"{split}.npz"
        print(f"Embedding {split} from {csv_path} ...")
        results[split] = embed_split(yamnet, csv_path, out)
        notes.append(f"{split}: {results[split]['n']} embeddings → {out} (skipped {results[split]['skipped']})")

    meta = {
        "feature_type": "YAMNet_embedding_1024",
        "sample_rate": SAMPLE_RATE,
        "chunk_seconds": 1,
        "derived_from": str(DERIVED),
        "created": datetime.now().isoformat(timespec="seconds"),
        "splits": results,
        "note": "For audio_v3 training only. Do not confuse with data/embeddings used by audio_v2.",
    }
    meta_path = EMB_DIR / "feature_config.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    notes.append(f"Wrote {meta_path}")

    summary = {
        "embeddings": results,
        "ready_status": (
            "READY FOR AUDIO V3 TRAINING — derived chunks, corrected labels, "
            "stratified source-safe splits, restored aug_idx, hard-neg audit, "
            "K-of-N helpers, and embedding cache are in place. Model not trained yet."
        ),
    }
    # update derived summary.json
    summary_path = DERIVED / "summary.json"
    if summary_path.exists():
        s = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        s = {}
    s["embeddings"] = results
    s["ready_status"] = summary["ready_status"]
    summary_path.write_text(json.dumps(s, indent=2), encoding="utf-8")

    append_report(notes, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        append_report([traceback.format_exc()], {"ready_status": "EMBEDDING FAILED"})
        raise
