"""Retraining gate must never train and must reject forbidden gold labels."""

import csv
import json
import sys
from pathlib import Path

import retraining_gate
from gold_policy import assign_split, leakage_pairs


def test_gate_forbids_training_on_empty_gold(tmp_path, monkeypatch):
    monkeypatch.setattr(retraining_gate, "STAGE6_GOLD", tmp_path / "s6")
    monkeypatch.setattr(retraining_gate, "REALWORLD_GOLD", tmp_path / "rw")
    monkeypatch.setattr(retraining_gate, "OUT", tmp_path / "out.json")
    report = retraining_gate.evaluate()
    assert report["automatic_retrain"] is False
    assert report["training_forbidden_this_run"] is True
    assert report["approved_to_train"] is False
    assert report["ready_to_consider_training"] is False
    assert report["counts"]["total_DISTRESS"] == 0


def test_forbidden_labels_fail_gate(tmp_path, monkeypatch):
    s6 = tmp_path / "s6"
    s6.mkdir()
    with (s6 / "confirmed_distress.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["event_id", "manual_verdict", "license_status", "split"])
        w.writeheader()
        w.writerow({
            "event_id": "e1",
            "manual_verdict": "UNREVIEWED",
            "license_status": "SAFE",
            "split": "train",
        })
    monkeypatch.setattr(retraining_gate, "STAGE6_GOLD", s6)
    monkeypatch.setattr(retraining_gate, "REALWORLD_GOLD", tmp_path / "rw")
    monkeypatch.setattr(retraining_gate, "OUT", tmp_path / "out.json")
    report = retraining_gate.evaluate()
    assert report["gates"]["no_forbidden_labels"] is False
    assert report["ready_to_consider_training"] is False


def test_leakage_detection():
    rows = [
        {"event_id": "same", "split": "train"},
        {"event_id": "same", "split": "test"},
    ]
    leaks = leakage_pairs(rows)
    assert leaks
    assert assign_split("abc") in {"train", "val", "test"}


def test_gate_cli_does_not_train(tmp_path, monkeypatch):
    monkeypatch.setattr(retraining_gate, "STAGE6_GOLD", tmp_path / "s6")
    monkeypatch.setattr(retraining_gate, "REALWORLD_GOLD", tmp_path / "rw")
    monkeypatch.setattr(retraining_gate, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(sys, "argv", ["retraining_gate.py"])
    code = retraining_gate.main()
    assert code == 2
    data = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert data["automatic_retrain"] is False
    assert data["gates"]["training_executed"] is False
