"""
Prepare Human Distress Gold Set v1 candidates.

Does NOT retrain, copy/relabel used recordings, or treat folder names as gold.

Usage (from safeher_ai/):
    python training/prepare_human_distress_gold_v1.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_distress_gold_v1 import (  # noqa: E402
    AUDIOSET_ROOT,
    AUDIO_EXTS,
    BERST_META,
    FSD_META,
    INCOMING,
    LEFTOVER_SCREAM_CAP_PER_ORIGIN,
    MANIFEST_FIELDS,
    OUT,
    PHRASE_CATEGORIES,
    PRIMARY_EVAL_CATEGORIES,
    RAW_DISTRESS,
    SPEECH_EM,
    SPEECH_V2_EM,
    ensure_incoming_layout,
    file_md5,
    leakage_status,
    load_block_sets,
    normalize_path,
    parse_incoming_stem,
    phrase_from_folder,
    source_key_for,
    utc_now,
)
from prepare_gold_eval_v1 import resolve_ai_path  # noqa: E402

log = logging.getLogger("human_distress_gold_v1")


def load_sidecars() -> dict[str, dict]:
    rows = {}
    csv_path = INCOMING / "collection_template.csv"
    if not csv_path.is_file():
        return rows
    df = pd.read_csv(csv_path)
    if df.empty or "filename" not in df.columns:
        return rows
    for rec in df.itertuples(index=False):
        name = str(getattr(rec, "filename", "")).strip()
        if name:
            rows[name] = rec._asdict() if hasattr(rec, "_asdict") else rec._asdict()
    return rows


def blank_row() -> dict:
    return {k: "" for k in MANIFEST_FIELDS}


def candidate_from_path(
    path: Path,
    phrase: str,
    origin: str,
    blocked: dict,
    sidecar: dict | None = None,
) -> dict:
    npath = normalize_path(path)
    if npath in blocked.get("gold_paths", set()) or npath in blocked.get("paths", set()):
        digest = ""
        key = ""
        leak = "BLOCKED_GOLD_EVAL_V1" if npath in blocked.get("gold_paths", set()) else "BLOCKED_PATH"
    else:
        digest = file_md5(path)
        key = source_key_for(path, digest, phrase)
        leak = leakage_status(path, digest, key, phrase, blocked)
    parsed = parse_incoming_stem(path.stem)
    side = sidecar or {}
    display = PHRASE_CATEGORIES.get(phrase, {}).get("display", phrase)
    language = (
        str(side.get("language") or "")
        or parsed.get("language")
        or PHRASE_CATEGORIES.get(phrase, {}).get("language", "")
    )
    env = str(side.get("environment") or parsed.get("environment") or "UNKNOWN")
    cond = str(side.get("recording_condition") or "")
    if not cond:
        bits = [env]
        if parsed.get("mic_distance"):
            bits.append(parsed["mic_distance"])
        if parsed.get("emotional_intensity"):
            bits.append(parsed["emotional_intensity"])
        cond = " / ".join(b for b in bits if b and b != "UNKNOWN")
    row = blank_row()
    row.update(
        {
            "file_path": str(path.resolve()),
            "phrase_category": phrase,
            "proposed_phrase_display": display,
            "speaker_id": str(side.get("speaker_id") or parsed.get("speaker_id") or ""),
            "language": language,
            "environment": env,
            "recording_condition": cond or "UNKNOWN",
            "source": origin,
            "HUMAN_VERIFIED": False,
            "HUMAN_LABEL": "",
            "reviewer": "",
            "notes": (
                "Folder/filename is a proposed category only. "
                "Reviewer must confirm the intended phrase/distress context."
            ),
            "leakage_status": leak,
            "source_key": key,
            "content_md5": digest,
            "human_verification_status": "UNREVIEWED",
            "folder_label_is_not_gold": True,
            "gender": str(side.get("gender") or parsed.get("gender") or ""),
            "accent": str(side.get("accent") or ""),
            "mic_distance": str(side.get("mic_distance") or parsed.get("mic_distance") or ""),
            "speaking_speed": str(side.get("speaking_speed") or parsed.get("speaking_speed") or ""),
            "emotional_intensity": str(
                side.get("emotional_intensity") or parsed.get("emotional_intensity") or ""
            ),
            "origin": origin,
            "original_filename": path.name,
        }
    )
    return row


def scan_existing_phrase_roots(blocked: dict) -> list[dict]:
    rows = []
    roots = [
        (RAW_DISTRESS, "raw_distress"),
        (SPEECH_EM, "speech_emergency_phrases"),
        (SPEECH_V2_EM, "speech_v2_prep_emergency"),
    ]
    for root, origin in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in AUDIO_EXTS:
                continue
            phrase = phrase_from_folder(path.parent.name)
            if not phrase and origin == "speech_emergency_phrases":
                phrase = phrase_from_folder(path.parent.name)
            if not phrase:
                # raw Screaming / phrase folders only
                continue
            rows.append(candidate_from_path(path, phrase, origin, blocked))
    return rows


def scan_incoming(blocked: dict) -> list[dict]:
    sidecars = load_sidecars()
    rows = []
    if not INCOMING.exists():
        return rows
    for path in sorted(INCOMING.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTS:
            continue
        phrase = phrase_from_folder(path.parent.name)
        if not phrase:
            continue
        side = sidecars.get(path.name) or sidecars.get(str(path.relative_to(INCOMING)))
        rows.append(candidate_from_path(path, phrase, "incoming_new_recording", blocked, side))
    return rows


def scan_leftover_screaming(blocked: dict) -> list[dict]:
    rows = []
    if FSD_META.is_file():
        fsd = pd.read_csv(FSD_META)
        scream = fsd[fsd["source_label"].astype(str).str.contains("Screaming", na=False)]
        for rec in scream.itertuples(index=False):
            path = resolve_ai_path(str(rec.wav_path))
            if path.is_file():
                rows.append(candidate_from_path(path, "screaming", "fsd50k_distress_leftover", blocked))
    if AUDIOSET_ROOT.is_dir():
        for path in sorted(AUDIOSET_ROOT.rglob("*.wav")):
            rows.append(candidate_from_path(path, "screaming", "audioset_screaming_leftover", blocked))
    if BERST_META.is_file():
        berst = pd.read_csv(BERST_META)
        likely = berst[berst["preliminary_category"].astype(str) == "LIKELY_DISTRESS"]
        for rec in likely.itertuples(index=False):
            path = resolve_ai_path(str(rec.local_path))
            if path.is_file():
                row = candidate_from_path(path, "screaming", "berst_fear_shout_leftover", blocked)
                row["speaker_id"] = str(getattr(rec, "speaker_id", "") or row["speaker_id"])
                row["gender"] = str(getattr(rec, "gender", "") or row["gender"])
                row["language"] = str(getattr(rec, "language", "") or row["language"])
                row["notes"] = (
                    "BERSt prompted fear+shout leftover (not in Gold Eval v1). "
                    "Folder/metadata is not a verified gold label."
                )
                rows.append(row)
    return rows


def cap_leftover_screaming(rows: list[dict]) -> list[dict]:
    clean = [r for r in rows if r["leakage_status"] == "CLEAN"]
    kept = []
    per: dict[str, int] = {}
    used_hash = set()
    for row in clean:
        origin = row["origin"]
        if per.get(origin, 0) >= LEFTOVER_SCREAM_CAP_PER_ORIGIN:
            continue
        if row["content_md5"] in used_hash:
            continue
        kept.append(row)
        used_hash.add(row["content_md5"])
        per[origin] = per.get(origin, 0) + 1
    return kept


def finalize(rows: list[dict]) -> list[dict]:
    out = []
    for i, row in enumerate(rows, start=1):
        rec = dict(row)
        rec["sample_id"] = f"HDG1-{rec['phrase_category']}-{i:04d}"
        rec["HUMAN_VERIFIED"] = False
        rec["HUMAN_LABEL"] = ""
        rec["human_verification_status"] = "UNREVIEWED"
        rec["folder_label_is_not_gold"] = True
        out.append(rec)
    return out


def write_review_sheet(candidates: list[dict], summary: dict) -> None:
    html = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Human Distress Gold v1 review</title>",
        "<style>body{font:14px/1.45 system-ui;margin:24px}table{border-collapse:collapse;width:100%}",
        "th,td{border:1px solid #ccc;padding:6px 8px;text-align:left}th{background:#f3f3f3}",
        ".warn{background:#fff3cd;border:1px solid #e0c36c;padding:12px;margin-bottom:16px}</style></head><body>",
        "<h1>Human Distress Gold Set v1</h1>",
        "<div class='warn'><b>Folder names are not gold.</b> Confirm the clip is the intended phrase ",
        "in a real distress context, then mark DISTRESS, NORMAL, or UNCERTAIN.</div>",
        f"<p>Generated {summary.get('generated_at','')} — clean candidates {len(candidates)}.",
        " Review: <code>python training/human_distress_gold_v1_review.py</code> → ",
        "<code>http://127.0.0.1:8767/</code></p><table><thead><tr>",
        "<th>sample_id</th><th>proposed phrase</th><th>language</th><th>environment</th>",
        "<th>source</th><th>HUMAN_VERIFIED</th><th>verdict</th></tr></thead><tbody>",
    ]
    for rec in candidates:
        html.append(
            f"<tr><td>{rec['sample_id']}</td><td>{rec['proposed_phrase_display']}</td>"
            f"<td>{rec['language']}</td><td>{rec['environment']}</td><td>{rec['source']}</td>"
            f"<td>false</td><td>DISTRESS / NORMAL / UNCERTAIN</td></tr>"
        )
    html.append("</tbody></table></body></html>")
    (OUT / "review_sheet.html").write_text("\n".join(html), encoding="utf-8")


def prepare() -> dict:
    ensure_incoming_layout()
    OUT.mkdir(parents=True, exist_ok=True)
    blocked = load_block_sets()

    existing = scan_existing_phrase_roots(blocked)
    incoming = scan_incoming(blocked)
    leftover_all = scan_leftover_screaming(blocked)
    leftover_kept = cap_leftover_screaming(leftover_all)

    scanned = existing + incoming + leftover_all
    clean_incoming = [r for r in incoming if r["leakage_status"] == "CLEAN"]
    clean = clean_incoming + leftover_kept
    # de-dupe clean by hash/path
    seen = set()
    unique_clean = []
    for row in clean:
        sig = (row["content_md5"], normalize_path(row["file_path"]))
        if sig in seen:
            continue
        seen.add(sig)
        unique_clean.append(row)

    blocked_rows = [r for r in scanned if r["leakage_status"] != "CLEAN"]
    surplus_scream = [
        r
        for r in leftover_all
        if r["leakage_status"] == "CLEAN"
        and r["content_md5"] not in {x["content_md5"] for x in leftover_kept}
    ]

    candidates = finalize(unique_clean)
    cand_df = pd.DataFrame(candidates, columns=MANIFEST_FIELDS)
    cand_df.to_csv(OUT / "candidates.csv", index=False)
    cand_df.to_csv(OUT / "review_queue.csv", index=False)
    pd.DataFrame(blocked_rows, columns=MANIFEST_FIELDS).to_csv(OUT / "blocked.csv", index=False)
    if surplus_scream:
        pd.DataFrame(surplus_scream, columns=MANIFEST_FIELDS).to_csv(OUT / "surplus_screaming.csv", index=False)

    reviews = OUT / "reviews.csv"
    if not reviews.is_file():
        pd.DataFrame(
            columns=[
                "sample_id",
                "reviewer_id",
                "manual_verdict",
                "confirmed_category",
                "review_timestamp",
                "notes",
            ]
        ).to_csv(reviews, index=False)

    by_phrase = pd.Series([r["phrase_category"] for r in candidates]).value_counts().to_dict() if candidates else {}
    blocked_by_phrase = (
        pd.Series([r["phrase_category"] for r in blocked_rows]).value_counts().to_dict() if blocked_rows else {}
    )
    blocked_by_reason = (
        pd.Series([r["leakage_status"] for r in blocked_rows]).value_counts().to_dict() if blocked_rows else {}
    )

    missing_manual = {}
    for cat in PRIMARY_EVAL_CATEGORIES:
        n = int(by_phrase.get(cat, 0))
        if cat == "screaming":
            missing_manual[cat] = max(0, 40 - n)
        else:
            missing_manual[cat] = "collect_new_recordings" if n == 0 else 0

    summary = {
        "generated_at": utc_now(),
        "evaluation_only": True,
        "combined_with_training": False,
        "no_retrain": True,
        "no_production_overwrite": True,
        "folder_labels_are_not_gold": True,
        "primary_categories": PRIMARY_EVAL_CATEGORIES,
        "additional_project_phrases": [k for k in PHRASE_CATEGORIES if k not in PRIMARY_EVAL_CATEGORIES],
        "scanned": {
            "existing_project_phrase_files": len(existing),
            "incoming_new": len(incoming),
            "leftover_screaming_scanned": len(leftover_all),
        },
        "candidates": {
            "total": len(candidates),
            "by_phrase": by_phrase,
            "incoming_clean": len(clean_incoming),
            "leftover_screaming_clean_capped": len(leftover_kept),
        },
        "blocked": {
            "total": len(blocked_rows),
            "by_phrase": blocked_by_phrase,
            "by_reason": blocked_by_reason,
        },
        "human_verification": {
            "HUMAN_VERIFIED_true": 0,
            "DISTRESS": 0,
            "NORMAL": 0,
            "UNCERTAIN": 0,
            "UNREVIEWED": len(candidates),
        },
        "official_eval": "NOT_RUN_UNTIL_VERIFIED_LABELS_EXIST",
        "missing_data_to_collect_manually": missing_manual,
        "incoming_drop_folder": str(INCOMING),
        "review": {
            "command": "python training/human_distress_gold_v1_review.py",
            "url": "http://127.0.0.1:8767/",
            "verdicts": ["DISTRESS", "NORMAL", "UNCERTAIN"],
        },
        "notes": [
            "Every unique raw distress phrase source is already in Balanced-v1; those files are BLOCKED.",
            "speech/emergency_phrases and speech_v2_prep/emergency are copies of the same recordings and are BLOCKED.",
            "Leftover FSD/BERSt/AudioSet screaming is included only if it is not in Balanced-v1 or Gold Eval v1.",
            "Do not treat proposed_phrase_display as HUMAN_LABEL.",
        ],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "threshold_results.json").write_text(
        json.dumps(
            {
                "status": "NOT_RUN",
                "reason": "No HUMAN_VERIFIED samples. Folder labels must not be scored as gold.",
                "n_verified": 0,
                "generated_at": utc_now(),
                "production_threshold_changed": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_review_sheet(candidates, summary)
    log.info("Wrote %s candidates=%s blocked=%s", OUT, len(candidates), len(blocked_rows))
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
