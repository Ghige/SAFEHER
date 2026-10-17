"""Human Distress Gold v1: leakage, unverified labels, eval gate, no production mutation."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import evaluate_human_distress_gold_v1 as ev
import human_distress_gold_v1 as hdg
import prepare_human_distress_gold_v1 as prep

AI_ROOT = Path(__file__).resolve().parents[1]
PROD_TFLITE = AI_ROOT / "models" / "final" / "yamnet_distress_quant.tflite"
BALANCED_KERAS = AI_ROOT / "data" / "models" / "audio_balanced_v1" / "audio_distress_classifier.keras"
DECISION = AI_ROOT.parents[0] / "safeher_android" / "app" / "src" / "main" / "java" / "com" / "safeher" / "app" / "services" / "ai" / "DecisionContract.kt"


def test_phrase_taxonomy_matches_repo_definitions():
    assert hdg.PHRASE_CATEGORIES["help_me"]["display"] == "Help Me"
    assert hdg.PHRASE_CATEGORIES["madad_karo"]["display"] == "मदद करो"
    assert hdg.PHRASE_CATEGORIES["mujhe_bachao"]["display"] == "मुझे बचाओ"
    assert "madat_karo" in hdg.PHRASE_CATEGORIES
    assert "palice_call_martini" in hdg.PHRASE_CATEGORIES
    assert hdg.phrase_from_folder("help me") == "help_me"
    assert hdg.phrase_from_folder("Sendhelp") == "send_help"


def test_blocks_balanced_and_gold_eval_v1(tmp_path):
    blocked = hdg.load_block_sets()
    assert blocked["paths"]
    assert blocked["hashes"]
    assert blocked["gold_paths"] or blocked["gold_hashes"]
    used_hash = next(iter(blocked["hashes"]))
    assert (
        hdg.leakage_status(tmp_path / "x.wav", used_hash, "hash::fresh", "help_me", blocked)
        in {"BLOCKED_HASH", "BLOCKED_GOLD_EVAL_V1"}
    )


def test_folder_labels_are_not_verified():
    rows = prep.finalize(
        [
            {
                **{k: "" for k in hdg.MANIFEST_FIELDS},
                "file_path": "x.wav",
                "phrase_category": "help_me",
                "proposed_phrase_display": "Help Me",
                "leakage_status": "CLEAN",
                "content_md5": "abc",
                "source_key": "hash::abc",
                "HUMAN_VERIFIED": True,
                "HUMAN_LABEL": "DISTRESS",
            }
        ]
    )
    assert rows[0]["HUMAN_VERIFIED"] is False
    assert rows[0]["HUMAN_LABEL"] == ""
    assert rows[0]["folder_label_is_not_gold"] is True


def test_official_eval_requires_verified_labels(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "OUT", tmp_path)
    pd.DataFrame(
        [{"sample_id": "HDG1-help_me-0001", "file_path": "missing.wav", "phrase_category": "help_me", "language": "english"}]
    ).to_csv(tmp_path / "candidates.csv", index=False)
    pd.DataFrame(columns=["sample_id", "reviewer_id", "manual_verdict", "confirmed_category", "review_timestamp", "notes"]).to_csv(
        tmp_path / "reviews.csv", index=False
    )
    result = ev.evaluate()
    assert result["status"] == "NOT_RUN"
    assert result["n_verified"] == 0


def test_uncertain_is_not_verified(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "OUT", tmp_path)
    pd.DataFrame([{"sample_id": "HDG1-help_me-0001", "file_path": "missing.wav", "phrase_category": "help_me", "language": "english"}]).to_csv(
        tmp_path / "candidates.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "sample_id": "HDG1-help_me-0001",
                "reviewer_id": "r",
                "manual_verdict": "UNCERTAIN",
                "confirmed_category": "help_me",
                "review_timestamp": "2026-10-05T00:00:00Z",
                "notes": "",
            }
        ]
    ).to_csv(tmp_path / "reviews.csv", index=False)
    result = ev.evaluate()
    assert result["status"] == "NOT_RUN"


def test_prepare_does_not_write_audio_copies():
    src = Path(prep.__file__).read_text(encoding="utf-8")
    assert "sf.write" not in src
    assert "shutil.copy" not in src


def test_production_artifacts_untouched():
    assert PROD_TFLITE.is_file()
    assert PROD_TFLITE.stat().st_size == 3_827_768
    assert BALANCED_KERAS.is_file()
    text = DECISION.read_text(encoding="utf-8")
    assert "TIER_IMMEDIATE_SOS = 65" in text
    assert "CONFIRM_FIRST_BETA = true" in text


def test_prepared_candidates_are_clean_and_unverified():
    path = hdg.OUT / "candidates.csv"
    if not path.is_file():
        return
    df = pd.read_csv(path)
    required = {
        "sample_id",
        "file_path",
        "phrase_category",
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
    }
    assert required.issubset(set(df.columns))
    if df.empty:
        return
    assert (df["leakage_status"] == "CLEAN").all()
    verified = df["HUMAN_VERIFIED"].astype(str).str.lower().isin(["true", "1"])
    reviews = hdg.OUT / "reviews.csv"
    if reviews.is_file() and pd.read_csv(reviews).empty:
        assert (~verified).all()


def test_blocked_existing_phrase_recordings():
    blocked = hdg.OUT / "blocked.csv"
    if not blocked.is_file():
        return
    df = pd.read_csv(blocked)
    if df.empty:
        return
    assert df["leakage_status"].ne("CLEAN").all()
    # Existing project phrase files must not appear as clean candidates.
    cand = pd.read_csv(hdg.OUT / "candidates.csv") if (hdg.OUT / "candidates.csv").is_file() else pd.DataFrame()
    if cand.empty:
        return
    assert set(cand["file_path"].astype(str)).isdisjoint(set(df["file_path"].astype(str)))


def test_summary_says_eval_only():
    path = hdg.OUT / "summary.json"
    if not path.is_file():
        return
    summary = json.loads(path.read_text(encoding="utf-8"))
    assert summary["no_retrain"] is True
    assert summary["combined_with_training"] is False
    assert summary["folder_labels_are_not_gold"] is True
