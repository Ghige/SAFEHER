"""
Eval harness for multi-signal decision cases (false-positive + low-volume).

Does NOT claim real-world accuracy — uses synthetic scores / phrase text only.
Run from repo:
  cd safeher_backend && pytest tests/test_safety_decision_engine.py -q
  python -m training.eval_multisignal_cases   # from safeher_ai with PYTHONPATH
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow importing backend engine when run from safeher_ai
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "safeher_backend"))

from app.ai.safety_decision_engine import (  # noqa: E402
    AudioModelResult,
    SpeechModelResult,
    MovementModelResult,
    decide,
)
from app.ai.speech_phrase_detector import detect_emergency_phrase  # noqa: E402


FALSE_POSITIVE_CASES = [
    ("laughing", 0.2, 0.0, 0.1, 0.6),
    ("singing", 0.15, 0.0, 0.05, 0.7),
    ("angry_conversation", 0.25, 0.1, 0.1, 0.8),
    ("running", 0.1, 0.0, 0.9, 0.4),
    ("transit_noise", 0.2, 0.0, 0.3, 0.85),
    ("loud_normal_speech", 0.18, 0.0, 0.05, 0.95),
]

LOW_VOLUME_PHRASES = [
    "help me",
    "please help",
    "bachao",
    "mujhe bachao",
    "madat kara",
    "mala vachva",
]


def main():
    print("=== False-positive style checks (synthetic) ===")
    fails = 0
    for name, distress, phrase, move, volume in FALSE_POSITIVE_CASES:
        d = decide(
            AudioModelResult(distress, distress, volume),
            SpeechModelResult(phrase >= 0.55, phrase),
            MovementModelResult(move),
        )
        ok = not d.should_trigger_sos
        print(f"  [{('OK' if ok else 'FAIL')}] {name}: action={d.action} risk={d.risk_score}")
        if not ok:
            fails += 1

    print("\n=== Low-volume emergency phrase checks ===")
    for phrase in LOW_VOLUME_PHRASES:
        hit = detect_emergency_phrase(phrase)
        d = decide(
            AudioModelResult(distress_score=0.2, volume_score=0.08),
            SpeechModelResult(hit.phrase_detected, hit.phrase_score, hit.language, hit.phrase),
            MovementModelResult(0.0),
        )
        ok = d.risk_level.value in ("MEDIUM", "HIGH")
        print(f"  [{('OK' if ok else 'FAIL')}] '{phrase}' -> {d.action} ({d.risk_level})")
        if not ok:
            fails += 1

    print("\nNOTE: Synthetic only. Retrain/evaluate with real recordings before product claims.")
    if fails:
        print(f"Failed checks: {fails}")
        sys.exit(1)
    print("All synthetic checks passed.")


if __name__ == "__main__":
    main()
