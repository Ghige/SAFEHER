"""Gold Eval v1: leakage, unverified labels, no production mutation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import evaluate_gold_thresholds_v1 as ev
import prepare_gold_eval_v1 as prep

AI_ROOT = Path(__file__).resolve().parents[1]
BALANCED = AI_ROOT / "data" / "derived" / "audio_balanced_v1"
OUT = AI_ROOT / "data" / "derived" / "gold_eval_v1"
PROD_TFLITE = AI_ROOT / "models" / "final" / "yamnet_distress_quant.tflite"
PROD_ANDROID = AI_ROOT.parents[0] / "safeher_android" / "app" / "src" / "main" / "assets" / "yamnet_distress_quant.tflite"
BALANCED_KERAS = AI_ROOT / "data" / "models" / "audio_balanced_v1" / "audio_distress_classifier.keras"
LEGACY_KERAS = AI_ROOT / "models" / "final" / "safeher_classifier_20260705_1705.keras"


def test_leakage_blocks_used_source_keys_and_hashes():
    blocked = prep.load_used_blocks()
    assert blocked["source_keys"]
    assert blocked["hashes"]
    used_key = next(iter(blocked["source_keys"]))
    used_hash = next(iter(blocked["hashes"]))
    assert prep.leakage_for(used_key, "deadbeef", "nope.wav", "cars", "x.wav", blocked) == "BLOCKED_SOURCE_KEY"
    assert prep.leakage_for("hash::unused", used_hash, "nope.wav", "cars", "x.wav", blocked) == "BLOCKED_HASH"
    assert prep.leakage_for("hash::fresh", "freshhash", r"Z:\not\used.wav", "cars", "x.wav", blocked) == "CLEAN"
    if blocked["yt_keys"]:
        yt = next(iter(blocked["yt_keys"]))
        assert (
            prep.leakage_for("hash::freshyt", "freshhash", r"Z:\scream.wav", "Screaming", f"{yt}_out.wav", blocked)
            == "BLOCKED_YT_GROUP"
        )


def test_folder_labels_are_not_verified_gold():
    recs = prep.finalize_rows(
        [
            {
                "file_path": "dummy.wav",
                "file_id": "dummy",
                "source_key": "hash::abc",
                "original_category": "Screaming",
                "proposed_label": "DISTRESS",
                "category_group": "screaming",
                "content_md5": "abc",
                "leakage_status": "CLEAN",
                "origin": "raw_distress",
                "folder": "Screaming",
                "phrase": "",
                "priority": 5,
                "notes": "test",
            }
        ],
        "GEV1-T",
    )
    assert recs[0]["HUMAN_VERIFIED"] is False
    assert recs[0]["human_verification_status"] == "UNREVIEWED"
    assert recs[0]["proposed_label"] == "DISTRESS"


def test_official_eval_skips_unverified(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "OUT", tmp_path)
    monkeypatch.setattr(prep, "OUT", tmp_path)
    pd.DataFrame(
        [
            {
                "gold_id": "GEV1-D-0001",
                "file_path": "missing.wav",
                "proposed_label": "DISTRESS",
                "HUMAN_VERIFIED": False,
                "source_key": "hash::x",
            }
        ]
    ).to_csv(tmp_path / "gold_candidates.csv", index=False)
    pd.DataFrame(columns=["gold_id", "reviewer_id", "manual_verdict", "review_timestamp", "notes"]).to_csv(
        tmp_path / "gold_reviews.csv", index=False
    )
    result = ev.evaluate()
    assert result["status"] == "NOT_RUN"
    assert result["n_verified"] == 0


def test_uncertain_is_not_verified_gold(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "OUT", tmp_path)
    pd.DataFrame(
        [{"gold_id": "GEV1-D-0001", "file_path": "missing.wav", "proposed_label": "DISTRESS", "source_key": "k"}]
    ).to_csv(tmp_path / "gold_candidates.csv", index=False)
    pd.DataFrame(
        [
            {
                "gold_id": "GEV1-D-0001",
                "reviewer_id": "r",
                "manual_verdict": "UNCERTAIN",
                "review_timestamp": "2026-10-05T00:00:00Z",
                "notes": "",
            }
        ]
    ).to_csv(tmp_path / "gold_reviews.csv", index=False)
    result = ev.evaluate()
    assert result["status"] == "NOT_RUN"
    assert result["n_verified"] == 0


def test_no_augmentation_copies_created_by_prepare_module():
    src = Path(prep.__file__).read_text(encoding="utf-8")
    assert "sf.write" not in src
    assert "TimeStretch" not in src
    assert "PitchShift" not in src
    assert "no_augmentation" in src


def test_production_artifacts_still_isolated():
    assert PROD_TFLITE.is_file()
    assert PROD_TFLITE.stat().st_size == 3_827_768
    if PROD_ANDROID.is_file():
        assert PROD_ANDROID.stat().st_size == 3_827_768
    assert BALANCED_KERAS.is_file()
    if LEGACY_KERAS.is_file():
        assert LEGACY_KERAS.resolve() != BALANCED_KERAS.resolve()


def test_prepared_manifest_has_required_columns_and_no_leakage():
    cand = OUT / "gold_candidates.csv"
    if not cand.is_file():
        return
    df = pd.read_csv(cand)
    required = {
        "gold_id",
        "file_path",
        "source_key",
        "original_category",
        "proposed_label",
        "category_group",
        "content_md5",
        "leakage_status",
        "human_verification_status",
        "HUMAN_VERIFIED",
    }
    assert required.issubset(set(df.columns))
    assert (df["leakage_status"] == "CLEAN").all()
    # Default prepared manifest must not claim verification from folders.
    if "gold_reviews.csv" in {p.name for p in OUT.iterdir()}:
        reviews = pd.read_csv(OUT / "gold_reviews.csv")
        if reviews.empty:
            assert (~df["HUMAN_VERIFIED"].astype(str).str.lower().isin(["true", "1"])).all()
    blocked = prep.load_used_blocks()
    assert set(df["source_key"].astype(str)).isdisjoint(blocked["source_keys"])
    assert set(df["content_md5"].astype(str)).isdisjoint(blocked["hashes"])
    assert df["source_key"].nunique() == len(df)
    assert df["content_md5"].nunique() == len(df)


def test_threshold_metrics_and_recommendation_math():
    y = np.array([1, 1, 1, 0, 0, 0])
    s = np.array([0.9, 0.8, 0.2, 0.7, 0.1, 0.05])
    low = ev.metrics_at(y, s, 0.15)
    high = ev.metrics_at(y, s, 0.75)
    assert low["distress_recall"] == 1.0
    assert low["false_negatives"] == 0
    assert low["false_positives"] == 1
    assert high["false_positives"] == 0
    assert high["false_negatives"] == 1
    rec = ev.recommend([low, high])
    assert rec["production_threshold_changed"] is False
    assert rec["candidates"]


def test_prepared_summary_does_not_fabricate_targets():
    path = OUT / "summary.json"
    if not path.is_file():
        return
    summary = json.loads(path.read_text(encoding="utf-8"))
    assert summary["candidates"]["distress"] <= 500
    assert summary["candidates"]["hard_negative"] <= 1000
    assert summary["no_retrain"] is True
    assert summary["no_augmentation"] is True
    assert summary["folder_labels_are_not_gold"] is True
    assert summary["HUMAN_VERIFIED_default"] is False
