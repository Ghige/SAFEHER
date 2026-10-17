"""
Stage 3 finish — golden vectors: Python unified + backend must agree.
Also verifies decision_contract copies and confirm_30s == 30s.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
BACKEND = REPO / "safeher_backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sde.unified_engine import UnifiedSignals, decide_unified, load_contract

GOLDEN = Path(__file__).resolve().parent / "golden_vectors.json"
CANONICAL_CONTRACT = Path(__file__).resolve().parent / "decision_contract.json"
BACKEND_CONTRACT = BACKEND / "app" / "ai" / "decision_contract.json"
ANDROID_ASSET_CONTRACT = (
    REPO / "safeher_android" / "app" / "src" / "main" / "assets" / "decision_contract.json"
)
ANDROID_TEST_GOLDEN = (
    REPO / "safeher_android" / "app" / "src" / "test" / "resources" / "golden_vectors.json"
)


def _load_golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_contract_confirm_30s_matches_countdown():
    c = load_contract()
    conf = c["confirmation"]
    assert conf["api_action_name"] == "confirm_30s"
    assert int(conf["countdown_seconds"]) == 30
    assert c["DEMO_MODE"] is True
    assert c["AI_AUTO_SOS_ENABLED"] is False


def test_contract_copies_match_canonical():
    canonical = CANONICAL_CONTRACT.read_text(encoding="utf-8")
    assert BACKEND_CONTRACT.read_text(encoding="utf-8") == canonical
    assert ANDROID_ASSET_CONTRACT.read_text(encoding="utf-8") == canonical
    assert ANDROID_TEST_GOLDEN.read_text(encoding="utf-8") == GOLDEN.read_text(encoding="utf-8")


def test_backend_loads_shared_contract():
    from app.ai.safety_decision_engine import get_default_config, load_decision_contract

    loaded = load_decision_contract()
    cfg = get_default_config()
    assert loaded["contract_version"] == "1.0.0"
    assert cfg.confirm_action_name == "confirm_30s"
    assert cfg.confirm_countdown_seconds == 30
    assert cfg.risk_high == pytest.approx(0.65)
    assert cfg.distress_floor_high == pytest.approx(0.80)


def test_golden_vectors_python_and_backend_agree():
    from app.ai.safety_decision_engine import (
        AudioModelResult,
        MovementModelResult,
        SpeechModelResult,
        decide,
    )

    data = _load_golden()
    assert data["contract_version"] == load_contract()["contract_version"]

    for vec in data["vectors"]:
        uni = decide_unified(
            UnifiedSignals(
                audio_distress=vec["audio"],
                speech_emergency=vec["speech"],
                movement_anomaly=vec["movement"],
                volume=vec.get("volume", 0.0),
                fall_detected=bool(vec.get("fall", False)),
                is_night=False,
            ),
            demo_mode=True,
            ai_auto_sos_enabled=False,
        )
        back = decide(
            audio=AudioModelResult(
                distress_score=vec["audio"],
                volume_score=vec.get("volume", 0.0),
            ),
            speech=SpeechModelResult(
                phrase_score=vec["speech"],
                phrase_detected=vec["speech"] >= 0.55,
            ),
            movement=MovementModelResult(
                movement_anomaly_score=vec["movement"],
                fall_detected=bool(vec.get("fall", False)),
            ),
            is_night=False,
        )
        assert uni.action == vec["expected_action"], f"{vec['id']}: unified action"
        assert uni.state == vec["expected_state"], f"{vec['id']}: unified state"
        assert back.action == vec["expected_action"], f"{vec['id']}: backend action"
        assert uni.action == back.action, f"{vec['id']}: unified vs backend action"
        assert round(uni.risk_score, 3) == round(back.risk_score, 3), f"{vec['id']}: risk_score"
