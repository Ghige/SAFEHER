"""
SafeHer — Gold Evaluation Set v1 (candidates only).

Does NOT retrain.
Does NOT overwrite production TFLite / Keras baselines / DecisionContract.
Does NOT delete or rewrite original audio.
Does NOT treat folder labels as verified gold.

Usage (from safeher_ai/):
    python training/prepare_gold_eval_v1.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

AI_ROOT = Path(__file__).resolve().parents[1]
BALANCED = AI_ROOT / "data" / "derived" / "audio_balanced_v1"
OUT = AI_ROOT / "data" / "derived" / "gold_eval_v1"
FSD_META = AI_ROOT / "data" / "derived" / "fsd50k_distress" / "metadata" / "fsd50k_distress_metadata.csv"
BERST_META = AI_ROOT / "data" / "derived" / "distress_collection_v2" / "metadata" / "collection_metadata.csv"
AUDIOSET_ROOT = AI_ROOT / "data" / "derived" / "audioset_screaming"

TARGET_DISTRESS = 500
TARGET_HARD_NEGATIVE = 1000
RANDOM_STATE = 42

# Official ESC-50 taxonomy (Piczak). Filename ends with -<class_id>.
ESC50_CLASSES = {
    0: "dog",
    1: "rooster",
    2: "pig",
    3: "cow",
    4: "frog",
    5: "cat",
    6: "hen",
    7: "insects",
    8: "sheep",
    9: "crow",
    10: "rain",
    11: "sea_waves",
    12: "crackling_fire",
    13: "crickets",
    14: "chirping_birds",
    15: "water_drops",
    16: "wind",
    17: "pouring_water",
    18: "toilet_flush",
    19: "thunderstorm",
    20: "crying_baby",
    21: "sneezing",
    22: "clapping",
    23: "breathing",
    24: "coughing",
    25: "footsteps",
    26: "laughing",
    27: "brushing_teeth",
    28: "snoring",
    29: "drinking_sipping",
    30: "door_wood_knock",
    31: "mouse_click",
    32: "keyboard_typing",
    33: "door_wood_creaks",
    34: "can_opening",
    35: "washing_machine",
    36: "vacuum_cleaner",
    37: "clock_alarm",
    38: "clock_tick",
    39: "glass_breaking",
    40: "helicopter",
    41: "chainsaw",
    42: "siren",
    43: "car_horn",
    44: "engine",
    45: "train",
    46: "church_bells",
    47: "airplane",
    48: "fireworks",
    49: "hand_saw",
}

ESC50_HARD_GROUPS = {
    "laughing": {26},
    "talking_like": {20, 21, 22, 23, 24},
    "shout_like_non_distress": {0, 5},  # animal vocalizations can look scream-like
    "crowd_urban": {42, 43, 46, 48},
    "transport": {40, 44, 45, 47},
}

CANDIDATE_FIELDS = [
    "gold_id",
    "file_path",
    "file_id",
    "source_key",
    "original_category",
    "proposed_label",
    "category_group",
    "content_md5",
    "leakage_status",
    "human_verification_status",
    "HUMAN_VERIFIED",
    "origin",
    "folder",
    "phrase",
    "priority",
    "notes",
]

log = logging.getLogger("gold_eval_v1")


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


def resolve_ai_path(value: str) -> Path:
    p = Path(str(value))
    if p.is_absolute():
        return p
    return (AI_ROOT / p).resolve()


def esc50_class_id(filename: str) -> int | None:
    stem = Path(filename).stem
    if "-" not in stem:
        return None
    tail = stem.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else None


def hn_group_for_row(row: pd.Series) -> str:
    folder = str(row.get("folder") or "")
    source = str(row.get("source") or "")
    if folder == "NotScreaming":
        return "shouting_non_distress"
    if folder == "Traffic":
        return "traffic"
    if folder in {"cars", "Truck", "bics"}:
        return "vehicles"
    if folder in {"airplane", "helicopter"}:
        return "transport"
    if folder == "_root":
        return "ambient_root"
    if folder == "ESC-50-master":
        cid = esc50_class_id(source)
        name = ESC50_CLASSES.get(cid if cid is not None else -1, "esc50_other")
        if cid in ESC50_HARD_GROUPS["laughing"]:
            return "laughing"
        if cid in ESC50_HARD_GROUPS["talking_like"]:
            return f"talking_like_{name}"
        if cid in ESC50_HARD_GROUPS["crowd_urban"]:
            return f"crowd_urban_{name}"
        if cid in ESC50_HARD_GROUPS["transport"]:
            return f"transport_{name}"
        if cid in ESC50_HARD_GROUPS["shout_like_non_distress"]:
            return f"scream_like_non_distress_{name}"
        return f"esc50_{name}"
    return folder or "other_normal"


def hn_priority(group: str) -> int:
    if group == "shouting_non_distress":
        return 10
    if group == "laughing":
        return 20
    if group.startswith("talking_like_"):
        return 30
    if group.startswith("scream_like_non_distress_"):
        return 35
    if group == "traffic":
        return 40
    if group.startswith("crowd_urban_"):
        return 45
    if group.startswith("transport_") or group == "transport":
        return 50
    if group == "vehicles":
        return 55
    if group == "ambient_root":
        return 70
    if group.startswith("esc50_"):
        return 80
    if group.startswith("berst_"):
        return 90
    return 99


def load_used_blocks() -> dict:
    used_frames = []
    for name in ("train_sources.csv", "val_sources.csv", "test_sources.csv"):
        path = BALANCED / "splits" / name
        if path.is_file():
            used_frames.append(pd.read_csv(path))
    if not used_frames:
        raise FileNotFoundError("Balanced-v1 split source CSVs are missing")
    used = pd.concat(used_frames, ignore_index=True)
    chunks = BALANCED / "chunk_manifest.csv"
    chunk_df = pd.read_csv(chunks) if chunks.is_file() else pd.DataFrame()

    source_keys = set(used["source_key"].astype(str))
    hashes = set(used["content_md5"].astype(str))
    paths = set(used["original_path"].astype(str))
    if not chunk_df.empty:
        source_keys |= set(chunk_df["source_key"].astype(str))
        hashes |= set(chunk_df["content_md5"].astype(str))
        paths |= set(chunk_df["original_path"].astype(str))

    yt_keys = {k[4:] for k in source_keys if k.startswith("yt::")}
    for src in used.get("source", pd.Series(dtype=str)).astype(str):
        if src:
            yt_keys.add(youtube_key(src))
    return {
        "source_keys": source_keys,
        "hashes": hashes,
        "paths": paths,
        "yt_keys": yt_keys,
        "used_df": used,
    }


def leakage_for(source_key: str, content_md5: str, path: str, folder: str, source: str, blocked: dict) -> str:
    if path in blocked["paths"]:
        return "BLOCKED_PATH"
    if content_md5 and content_md5 in blocked["hashes"]:
        return "BLOCKED_HASH"
    if source_key and source_key in blocked["source_keys"]:
        return "BLOCKED_SOURCE_KEY"
    if folder in {"Screaming", "NotScreaming"} and youtube_key(source) in blocked["yt_keys"]:
        return "BLOCKED_YT_GROUP"
    if source_key.startswith("yt::") and source_key[4:] in blocked["yt_keys"]:
        return "BLOCKED_YT_GROUP"
    return "CLEAN"


def leftover_from_balanced(blocked: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    manifest = pd.read_csv(BALANCED / "source_manifest.csv")
    statuses = []
    for row in manifest.itertuples(index=False):
        statuses.append(
            leakage_for(
                str(row.source_key),
                str(row.content_md5),
                str(row.original_path),
                str(row.folder),
                str(row.source),
                blocked,
            )
        )
    manifest["leakage_status"] = statuses
    clean = manifest[manifest["leakage_status"] == "CLEAN"].copy()
    leaked = manifest[manifest["leakage_status"] != "CLEAN"].copy()
    return clean, leaked


def cached_md5(path: Path, cache: dict[str, str]) -> str:
    key = str(path.resolve()) if path.exists() else str(path)
    stamp = ""
    if path.exists():
        st = path.stat()
        stamp = f"{st.st_size}:{int(st.st_mtime)}"
    cache_key = f"{key}|{stamp}"
    if cache_key in cache:
        return cache[cache_key]
    digest = file_md5(path)
    cache[cache_key] = digest
    return digest


def load_hash_cache() -> dict[str, str]:
    path = OUT / "hash_cache.csv"
    if not path.is_file():
        return {}
    df = pd.read_csv(path)
    return {str(r.cache_key): str(r.content_md5) for r in df.itertuples(index=False)}


def save_hash_cache(cache: dict[str, str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [{"cache_key": k, "content_md5": v} for k, v in sorted(cache.items())]
    ).to_csv(OUT / "hash_cache.csv", index=False)


def collect_external_distress(blocked: dict, cache: dict[str, str]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    excluded: list[dict] = []

    if FSD_META.is_file():
        fsd = pd.read_csv(FSD_META)
        for rec in fsd.itertuples(index=False):
            path = resolve_ai_path(str(rec.wav_path))
            label = str(rec.source_label)
            group = "screaming" if "Screaming" in label else (
                "crying" if "Crying" in label else (
                    "shout_yell" if "Shout" in label or "Yell" in label else (
                        "gasp" if "Gasp" in label else "fsd_other"
                    )
                )
            )
            if not path.is_file():
                excluded.append(_excl(path, f"fsd::{rec.freesound_id}", label, "MISSING_FILE", "fsd50k"))
                continue
            digest = cached_md5(path, cache)
            key = f"fsd::{rec.freesound_id}"
            leak = leakage_for(key, digest, str(path), "fsd50k_distress", path.name, blocked)
            item = {
                "file_path": str(path),
                "file_id": str(rec.freesound_id),
                "source_key": key,
                "original_category": label,
                "proposed_label": "DISTRESS",
                "category_group": group,
                "content_md5": digest,
                "leakage_status": leak,
                "origin": "fsd50k_distress",
                "folder": "fsd50k_distress",
                "phrase": "",
                "priority": 20 if group == "screaming" else (40 if group == "crying" else 70),
                "notes": "Folder/metadata label is proposed only; not human-verified.",
            }
            (rows if leak == "CLEAN" else excluded).append(item if leak == "CLEAN" else _excl_from(item))

    if AUDIOSET_ROOT.is_dir():
        for path in sorted(AUDIOSET_ROOT.rglob("*.wav")):
            digest = cached_md5(path, cache)
            key = f"audioset::{path.stem}"
            leak = leakage_for(key, digest, str(path), "audioset_screaming", path.name, blocked)
            item = {
                "file_path": str(path),
                "file_id": path.stem,
                "source_key": key,
                "original_category": "AudioSet_screaming",
                "proposed_label": "DISTRESS",
                "category_group": "screaming",
                "content_md5": digest,
                "leakage_status": leak,
                "origin": "audioset_screaming",
                "folder": path.parent.name,
                "phrase": "",
                "priority": 30,
                "notes": "AudioSet screaming folder label is proposed only; not human-verified.",
            }
            (rows if leak == "CLEAN" else excluded).append(item if leak == "CLEAN" else _excl_from(item))

    if BERST_META.is_file():
        berst = pd.read_csv(BERST_META)
        for rec in berst.itertuples(index=False):
            path = resolve_ai_path(str(rec.local_path))
            prelim = str(rec.preliminary_category)
            src_label = str(rec.source_label)
            if prelim not in {"LIKELY_DISTRESS", "POSSIBLE_DISTRESS"}:
                continue
            if not path.is_file():
                excluded.append(_excl(path, f"berst::{rec.clip_id}", src_label, "MISSING_FILE", "berst"))
                continue
            digest = cached_md5(path, cache)
            key = f"berst::{rec.recording_group}"
            leak = leakage_for(key, digest, str(path), "berst", path.name, blocked)
            item = {
                "file_path": str(path),
                "file_id": str(rec.clip_id),
                "source_key": key,
                "original_category": src_label,
                "proposed_label": "DISTRESS",
                "category_group": "screaming" if "fear_shout" in src_label else "fear_acted",
                "content_md5": digest,
                "leakage_status": leak,
                "origin": "berst",
                "folder": "source_01_berst",
                "phrase": "",
                "priority": 25 if prelim == "LIKELY_DISTRESS" else 55,
                "notes": f"BERSt {prelim} / {rec.category_basis}. Proposed only; not human-verified.",
                "_speaker": str(rec.speaker_id),
            }
            (rows if leak == "CLEAN" else excluded).append(item if leak == "CLEAN" else _excl_from(item))

    return rows, excluded


def collect_external_hard_negatives(blocked: dict, cache: dict[str, str]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    excluded: list[dict] = []
    if not BERST_META.is_file():
        return rows, excluded
    berst = pd.read_csv(BERST_META)
    for rec in berst.itertuples(index=False):
        if str(rec.preliminary_category) != "HARD_NEGATIVE":
            continue
        path = resolve_ai_path(str(rec.local_path))
        src_label = str(rec.source_label)
        if not path.is_file():
            excluded.append(_excl(path, f"berst::{rec.clip_id}", src_label, "MISSING_FILE", "berst"))
            continue
        digest = cached_md5(path, cache)
        key = f"berst::{rec.recording_group}"
        leak = leakage_for(key, digest, str(path), "berst", path.name, blocked)
        shout = "shouting_non_distress" if src_label.endswith("_shout") else "talking"
        item = {
            "file_path": str(path),
            "file_id": str(rec.clip_id),
            "source_key": key,
            "original_category": src_label,
            "proposed_label": "HARD_NEGATIVE",
            "category_group": f"berst_{shout}",
            "content_md5": digest,
            "leakage_status": leak,
            "origin": "berst",
            "folder": "source_01_berst",
            "phrase": "",
            "priority": 60 if shout == "shouting_non_distress" else 85,
            "notes": "BERSt prompted non-help speech/shout. Proposed HARD_NEGATIVE only.",
            "_speaker": str(rec.speaker_id),
        }
        (rows if leak == "CLEAN" else excluded).append(item if leak == "CLEAN" else _excl_from(item))
    return rows, excluded


def _excl(path: Path, source_key: str, category: str, status: str, origin: str) -> dict:
    return {
        "file_path": str(path),
        "source_key": source_key,
        "original_category": category,
        "proposed_label": "",
        "content_md5": "",
        "leakage_status": status,
        "origin": origin,
        "reason": status,
    }


def _excl_from(item: dict) -> dict:
    return {
        "file_path": item["file_path"],
        "source_key": item["source_key"],
        "original_category": item["original_category"],
        "proposed_label": item.get("proposed_label", ""),
        "content_md5": item.get("content_md5", ""),
        "leakage_status": item["leakage_status"],
        "origin": item.get("origin", ""),
        "reason": item["leakage_status"],
    }


def leftover_to_candidates(clean: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    distress, normal = [], []
    for row in clean.itertuples(index=False):
        label = int(row.label)
        folder = str(row.folder)
        source = str(row.source)
        phrase = str(getattr(row, "phrase", "") or "")
        if label == 1:
            group = phrase or folder.lower().replace(" ", "_")
            distress.append({
                "file_path": str(row.original_path),
                "file_id": Path(row.original_path).stem,
                "source_key": str(row.source_key),
                "original_category": folder if not phrase else phrase,
                "proposed_label": "DISTRESS",
                "category_group": group,
                "content_md5": str(row.content_md5),
                "leakage_status": "CLEAN",
                "origin": str(row.origin),
                "folder": folder,
                "phrase": phrase,
                "priority": 5,
                "notes": "Leftover unique raw distress unused by Balanced-v1. Folder label is not verified.",
            })
        else:
            s = pd.Series({
                "folder": folder,
                "source": source,
            })
            group = hn_group_for_row(s)
            normal.append({
                "file_path": str(row.original_path),
                "file_id": Path(row.original_path).stem,
                "source_key": str(row.source_key),
                "original_category": folder if folder != "ESC-50-master" else f"ESC-50:{ESC50_CLASSES.get(esc50_class_id(source) or -1, 'other')}",
                "proposed_label": "HARD_NEGATIVE",
                "category_group": group,
                "content_md5": str(row.content_md5),
                "leakage_status": "CLEAN",
                "origin": str(row.origin),
                "folder": folder,
                "phrase": "",
                "priority": hn_priority(group),
                "notes": "Leftover unique unused Balanced-v1 normal. Folder label is not verified.",
            })
    return distress, normal


def sample_unique(items: list[dict], n: int, rng: np.random.RandomState, per_key_cap: int = 2, per_speaker_cap: int = 4) -> list[dict]:
    if n <= 0 or not items:
        return []
    by_pri: dict[int, list[dict]] = defaultdict(list)
    for item in items:
        by_pri[int(item.get("priority", 99))].append(item)
    chosen: list[dict] = []
    used_hash: set[str] = set()
    used_key_count: dict[str, int] = defaultdict(int)
    used_spk_count: dict[str, int] = defaultdict(int)
    used_path: set[str] = set()

    def accept(item: dict) -> bool:
        h = item.get("content_md5") or ""
        if h and h in used_hash:
            return False
        if item["file_path"] in used_path:
            return False
        if used_key_count[item["source_key"]] >= per_key_cap:
            return False
        spk = item.get("_speaker")
        if spk and used_spk_count[spk] >= per_speaker_cap:
            return False
        return True

    def take(item: dict) -> None:
        chosen.append(item)
        if item.get("content_md5"):
            used_hash.add(item["content_md5"])
        used_path.add(item["file_path"])
        used_key_count[item["source_key"]] += 1
        if item.get("_speaker"):
            used_spk_count[item["_speaker"]] += 1

    for pri in sorted(by_pri):
        pool = [x for x in by_pri[pri] if accept(x)]
        rng.shuffle(pool)
        for item in pool:
            if len(chosen) >= n:
                return chosen
            if accept(item):
                take(item)
    return chosen


def sample_distress(items: list[dict], n: int, rng: np.random.RandomState) -> list[dict]:
    """Keep leftover raw first, then mix FSD / BERSt / AudioSet screaming. No duplicates."""
    chosen: list[dict] = []
    used_h: set[str] = set()
    used_k: set[str] = set()
    used_p: set[str] = set()
    used_spk: dict[str, int] = defaultdict(int)

    def accept(item: dict) -> bool:
        if item["content_md5"] in used_h or item["file_path"] in used_p or item["source_key"] in used_k:
            return False
        spk = item.get("_speaker")
        if spk and used_spk[spk] >= 3:
            return False
        return True

    def take(item: dict) -> None:
        chosen.append(item)
        used_h.add(item["content_md5"])
        used_p.add(item["file_path"])
        used_k.add(item["source_key"])
        if item.get("_speaker"):
            used_spk[item["_speaker"]] += 1

    def fill(pool: list[dict], need: int) -> None:
        avail = [x for x in pool if accept(x)]
        rng.shuffle(avail)
        for item in avail:
            if need <= 0:
                return
            if accept(item):
                take(item)
                need -= 1

    leftover = [x for x in items if x.get("origin") in {"raw_distress", "speech_emergency"}]
    fill(leftover, n)
    preferred = [
        ("fsd50k_distress", "screaming", 200),
        ("berst", "screaming", 160),
        ("audioset_screaming", "screaming", 140),
    ]
    for origin, group, quota in preferred:
        if len(chosen) >= n:
            break
        fill(
            [x for x in items if x.get("origin") == origin and x.get("category_group") == group],
            min(quota, n - len(chosen)),
        )
    if len(chosen) < n:
        fill([x for x in items if x.get("category_group") == "screaming"], n - len(chosen))
    if len(chosen) < n:
        fill(items, n - len(chosen))
    return chosen[:n]


def sample_hard_negatives(items: list[dict], n: int, rng: np.random.RandomState) -> list[dict]:
    """Quota-fill difficult normal groups, then backfill. Never duplicate hashes."""
    quotas = [
        ("shouting_non_distress", 250),
        ("laughing", 40),
        ("talking_like_", 140),
        ("scream_like_non_distress_", 40),
        ("traffic", 40),
        ("crowd_urban_", 80),
        ("transport", 140),
        ("vehicles", 140),
        ("berst_shouting_non_distress", 80),
        ("berst_talking", 50),
        ("ambient_root", 60),
    ]
    chosen: list[dict] = []
    used = set()
    used_keys: set[str] = set()

    def matches(group: str, key: str) -> bool:
        if key.endswith("_"):
            return group.startswith(key)
        if key == "transport":
            return group == "transport" or group.startswith("transport_")
        return group == key

    def take_from(pool: list[dict], need: int) -> None:
        avail = [
            x
            for x in pool
            if x["content_md5"] not in used
            and x["file_path"] not in used
            and x["source_key"] not in used_keys
        ]
        rng.shuffle(avail)
        for item in avail:
            if need <= 0:
                return
            if item["content_md5"] in used or item["file_path"] in used or item["source_key"] in used_keys:
                continue
            chosen.append(item)
            used.add(item["content_md5"])
            used.add(item["file_path"])
            used_keys.add(item["source_key"])
            need -= 1

    remaining = list(items)
    for key, quota in quotas:
        if len(chosen) >= n:
            break
        pool = [x for x in remaining if matches(str(x["category_group"]), key)]
        take_from(pool, min(quota, n - len(chosen)))
    if len(chosen) < n:
        take_from(remaining, n - len(chosen))
    return chosen[:n]


def finalize_rows(rows: list[dict], prefix: str) -> list[dict]:
    out = []
    for i, row in enumerate(rows, start=1):
        rec = {k: row.get(k, "") for k in CANDIDATE_FIELDS if k not in {"gold_id", "human_verification_status", "HUMAN_VERIFIED"}}
        rec["gold_id"] = f"{prefix}-{i:04d}"
        rec["human_verification_status"] = "UNREVIEWED"
        rec["HUMAN_VERIFIED"] = False
        rec["file_path"] = row["file_path"]
        rec["file_id"] = row["file_id"]
        rec["source_key"] = row["source_key"]
        rec["original_category"] = row["original_category"]
        rec["proposed_label"] = row["proposed_label"]
        rec["category_group"] = row["category_group"]
        rec["content_md5"] = row["content_md5"]
        rec["leakage_status"] = row["leakage_status"]
        rec["origin"] = row["origin"]
        rec["folder"] = row.get("folder", "")
        rec["phrase"] = row.get("phrase", "")
        rec["priority"] = row.get("priority", 99)
        rec["notes"] = row.get("notes", "")
        out.append(rec)
    return out


def write_review_queue(candidates: list[dict]) -> None:
    fields = CANDIDATE_FIELDS + ["review_order"]
    rows = []
    for i, rec in enumerate(candidates, start=1):
        item = dict(rec)
        item["review_order"] = i
        rows.append(item)
    pd.DataFrame(rows, columns=fields).to_csv(OUT / "gold_review_queue.csv", index=False)


def write_review_sheet(candidates: list[dict], summary: dict) -> None:
    html = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>SafeHer Gold Eval v1 — Review sheet</title>",
        "<style>body{font:14px/1.45 system-ui,sans-serif;margin:24px;color:#111}",
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px 8px;text-align:left}",
        "th{background:#f3f3f3} .d{background:#ffe8e6} .n{background:#eef7ff} .warn{background:#fff3cd;padding:12px;border:1px solid #e0c36c;margin-bottom:16px}",
        "code{font-size:12px}</style></head><body>",
        "<h1>Gold Eval v1 review sheet</h1>",
        "<div class='warn'><b>Folder labels are not gold.</b> Mark every clip DISTRESS, NORMAL, or UNCERTAIN. ",
        "HUMAN_VERIFIED stays false until you save a DISTRESS or NORMAL verdict in the review app. ",
        "Do not use proposed_label as a verified label.</div>",
        f"<p>Generated {summary.get('generated_at','')} — "
        f"distress candidates {summary['candidates']['distress']} / "
        f"hard-negative candidates {summary['candidates']['hard_negative']}.</p>",
        "<p>Preferred workflow: <code>python training/gold_eval_v1_review.py</code> then open "
        "<code>http://127.0.0.1:8766/</code>.</p>",
        "<table><thead><tr><th>gold_id</th><th>proposed</th><th>group</th><th>original category</th>",
        "<th>source_key</th><th>HUMAN_VERIFIED</th><th>your verdict</th><th>path</th></tr></thead><tbody>",
    ]
    for rec in candidates:
        cls = "d" if rec["proposed_label"] == "DISTRESS" else "n"
        html.append(
            f"<tr class='{cls}'><td>{rec['gold_id']}</td><td>{rec['proposed_label']}</td>"
            f"<td>{rec['category_group']}</td><td>{rec['original_category']}</td>"
            f"<td><code>{rec['source_key']}</code></td><td>false</td>"
            f"<td>DISTRESS / NORMAL / UNCERTAIN</td><td><code>{rec['file_path']}</code></td></tr>"
        )
    html.append("</tbody></table></body></html>")
    (OUT / "review_sheet.html").write_text("\n".join(html), encoding="utf-8")


def prepare() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    blocked = load_used_blocks()
    leftover_clean, leftover_leaked = leftover_from_balanced(blocked)
    cache = load_hash_cache()

    raw_d, raw_n = leftover_to_candidates(leftover_clean)
    ext_d, ext_d_ex = collect_external_distress(blocked, cache)
    ext_n, ext_n_ex = collect_external_hard_negatives(blocked, cache)
    save_hash_cache(cache)

    rng = np.random.RandomState(RANDOM_STATE)
    distress_pool = raw_d + ext_d
    normal_pool = raw_n + ext_n
    distress_sel = sample_distress(distress_pool, TARGET_DISTRESS, rng)
    distress_keys = {r["source_key"] for r in distress_sel}
    distress_hashes = {r["content_md5"] for r in distress_sel}
    hn_pool = [
        r
        for r in normal_pool
        if r["source_key"] not in distress_keys and r["content_md5"] not in distress_hashes
    ]
    normal_sel = sample_hard_negatives(hn_pool, TARGET_HARD_NEGATIVE, rng)

    distress_rows = finalize_rows(distress_sel, "GEV1-D")
    normal_rows = finalize_rows(normal_sel, "GEV1-N")
    candidates = distress_rows + normal_rows
    cand_df = pd.DataFrame(candidates, columns=CANDIDATE_FIELDS)
    cand_df.to_csv(OUT / "gold_candidates.csv", index=False)
    write_review_queue(candidates)

    excluded_rows = leftover_leaked.assign(reason=leftover_leaked["leakage_status"]).to_dict("records")
    excluded_rows.extend(ext_d_ex)
    excluded_rows.extend(ext_n_ex)
    # Also count unused pool not selected (not leakage — surplus)
    selected_paths = {r["file_path"] for r in candidates}
    surplus = [r for r in distress_pool + normal_pool if r["file_path"] not in selected_paths]
    excl_df = pd.DataFrame(excluded_rows)
    if not excl_df.empty:
        keep_cols = [c for c in ["file_path", "source_key", "original_category", "proposed_label", "content_md5", "leakage_status", "origin", "reason"] if c in excl_df.columns]
        excl_df[keep_cols].to_csv(OUT / "gold_excluded.csv", index=False)
    else:
        pd.DataFrame(columns=["file_path", "source_key", "leakage_status", "reason"]).to_csv(OUT / "gold_excluded.csv", index=False)
    pd.DataFrame(surplus).to_csv(OUT / "gold_surplus_unused.csv", index=False)

    reviews_path = OUT / "gold_reviews.csv"
    if not reviews_path.is_file():
        pd.DataFrame(columns=[
            "gold_id", "reviewer_id", "manual_verdict", "review_timestamp", "notes"
        ]).to_csv(reviews_path, index=False)

    phrase_shortfall = {
        "Help Me": 0,
        "Madad Karo / madat karo": 0,
        "Mujhe Bachao": 0,
        "Call Police": 0,
        "Sendhelp": 0,
        "I Need Help": 0,
        "Screaming (leftover unique raw)": int(sum(1 for r in raw_d if str(r.get("folder")) == "Screaming")),
    }

    d_groups = pd.Series([r["category_group"] for r in distress_rows]).value_counts().to_dict()
    n_groups = pd.Series([r["category_group"] for r in normal_rows]).value_counts().to_dict()
    leak_counts = leftover_leaked["leakage_status"].value_counts().to_dict() if not leftover_leaked.empty else {}
    leak_counts["external_blocked"] = int(len(ext_d_ex) + len(ext_n_ex))

    summary = {
        "generated_at": utc_now(),
        "no_retrain": True,
        "no_production_overwrite": True,
        "no_original_audio_deleted": True,
        "no_augmentation": True,
        "folder_labels_are_not_gold": True,
        "targets": {"distress": TARGET_DISTRESS, "hard_negative": TARGET_HARD_NEGATIVE},
        "available_clean_pool": {
            "leftover_raw_distress": len(raw_d),
            "leftover_raw_normal": len(raw_n),
            "external_distress": len(ext_d),
            "external_hard_negative": len(ext_n),
        },
        "candidates": {
            "distress": len(distress_rows),
            "hard_negative": len(normal_rows),
            "uncertain": 0,
            "human_verified_true": 0,
            "target_distress_met": len(distress_rows) >= TARGET_DISTRESS,
            "target_hard_negative_met": len(normal_rows) >= TARGET_HARD_NEGATIVE,
        },
        "excluded_leakage_or_duplicate": {
            "balanced_v1_blocked_sources": int(len(leftover_leaked)),
            "external_blocked": int(len(ext_d_ex) + len(ext_n_ex)),
            "by_reason": leak_counts,
        },
        "distress_by_group": d_groups,
        "distress_by_origin": pd.Series([r["origin"] for r in distress_rows]).value_counts().to_dict(),
        "hard_negative_by_group": n_groups,
        "hard_negative_by_origin": pd.Series([r["origin"] for r in normal_rows]).value_counts().to_dict(),
        "priority_phrase_leftover_in_gold": phrase_shortfall,
        "priority_phrase_note": (
            "All unique Help Me / Madad Karo / Mujhe Bachao / Call Police / "
            "Sendhelp / I Need Help / raw Screaming sources were consumed by "
            "Balanced-v1 train/val/test. They are excluded from Gold to prevent leakage."
        ),
        "human_verification_status": "UNREVIEWED",
        "HUMAN_VERIFIED_default": False,
        "official_threshold_eval": "NOT_RUN_UNTIL_VERIFIED_LABELS_EXIST",
        "review_howto": {
            "command": "python training/gold_eval_v1_review.py",
            "url": "http://127.0.0.1:8766/",
            "verdicts": ["DISTRESS", "NORMAL", "UNCERTAIN"],
            "sheet": str(OUT / "review_sheet.html"),
        },
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "threshold_results.json").write_text(
        json.dumps(
            {
                "status": "NOT_RUN",
                "reason": "No HUMAN_VERIFIED samples yet. Folder labels must not be scored as gold.",
                "n_verified": 0,
                "generated_at": utc_now(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_review_sheet(candidates, summary)
    log.info("Wrote %s (%s distress, %s hard-negative)", OUT, len(distress_rows), len(normal_rows))
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.parse_args()
    summary = prepare()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
