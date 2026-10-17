"""Load / validate Safety Decision Engine configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SDE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = SDE_DIR / "decision_engine_config.json"
SAFEHER_AI_ROOT = SDE_DIR.parent


@dataclass
class DecisionEngineConfig:
    raw: dict[str, Any]
    path: Path

    @property
    def demo_mode(self) -> bool:
        return bool(self.raw.get("DEMO_MODE", True))

    @property
    def thresholds(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for k, v in self.raw.get("thresholds", {}).items():
            if k == "note" or isinstance(v, str):
                continue
            out[k] = float(v)
        return out

    @property
    def rules(self) -> dict[str, Any]:
        return dict(self.raw.get("rules", {}))

    @property
    def emergency_phrases(self) -> list[str]:
        return [str(p).strip().lower() for p in self.raw.get("emergency_phrases", [])]

    @property
    def confirmation(self) -> dict[str, Any]:
        return dict(self.raw.get("confirmation", {}))

    @property
    def safety(self) -> dict[str, Any]:
        return dict(self.raw.get("safety", {}))

    @property
    def models(self) -> dict[str, Any]:
        return dict(self.raw.get("models", {}))

    def resolve_model_dir(self, key: str) -> Path:
        rel = self.models[key]["dir"]
        p = Path(rel)
        if not p.is_absolute():
            p = (SAFEHER_AI_ROOT / p).resolve()
        return p

    def assert_demo_safe(self) -> None:
        if not self.demo_mode:
            raise RuntimeError(
                "DEMO_MODE is false. Refusing to run: this package is TEST/DEMO only."
            )
        safety = self.safety
        if safety.get("allow_real_sos") or safety.get("allow_phone_calls"):
            raise RuntimeError("Real SOS/calls enabled in config — blocked for safety.")
        if safety.get("allow_sms") or safety.get("allow_whatsapp"):
            raise RuntimeError("SMS/WhatsApp enabled in config — blocked for safety.")
        if safety.get("allow_emergency_contact_notifications"):
            raise RuntimeError("Emergency contact notifications enabled — blocked.")


def load_config(path: Path | None = None) -> DecisionEngineConfig:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg = DecisionEngineConfig(raw=raw, path=cfg_path)
    cfg.assert_demo_safe()
    return cfg
