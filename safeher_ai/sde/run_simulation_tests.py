"""
SafeHer Safety Decision Engine — simulation test harness (DEMO ONLY).

Loads Audio v4 Exp02, Speech v2, Movement v2 (read-only).
Runs 16 scripted multi-signal scenarios with injected scores
(representative of each case). Does NOT send real SOS.

Run:
  ..\\venv311\\Scripts\\python.exe -m sde.run_simulation_tests
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sde.config import load_config
from sde.confirmation import UserChoice
from sde.engine import EngineInput, SafetyDecisionEngine
from sde.model_loaders import load_models

LOG_DIR = ROOT / "data" / "training_logs"
LOG_PATH = LOG_DIR / "decision_engine_test.log"
SUMMARY_PATH = LOG_DIR / "decision_engine_test_summary.md"


class Logger:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.fh = open(path, "w", encoding="utf-8")

    def log(self, msg: str = ""):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", errors="replace").decode("ascii"))
        self.fh.write(line + "\n")
        self.fh.flush()

    def close(self):
        self.fh.close()


# Scenario definitions: injected model scores + phrase + simulated user response
# Scores are 0–1 and chosen to exercise the configurable rule engine.
SCENARIOS: list[dict] = [
    {
        "id": 1,
        "name": "Normal conversation",
        "audio_score": 0.12,
        "speech_emergency_score": 0.08,
        "movement_score": 0.10,
        "detected_phrase": None,
        "confidence": 0.20,
        "user_choice": None,
        "expected_decision": "NORMAL",
    },
    {
        "id": 2,
        "name": 'Quiet "help me"',
        "audio_score": 0.15,
        "speech_emergency_score": 0.88,
        "movement_score": 0.12,
        "detected_phrase": "help me",
        "confidence": 0.92,
        "user_choice": "NO_RESPONSE",
        "expected_decision": "SUSPICIOUS",
    },
    {
        "id": 3,
        "name": 'Loud "help me"',
        "audio_score": 0.55,
        "speech_emergency_score": 0.94,
        "movement_score": 0.18,
        "detected_phrase": "help me",
        "confidence": 0.96,
        "user_choice": "NO_RESPONSE",
        "expected_decision": "EMERGENCY",
    },
    {
        "id": 4,
        "name": '"mujhe bachao"',
        "audio_score": 0.18,
        "speech_emergency_score": 0.90,
        "movement_score": 0.14,
        "detected_phrase": "mujhe bachao",
        "confidence": 0.93,
        "user_choice": "NO_RESPONSE",
        "expected_decision": "SUSPICIOUS",
    },
    {
        "id": 5,
        "name": '"madat karo"',
        "audio_score": 0.16,
        "speech_emergency_score": 0.91,
        "movement_score": 0.11,
        "detected_phrase": "madat karo",
        "confidence": 0.94,
        "user_choice": "CANCEL",
        "expected_decision": "SUSPICIOUS",
    },
    {
        "id": 6,
        "name": "Screaming only",
        "audio_score": 0.86,
        "speech_emergency_score": 0.05,
        "movement_score": 0.20,
        "detected_phrase": None,
        "confidence": 0.10,
        "user_choice": "NO_RESPONSE",
        "expected_decision": "EMERGENCY",
    },
    {
        "id": 7,
        "name": "Abnormal movement only",
        "audio_score": 0.10,
        "speech_emergency_score": 0.04,
        "movement_score": 0.88,
        "detected_phrase": None,
        "confidence": 0.10,
        "user_choice": None,
        "expected_decision": "NORMAL",
    },
    {
        "id": 8,
        "name": "Screaming + abnormal movement",
        "audio_score": 0.84,
        "speech_emergency_score": 0.06,
        "movement_score": 0.82,
        "detected_phrase": None,
        "confidence": 0.15,
        "user_choice": "NO_RESPONSE",
        "expected_decision": "EMERGENCY",
    },
    {
        "id": 9,
        "name": "Emergency speech + normal movement",
        "audio_score": 0.20,
        "speech_emergency_score": 0.89,
        "movement_score": 0.15,
        "detected_phrase": "i need help",
        "confidence": 0.90,
        "user_choice": "NO_RESPONSE",
        "expected_decision": "SUSPICIOUS",
    },
    {
        "id": 10,
        "name": "Emergency speech + abnormal movement",
        "audio_score": 0.22,
        "speech_emergency_score": 0.90,
        "movement_score": 0.85,
        "detected_phrase": "help me",
        "confidence": 0.91,
        "user_choice": "NO_RESPONSE",
        "expected_decision": "EMERGENCY",
    },
    {
        "id": 11,
        "name": "Baby crying",
        "audio_score": 0.35,
        "speech_emergency_score": 0.05,
        "movement_score": 0.12,
        "detected_phrase": None,
        "confidence": 0.10,
        "user_choice": None,
        "expected_decision": "NORMAL",
    },
    {
        "id": 12,
        "name": "Firecracker",
        "audio_score": 0.42,
        "speech_emergency_score": 0.03,
        "movement_score": 0.25,
        "detected_phrase": None,
        "confidence": 0.08,
        "user_choice": None,
        "expected_decision": "NORMAL",
    },
    {
        "id": 13,
        "name": "Traffic noise",
        "audio_score": 0.28,
        "speech_emergency_score": 0.02,
        "movement_score": 0.30,
        "detected_phrase": None,
        "confidence": 0.05,
        "user_choice": None,
        "expected_decision": "NORMAL",
    },
    {
        "id": 14,
        "name": "Laughing",
        "audio_score": 0.32,
        "speech_emergency_score": 0.04,
        "movement_score": 0.18,
        "detected_phrase": None,
        "confidence": 0.10,
        "user_choice": None,
        "expected_decision": "NORMAL",
    },
    {
        "id": 15,
        "name": "Normal walking",
        "audio_score": 0.08,
        "speech_emergency_score": 0.02,
        "movement_score": 0.35,
        "detected_phrase": None,
        "confidence": 0.05,
        "user_choice": None,
        "expected_decision": "NORMAL",
    },
    {
        "id": 16,
        "name": "Normal phone handling",
        "audio_score": 0.10,
        "speech_emergency_score": 0.03,
        "movement_score": 0.40,
        "detected_phrase": None,
        "confidence": 0.05,
        "user_choice": None,
        "expected_decision": "NORMAL",
    },
]


def main() -> int:
    started = datetime.now(timezone.utc)
    log = Logger(LOG_PATH)
    results: list[dict] = []
    errors: list[str] = []
    files_created = [
        "safeher_ai/sde/__init__.py",
        "safeher_ai/sde/config.py",
        "safeher_ai/sde/decision_engine_config.json",
        "safeher_ai/sde/engine.py",
        "safeher_ai/sde/model_loaders.py",
        "safeher_ai/sde/confirmation.py",
        "safeher_ai/sde/run_simulation_tests.py",
        "safeher_ai/data/training_logs/decision_engine_test.log",
        "safeher_ai/data/training_logs/decision_engine_test_summary.md",
    ]
    files_modified: list[str] = []

    try:
        log.log("=" * 72)
        log.log("SafeHer Safety Decision Engine — TEST/DEMO simulation")
        log.log("DEMO_MODE=true | NO real SOS / calls / SMS / WhatsApp / contacts")
        log.log("=" * 72)
        log.log(f"Start (UTC): {started.isoformat()}")

        cfg = load_config()
        log.log(f"Config: {cfg.path}")
        log.log(f"DEMO_MODE={cfg.demo_mode}")
        log.log(f"Thresholds: {json.dumps(cfg.thresholds)}")
        log.log(f"Rules: {json.dumps(cfg.rules)}")
        log.log(f"Countdown seconds: {cfg.confirmation.get('countdown_seconds')}")

        log.log("Loading models (read-only)...")
        models = load_models(cfg, log=log.log)
        log.log(f"Models loaded flags: {models.loaded}")
        log.log(f"Model paths: {json.dumps(models.paths, indent=2)}")
        if models.errors:
            for e in models.errors:
                log.log(f"MODEL LOAD ERROR: {e}")
                errors.append(e)

        engine = SafetyDecisionEngine(cfg)
        match_count = 0

        for sc in SCENARIOS:
            log.log("-" * 72)
            log.log(f"SCENARIO {sc['id']}: {sc['name']}")
            inp = EngineInput(
                audio_score=sc["audio_score"],
                speech_emergency_score=sc["speech_emergency_score"],
                movement_score=sc["movement_score"],
                detected_phrase=sc["detected_phrase"],
                confidence=sc["confidence"],
                timestamp=datetime.now(timezone.utc).isoformat(),
                scenario_id=str(sc["id"]),
                notes=sc["name"],
            )
            choice: UserChoice | None = sc.get("user_choice")
            if sc["expected_decision"] in ("EMERGENCY", "SUSPICIOUS"):
                out = engine.decide_with_confirmation(inp, user_choice=choice or "NO_RESPONSE")
            else:
                out = engine.decide_with_confirmation(inp, user_choice=None)

            ok = out.decision == sc["expected_decision"]
            if ok:
                match_count += 1
            else:
                errors.append(
                    f"Scenario {sc['id']} expected {sc['expected_decision']} got {out.decision}"
                )

            rec = {
                "timestamp": out.timestamp,
                "scenario_id": sc["id"],
                "scenario_name": sc["name"],
                "audio_score": out.audio_score,
                "speech_score": out.speech_score,
                "movement_score": out.movement_score,
                "detected_phrase": out.detected_phrase,
                "confidence_input": sc["confidence"],
                "individual_model_decisions": out.individual_model_decisions,
                "combined_decision": out.decision,
                "expected_decision": sc["expected_decision"],
                "expectation_met": ok,
                "trigger_reason": out.trigger_reason or out.reason,
                "reason": out.reason,
                "active_signals": out.active_signals,
                "countdown_result": out.countdown_result,
                "simulated_action": out.simulated_action,
                "confirmation": out.confirmation,
                "demo_mode": out.demo_mode,
                "real_sos": False,
            }
            results.append(rec)

            log.log(f"  Audio score:     {out.audio_score:.4f} -> {out.individual_model_decisions['audio']}")
            log.log(f"  Speech score:    {out.speech_score:.4f} -> {out.individual_model_decisions['speech']}")
            log.log(f"  Movement score:  {out.movement_score:.4f} -> {out.individual_model_decisions['movement']}")
            log.log(f"  Detected phrase: {out.detected_phrase}")
            log.log(f"  Decision:        {out.decision} (expected {sc['expected_decision']}) {'OK' if ok else 'MISMATCH'}")
            log.log(f"  Reason:          {out.reason}")
            log.log(f"  Countdown:       {out.countdown_result}")
            log.log(f"  Simulated action:{out.simulated_action}")
            log.log(f"  Real SOS:        False (DEMO)")

        # Write JSON companion for machines
        json_path = LOG_DIR / "decision_engine_test_results.json"
        json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        files_created.append("safeher_ai/data/training_logs/decision_engine_test_results.json")
        log.log(f"Wrote {json_path}")

        # Markdown summary
        md = _build_summary(
            started=started,
            models=models,
            results=results,
            errors=errors,
            files_created=files_created,
            files_modified=files_modified,
            match_count=match_count,
            cfg=cfg,
        )
        SUMMARY_PATH.write_text(md, encoding="utf-8")
        log.log(f"Wrote {SUMMARY_PATH}")
        log.log(f"Scenarios matching expectations: {match_count}/{len(SCENARIOS)}")
        log.log("STATUS=SUCCESS" if not models.errors else "STATUS=SUCCESS_WITH_MODEL_WARNINGS")
        log.log("NO REAL SOS. Simulation complete. Stopping.")
        return 0 if not errors else 1
    except Exception as e:
        log.log(f"FATAL: {e}")
        log.log(traceback.format_exc())
        SUMMARY_PATH.write_text(
            f"# Decision Engine Test Summary\n\n**FAILED**\n\n```\n{e}\n```\n",
            encoding="utf-8",
        )
        return 2
    finally:
        log.close()


def _build_summary(*, started, models, results, errors, files_created, files_modified, match_count, cfg) -> str:
    lines = [
        "# Safety Decision Engine — Test / Demo Summary",
        "",
        f"**Started (UTC):** {started.isoformat()}  ",
        f"**Finished (UTC):** {datetime.now(timezone.utc).isoformat()}  ",
        f"**DEMO_MODE:** `{cfg.demo_mode}`  ",
        "**Real SOS / calls / SMS / WhatsApp / contacts:** DISABLED",
        "",
        "## Models loaded (read-only)",
        "",
        "| Model | Loaded | Path |",
        "|-------|:------:|------|",
    ]
    for key in ("audio_v4_exp02", "speech_v2", "movement_v2"):
        path = models.paths.get(key, models.paths.get(key, "—"))
        if key == "speech_v2":
            path = models.paths.get("speech_v2", "—")
        elif key == "movement_v2":
            path = models.paths.get("movement_v2", "—")
        lines.append(f"| {key} | {models.loaded.get(key)} | `{path}` |")

    lines += [
        "",
        "## Files created",
        "",
    ]
    for f in files_created:
        lines.append(f"- `{f}`")
    lines += ["", "## Files modified", ""]
    if files_modified:
        for f in files_modified:
            lines.append(f"- `{f}`")
    else:
        lines.append("- *(none — existing models/datasets untouched)*")

    lines += [
        "",
        "## All 16 test scenarios",
        "",
        "| # | Scenario | Audio | Speech | Move | Phrase | Decision | Reason | Simulated action |",
        "|---|----------|------:|-------:|-----:|--------|----------|--------|------------------|",
    ]
    for r in results:
        phrase = r["detected_phrase"] or "—"
        reason = (r["reason"] or "").replace("|", "/")
        lines.append(
            f"| {r['scenario_id']} | {r['scenario_name']} | {r['audio_score']:.2f} | "
            f"{r['speech_score']:.2f} | {r['movement_score']:.2f} | {phrase} | "
            f"**{r['combined_decision']}** | {reason} | {r['simulated_action']} |"
        )

    lines += [
        "",
        "## Expectation check",
        "",
        f"Matched expected decisions: **{match_count}/{len(results)}**",
        "",
        "## Errors / mismatches",
        "",
    ]
    if errors:
        for e in errors:
            lines.append(f"- {e}")
    else:
        lines.append("- None")

    lines += [
        "",
        "## Limitations",
        "",
        "- Scenario scores are **injected simulations** representing each case; they do not claim live mic/IMU accuracy.",
        "- Models are loaded to verify artifacts; this harness does not retrain or overwrite them.",
        "- Speech v2 is binary; `detected_phrase` comes from the scenario / phrase catalog match layer.",
        "- Movement v2 was trained on synthetic-heavy data — treat movement scores as prototype-only.",
        "- `TEST_SOS_TRIGGERED` is log-only. No phones, SMS, WhatsApp, or contacts are contacted.",
        "- Not wired into Android / backend SOS production path.",
        "",
        "## Safety",
        "",
        "`DEMO_MODE = true` in `safeher_ai/sde/decision_engine_config.json`.",
        "Engine refuses real SOS actions while DEMO_MODE is true.",
        "",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
