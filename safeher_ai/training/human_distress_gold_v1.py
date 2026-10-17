"""
Human Distress Gold Set v1 — shared taxonomy, leakage, and schema.

Evaluation-only. Does not retrain, export TFLite, or change DecisionContract.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from prepare_gold_eval_v1 import (
    AUDIOSET_ROOT,
    BALANCED,
    BERST_META,
    FSD_META,
    leakage_for,
    load_used_blocks,
    youtube_key,
)

AI_ROOT = Path(__file__).resolve().parents[1]
GOLD_V1 = AI_ROOT / "data" / "derived" / "gold_eval_v1"
OUT = AI_ROOT / "data" / "derived" / "human_distress_gold_v1"
INCOMING = AI_ROOT / "data" / "incoming" / "human_distress_gold_v1"
SPEECH_EM = AI_ROOT / "data" / "speech" / "emergency_phrases"
SPEECH_V2_EM = AI_ROOT / "data" / "derived" / "speech_v2_prep" / "emergency"
RAW_DISTRESS = AI_ROOT / "data" / "raw" / "distress"

AUDIO_EXTS = {".wav", ".flac", ".ogg", ".mp3", ".m4a"}
REVIEW_VERDICTS = ("DISTRESS", "NORMAL", "UNCERTAIN")
LEFTOVER_SCREAM_CAP_PER_ORIGIN = 40

# Project-defined human distress phrases (verified from speech README + SDE + raw folders).
PHRASE_CATEGORIES = {
    "help_me": {
        "display": "Help Me",
        "language": "english",
        "aliases": {"help me", "help_me", "helpme"},
    },
    "madad_karo": {
        "display": "मदद करो",
        "language": "hindi",
        "aliases": {"madad_karo", "madad karo", "मदद करो"},
    },
    "mujhe_bachao": {
        "display": "मुझे बचाओ",
        "language": "hindi",
        "aliases": {"mujhe_bachao", "mujhe bachao", "bachao", "मुझे बचाओ"},
    },
    "call_police": {
        "display": "Call Police",
        "language": "english",
        "aliases": {"call police", "call_police", "callpolice"},
    },
    "i_need_help": {
        "display": "I Need Help",
        "language": "english",
        "aliases": {"i need help", "i_need_help", "ineedhelp"},
    },
    "send_help": {
        "display": "Send Help",
        "language": "english",
        "aliases": {"send help", "send_help", "sendhelp"},
    },
    "screaming": {
        "display": "Screaming",
        "language": "",
        "aliases": {"screaming", "scream", "distress_scream"},
    },
    # Additional phrases already defined in this repository.
    "madat_karo": {
        "display": "मदत करो",
        "language": "marathi",
        "aliases": {"madat karo", "madat_karo", "madat_kara", "मदत करो"},
    },
    "palice_call_martini": {
        "display": "पोलिसांना कॉल करा / palice call martini",
        "language": "marathi",
        "aliases": {"palice call martini", "palice_call_martini"},
    },
    "please_help": {
        "display": "Please Help",
        "language": "english",
        "aliases": {"please_help", "please help", "save_me", "save me"},
    },
    "mala_vachva": {
        "display": "मला वाचवा",
        "language": "marathi",
        "aliases": {"mala_vachva", "vachva", "मला वाचवा"},
    },
}

PRIMARY_EVAL_CATEGORIES = [
    "help_me",
    "madad_karo",
    "mujhe_bachao",
    "call_police",
    "i_need_help",
    "send_help",
    "screaming",
]

MANIFEST_FIELDS = [
    "sample_id",
    "file_path",
    "phrase_category",
    "proposed_phrase_display",
    "speaker_id",
    "language",
    "environment",
    "recording_condition",
    "source",
    "HUMAN_VERIFIED",
    "HUMAN_LABEL",
    "reviewer",
    "notes",
    "leakage_status",
    "source_key",
    "content_md5",
    "human_verification_status",
    "folder_label_is_not_gold",
    "gender",
    "accent",
    "mic_distance",
    "speaking_speed",
    "emotional_intensity",
    "origin",
    "original_filename",
]

FOLDER_TO_PHRASE = {
    "help me": "help_me",
    "help_me": "help_me",
    "madad_karo": "madad_karo",
    "madad karo": "madad_karo",
    "mujhe_bachao": "mujhe_bachao",
    "mujhe bachao": "mujhe_bachao",
    "bachao": "mujhe_bachao",
    "call police": "call_police",
    "call_police": "call_police",
    "i need help": "i_need_help",
    "i_need_help": "i_need_help",
    "sendhelp": "send_help",
    "send_help": "send_help",
    "send help": "send_help",
    "screaming": "screaming",
    "madat karo": "madat_karo",
    "madat_karo": "madat_karo",
    "madat_kara": "madat_karo",
    "palice call martini": "palice_call_martini",
    "palice_call_martini": "palice_call_martini",
    "please_help": "please_help",
    "save_me": "please_help",
    "mala_vachva": "mala_vachva",
    "vachva": "mala_vachva",
    "conversational_normal": "conversational_normal",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_md5(path: Path, buf: int = 1024 * 1024) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            chunk = f.read(buf)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def normalize_path(value: str | Path) -> str:
    try:
        return str(Path(value).resolve())
    except OSError:
        return str(value)


def phrase_from_folder(name: str) -> str:
    key = name.strip().lower().replace("-", "_")
    if key in FOLDER_TO_PHRASE:
        return FOLDER_TO_PHRASE[key]
    collapsed = re.sub(r"[\s_]+", " ", name.strip().lower())
    return FOLDER_TO_PHRASE.get(collapsed, "")


def parse_incoming_stem(stem: str) -> dict:
    """Optional incoming filename tokens: speaker_gender_lang_env_distance_speed_intensity_phrase."""
    parts = [p for p in re.split(r"[_\-]+", stem.lower()) if p]
    known_gender = {"male", "female", "unknown"}
    known_lang = {"english", "en", "hindi", "hi", "marathi", "mr", "kannada", "kn"}
    known_env = {"quiet", "conversation", "traffic", "public", "indoor", "outdoor"}
    known_dist = {"near", "far"}
    known_speed = {"slow", "normal", "fast"}
    known_int = {"whisper", "conversational", "urgent", "scream", "loud"}
    lang_map = {"en": "english", "hi": "hindi", "mr": "marathi", "kn": "kannada"}
    out = {
        "speaker_id": "",
        "gender": "",
        "language": "",
        "environment": "",
        "mic_distance": "",
        "speaking_speed": "",
        "emotional_intensity": "",
    }
    for token in parts:
        if token.startswith("spk") or token.startswith("speaker"):
            out["speaker_id"] = token
        elif token in known_gender:
            out["gender"] = token
        elif token in known_lang:
            out["language"] = lang_map.get(token, token)
        elif token in known_env:
            out["environment"] = token
        elif token in known_dist:
            out["mic_distance"] = token
        elif token in known_speed:
            out["speaking_speed"] = token
        elif token in known_int:
            out["emotional_intensity"] = token
    return out


def source_key_for(path: Path, digest: str, phrase: str) -> str:
    if phrase == "screaming" and path.parent.name.lower() == "screaming":
        return f"yt::{youtube_key(path.name)}"
    return f"hash::{digest}"


def load_block_sets() -> dict:
    blocked = load_used_blocks()
    paths = {normalize_path(p) for p in blocked["paths"]}
    hashes = set(blocked["hashes"])
    keys = set(blocked["source_keys"])
    yt = set(blocked["yt_keys"])

    manifest = BALANCED / "source_manifest.csv"
    if manifest.is_file():
        src = pd.read_csv(manifest)
        paths |= {normalize_path(p) for p in src["original_path"].astype(str)}
        hashes |= set(src["content_md5"].astype(str))
        keys |= set(src["source_key"].astype(str))

    excluded = BALANCED / "excluded.csv"
    if excluded.is_file():
        ex = pd.read_csv(excluded, usecols=lambda c: c in {"original_path", "content_md5", "source_key", "source"})
        if "original_path" in ex.columns:
            paths |= {normalize_path(p) for p in ex["original_path"].dropna().astype(str)}
        if "content_md5" in ex.columns:
            hashes |= {h for h in ex["content_md5"].dropna().astype(str) if h}
        if "source_key" in ex.columns:
            keys |= {k for k in ex["source_key"].dropna().astype(str) if k}

    gold_paths: set[str] = set()
    gold_hashes: set[str] = set()
    gold_keys: set[str] = set()
    for name in ("gold_candidates.csv", "gold_surplus_unused.csv", "gold_review_queue.csv"):
        gpath = GOLD_V1 / name
        if not gpath.is_file():
            continue
        g = pd.read_csv(gpath)
        if "file_path" in g.columns:
            gold_paths |= {normalize_path(p) for p in g["file_path"].dropna().astype(str)}
        if "content_md5" in g.columns:
            gold_hashes |= {h for h in g["content_md5"].dropna().astype(str) if h}
        if "source_key" in g.columns:
            gold_keys |= {k for k in g["source_key"].dropna().astype(str) if k}
    paths |= gold_paths
    hashes |= gold_hashes
    keys |= gold_keys

    for root in (SPEECH_EM, SPEECH_V2_EM, RAW_DISTRESS):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in AUDIO_EXTS:
                paths.add(normalize_path(path))

    return {
        "paths": paths,
        "hashes": hashes,
        "source_keys": keys,
        "yt_keys": yt,
        "gold_paths": gold_paths,
        "gold_hashes": gold_hashes,
        "gold_keys": gold_keys,
        "used_df": blocked.get("used_df"),
    }


def leakage_status(path: Path, digest: str, source_key: str, phrase: str, blocked: dict) -> str:
    npath = normalize_path(path)
    if npath in blocked.get("gold_paths", set()) or digest in blocked.get("gold_hashes", set()) or source_key in blocked.get("gold_keys", set()):
        return "BLOCKED_GOLD_EVAL_V1"
    if npath in blocked["paths"]:
        return "BLOCKED_PATH"
    folder = path.parent.name
    return leakage_for(source_key, digest, str(path), folder, path.name, blocked)


def ensure_incoming_layout() -> None:
    INCOMING.mkdir(parents=True, exist_ok=True)
    for slug in list(PHRASE_CATEGORIES) + ["conversational_normal"]:
        d = INCOMING / slug
        d.mkdir(parents=True, exist_ok=True)
        keep = d / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
    schema = {
        "purpose": "Drop NEW recordings only. Do not copy Balanced-v1 or Gold Eval v1 files here.",
        "not_verified_until_review": True,
        "folder_names_are_not_gold": True,
        "verdicts": list(REVIEW_VERDICTS),
        "filename_hint": "spk01_female_english_traffic_far_fast_urgent_help_me.wav",
        "sidecar_csv": "collection_template.csv",
        "categories": {
            key: {**val, "aliases": sorted(val["aliases"])}
            for key, val in PHRASE_CATEGORIES.items()
        },
        "robustness_axes": [
            "multiple speakers",
            "male/female",
            "accents",
            "speaking speed",
            "quiet",
            "background conversation",
            "traffic",
            "public-place noise",
            "indoor/outdoor",
            "near/far mic",
            "emotional intensity",
            "conversational versions of the same phrase",
        ],
    }
    (INCOMING / "collection_schema.json").write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    template = INCOMING / "collection_template.csv"
    if not template.exists():
        pd.DataFrame(
            columns=[
                "filename",
                "phrase_category",
                "speaker_id",
                "language",
                "gender",
                "accent",
                "environment",
                "recording_condition",
                "mic_distance",
                "speaking_speed",
                "emotional_intensity",
                "notes",
            ]
        ).to_csv(template, index=False)
