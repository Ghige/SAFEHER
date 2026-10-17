"""
Repair audio_v3_prep splits/labels without re-reading raw audio.

Fixes:
1) Split by shared source_key so paired Screaming/NotScreaming YouTube IDs
   cannot leak across train/val/test.
2) Tighten hard-negative tagging: audio_v2 FP sources + high likeness (>=0.70),
   not the overly broad 0.55 gate.
3) Rebuild train/val/test CSVs; keep existing aug WAVs that belong to new train keys.

Does NOT modify raw audio, audio_v2, or models/final. Does NOT train.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DERIVED = DATA / "derived" / "audio_v3_prep"
LABELS = DERIVED / "labels"
SPLITS = DERIVED / "splits"
HARD_NEG = DERIVED / "hard_negatives"
CHUNKS = DERIVED / "chunks"
ERROR_JSON = DATA / "training_logs" / "audio_error_analysis.json"
REPORT_MD = DATA / "training_logs" / "audio_v3_pretraining_changes.md"
CHANGE_LOG_JSON = DERIVED / "change_log.json"

TRAIN_RATIO, VAL_RATIO, TEST_RATIO = 0.75, 0.15, 0.10
RANDOM_STATE = 42
NOTSCREAM_HARD_MIN = 0.70  # tightened from 0.55


def youtube_key(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"_out$", "", stem)
    return stem


def source_key_row(row) -> str:
    folder = str(row["folder"])
    src = str(row["source"])
    if folder in {"Screaming", "NotScreaming"}:
        return f"yt::{youtube_key(src)}"
    return f"path::{row['original_path']}"


def load_all_fp_sources() -> set[str]:
    """Rebuild full FP source set: prefer live audio_v2 test predictions, else JSON."""
    sources = set()
    # Live reconstruction from audio_v2 model + legacy test embeddings (read-only)
    try:
        import tensorflow as tf

        test_csv = DATA / "splits" / "test.csv"
        emb_path = DATA / "embeddings" / "test.npz"
        model_path = DATA / "models" / "audio_v2" / "audio_distress_classifier.keras"
        if test_csv.exists() and emb_path.exists() and model_path.exists():
            test_df = pd.read_csv(test_csv)
            emb = np.load(emb_path)
            X = emb["X"]
            model = tf.keras.models.load_model(model_path)
            pred = (model.predict(X, verbose=0).ravel() >= 0.5).astype(int)
            y = test_df["label"].values.astype(int)
            fp_idx = np.where((y == 0) & (pred == 1))[0]
            for i in fp_idx:
                sources.add(str(test_df.iloc[int(i)]["source"]))
            print(f"Reconstructed {len(sources)} FP sources from audio_v2 test predictions")
            return sources
    except Exception as e:
        print(f"FP live reconstruction failed ({e}); falling back to JSON")

    if ERROR_JSON.exists():
        data = json.loads(ERROR_JSON.read_text(encoding="utf-8"))
        for src, _ in data.get("fp", {}).get("top_error_sources", []):
            sources.add(src)
        for ex in data.get("fp", {}).get("examples", []):
            if ex.get("source"):
                sources.add(ex["source"])
    return sources


def retag_hard_negatives(df: pd.DataFrame, fp_sources: set[str]) -> pd.DataFrame:
    df = df.copy()
    new_bucket = []
    new_decision = []
    new_rule = []
    for _, row in df.iterrows():
        folder = row["folder"]
        src = row["source"]
        score = float(row["scream_likeness"])
        bucket = row["bucket"]
        decision = row["decision"]
        rule = row["label_rule"]

        if folder == "NotScreaming" and int(row["label"]) == 0:
            hard = src in fp_sources or score >= NOTSCREAM_HARD_MIN
            if hard:
                reasons = []
                if src in fp_sources:
                    reasons.append("audio_v2_FP_source")
                if score >= NOTSCREAM_HARD_MIN:
                    reasons.append(f"likeness>={NOTSCREAM_HARD_MIN}")
                bucket = "hard_negative_scream_like"
                decision = "keep_normal_tagged_hard_neg"
                rule = "+".join(reasons)
            else:
                bucket = "easy_normal_notscreaming"
                decision = "keep_normal"
                rule = "NotScreaming easy"
        elif folder == "ESC-50-master" and src in fp_sources:
            bucket = "hard_negative_esc50_fp"
            decision = "keep_normal_tagged_hard_neg"
            rule = "ESC-50 source appeared as audio_v2 FP"
        # else leave scream/phrase/ambient as-is

        new_bucket.append(bucket)
        new_decision.append(decision)
        new_rule.append(rule)

    df["bucket"] = new_bucket
    df["decision"] = new_decision
    df["label_rule"] = new_rule
    return df


def stratified_split_by_key(df: pd.DataFrame):
    df = df.copy()
    df["source_key"] = df.apply(source_key_row, axis=1)

    # stratum for paired yt keys: use "paired_scream_notscream" if key appears in both
    key_strata = {}
    for key, g in df.groupby("source_key"):
        folders = set(g["folder"].unique())
        if folders >= {"Screaming", "NotScreaming"} or (
            "Screaming" in folders and "NotScreaming" in folders
        ):
            key_strata[key] = "paired_scream_notscream"
        else:
            # majority stratum
            key_strata[key] = g["stratum"].value_counts().idxmax()
    df["split_stratum"] = df["source_key"].map(key_strata)

    train_keys, val_keys, test_keys = set(), set(), set()
    notes = []
    for stratum, g in df.groupby("split_stratum"):
        keys = sorted(g["source_key"].unique())
        n = len(keys)
        if n == 1:
            train_keys.add(keys[0])
            notes.append(f"{stratum}: 1 key → train")
            continue
        if n == 2:
            train_keys.add(keys[0])
            test_keys.add(keys[1])
            notes.append(f"{stratum}: 2 keys → train+test")
            continue
        if n < 10:
            test_keys.add(keys[0])
            val_keys.add(keys[1])
            train_keys.update(keys[2:])
            notes.append(f"{stratum}: n={n} → 1 test, 1 val, rest train")
            continue
        tr, vt = train_test_split(keys, test_size=(VAL_RATIO + TEST_RATIO), random_state=RANDOM_STATE)
        va, te = train_test_split(
            vt, test_size=TEST_RATIO / (VAL_RATIO + TEST_RATIO), random_state=RANDOM_STATE
        )
        train_keys.update(tr)
        val_keys.update(va)
        test_keys.update(te)
        notes.append(f"{stratum}: n={n} → train={len(tr)} val={len(va)} test={len(te)}")

    # enforce disjoint
    assert not (train_keys & val_keys)
    assert not (train_keys & test_keys)
    assert not (val_keys & test_keys)

    def take(name, keys):
        out = df[df["source_key"].isin(keys)].copy()
        out["split"] = name
        return out.reset_index(drop=True)

    return take("train", train_keys), take("validation", val_keys), take("test", test_keys), notes


def attach_existing_augmentations(train_df: pd.DataFrame) -> pd.DataFrame:
    """Include already-written a1..a7 WAVs for train distress a0 rows."""
    base = train_df[(train_df["label"] == 1) & (train_df["aug_idx"] == 0)]
    new_rows = []
    missing = 0
    for _, row in base.iterrows():
        p = ROOT / str(row["filepath"])
        if not p.name.endswith("_a0.wav"):
            continue
        for a_idx in range(1, 8):
            aug_path = p.with_name(p.name.replace("_a0.wav", f"_a{a_idx}.wav"))
            if not aug_path.exists():
                missing += 1
                continue
            r = row.to_dict()
            r["filepath"] = str(aug_path.relative_to(ROOT))
            r["aug_idx"] = a_idx
            new_rows.append(r)
    print(f"Attached {len(new_rows)} existing aug rows; missing aug files: {missing}")
    if new_rows:
        train_df = pd.concat([train_df, pd.DataFrame(new_rows)], ignore_index=True)
    return train_df


def write_hard_neg_docs(df: pd.DataFrame, fp_sources: set[str]):
    hard = df[df["bucket"].isin(["hard_negative_scream_like", "hard_negative_esc50_fp"])].copy()
    rows = []
    for src, g in hard.groupby("source"):
        rows.append(
            {
                "source": src,
                "folder": g["folder"].iloc[0],
                "bucket": g["bucket"].iloc[0],
                "n_chunks": int(len(g)),
                "mean_scream_likeness": float(g["scream_likeness"].mean()),
                "max_scream_likeness": float(g["scream_likeness"].max()),
                "in_audio_v2_fp_list": bool(src in fp_sources),
                "classification": "HARD_NEGATIVE_SCREAM_LIKE_PRESERVED",
                "action": "KEEP as NORMAL label=0; do NOT delete",
            }
        )
    hard_src = pd.DataFrame(rows).sort_values(
        ["in_audio_v2_fp_list", "mean_scream_likeness"], ascending=False
    )
    hard_src.to_csv(HARD_NEG / "hard_negative_sources.csv", index=False)
    hard.to_csv(HARD_NEG / "hard_negative_chunks.csv", index=False)
    md = [
        "# Hard-negative audit (repaired)",
        "",
        f"Gate: audio_v2 FP source OR scream_likeness >= {NOTSCREAM_HARD_MIN}",
        f"Hard-negative sources: {len(hard_src)}",
        f"Hard-negative chunks: {len(hard)}",
        f"Overlap with known audio_v2 FP filenames: {int(hard_src['in_audio_v2_fp_list'].sum()) if len(hard_src) else 0}",
        "",
        "Raw files NOT deleted. Label remains NORMAL (0).",
        "",
    ]
    (HARD_NEG / "HARD_NEGATIVES.md").write_text("\n".join(md), encoding="utf-8")
    return hard_src


def append_report(text: str):
    if REPORT_MD.exists():
        REPORT_MD.write_text(REPORT_MD.read_text(encoding="utf-8") + "\n" + text + "\n", encoding="utf-8")
    if CHANGE_LOG_JSON.exists():
        clog = json.loads(CHANGE_LOG_JSON.read_text(encoding="utf-8"))
        clog.setdefault("events", []).append(
            {"ts": datetime.now().isoformat(timespec="seconds"), "kind": "REPAIR", "msg": text[:500]}
        )
        CHANGE_LOG_JSON.write_text(json.dumps(clog, indent=2), encoding="utf-8")


def main():
    df = pd.read_csv(LABELS / "chunk_labels_all.csv")
    fp_sources = load_all_fp_sources()
    print(f"FP sources loaded: {len(fp_sources)}")

    df2 = retag_hard_negatives(df, fp_sources)
    df2.to_csv(LABELS / "chunk_labels_all.csv", index=False)
    hard_src = write_hard_neg_docs(df2, fp_sources)

    train_df, val_df, test_df, notes = stratified_split_by_key(df2)
    for n in notes:
        print("[SPLIT]", n)

    train_df = attach_existing_augmentations(train_df)

    train_df.to_csv(SPLITS / "train.csv", index=False)
    val_df.to_csv(SPLITS / "val.csv", index=False)
    test_df.to_csv(SPLITS / "test.csv", index=False)

    def cov(d):
        return {
            "rows": len(d),
            "keys": int(d["source_key"].nunique()) if "source_key" in d.columns else None,
            "sources": int(d["source"].nunique()),
            "labels": dict(Counter(d["label"].astype(int))),
            "aug_idx": dict(Counter(d["aug_idx"].astype(int))),
            "strata": dict(Counter(d["stratum"])),
            "buckets": dict(Counter(d["bucket"])),
        }

    summary = {
        "repair_ts": datetime.now().isoformat(timespec="seconds"),
        "hard_negative_sources": int(len(hard_src)),
        "hard_negative_chunks": int(df2["bucket"].isin(["hard_negative_scream_like", "hard_negative_esc50_fp"]).sum()),
        "fp_sources_known": len(fp_sources),
        "source_key_overlap_train_test": int(len(set(train_df.source_key) & set(test_df.source_key))),
        "source_name_overlap_train_test_scream_pair_blocked": True,
        "train": cov(train_df),
        "validation": cov(val_df),
        "test": cov(test_df),
        "test_distress_strata": sorted(test_df.loc[test_df.label == 1, "stratum"].unique().tolist()),
        "ready_status": "SPLITS REPAIRED — run embed_audio_v3.py for embedding cache",
    }
    # merge into summary.json
    sp = DERIVED / "summary.json"
    old = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    old.update(summary)
    sp.write_text(json.dumps(old, indent=2), encoding="utf-8")

    report = [
        "## Split/label repair",
        f"Timestamp: {summary['repair_ts']}",
        f"- Split unit changed to `source_key` (YouTube ID for Screaming/NotScreaming pairs; original_path otherwise).",
        f"- Hard-negative gate tightened to likeness>={NOTSCREAM_HARD_MIN} OR audio_v2 FP source.",
        f"- Hard-negative sources now: {summary['hard_negative_sources']} (chunks {summary['hard_negative_chunks']})",
        f"- source_key overlap train∩test: {summary['source_key_overlap_train_test']}",
        f"- Test distress strata: {summary['test_distress_strata']}",
        f"- Train rows (with aug): {summary['train']['rows']}",
        f"- Val rows: {summary['validation']['rows']}",
        f"- Test rows: {summary['test']['rows']}",
        "",
        "```json",
        json.dumps(summary, indent=2),
        "```",
    ]
    append_report("\n".join(report))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
