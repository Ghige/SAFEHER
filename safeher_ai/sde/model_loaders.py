"""Load existing Audio / Speech / Movement models without modifying them."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .config import DecisionEngineConfig


@dataclass
class LoadedModels:
    audio_model: Any = None
    speech_model: Any = None
    speech_scaler: Any = None
    movement_model: Any = None
    movement_scaler: Any = None
    paths: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    loaded: dict[str, bool] = field(default_factory=dict)

    @property
    def all_ok(self) -> bool:
        return all(self.loaded.get(k) for k in ("audio_v4_exp02", "speech_v2", "movement_v2"))


def _load_joblib(path: Path):
    import joblib

    return joblib.load(path)


def load_models(cfg: DecisionEngineConfig, log=None) -> LoadedModels:
    """
    Load models from configured paths. Never writes to model directories.
    """
    out = LoadedModels()

    def _log(msg: str):
        if log:
            log(msg)
        else:
            print(msg)

    # Audio v4 Exp02
    try:
        audio_dir = cfg.resolve_model_dir("audio_v4_exp02")
        artifact = audio_dir / cfg.models["audio_v4_exp02"]["artifact"]
        out.paths["audio_v4_exp02"] = str(artifact)
        if not artifact.exists():
            raise FileNotFoundError(artifact)
        import tensorflow as tf  # noqa: F401
        from tensorflow import keras

        out.audio_model = keras.models.load_model(artifact)
        out.loaded["audio_v4_exp02"] = True
        _log(f"Loaded Audio v4 Exp02: {artifact}")
    except Exception as e:
        out.loaded["audio_v4_exp02"] = False
        out.errors.append(f"audio_v4_exp02: {e}")
        _log(f"FAILED to load Audio v4 Exp02: {e}")

    # Speech v2
    try:
        speech_dir = cfg.resolve_model_dir("speech_v2")
        model_path = speech_dir / cfg.models["speech_v2"]["artifact"]
        scaler_path = speech_dir / cfg.models["speech_v2"]["scaler"]
        out.paths["speech_v2"] = str(model_path)
        out.paths["speech_v2_scaler"] = str(scaler_path)
        if not model_path.exists():
            raise FileNotFoundError(model_path)
        out.speech_model = _load_joblib(model_path)
        out.speech_scaler = _load_joblib(scaler_path) if scaler_path.exists() else None
        out.loaded["speech_v2"] = True
        _log(f"Loaded Speech v2: {model_path}")
    except Exception as e:
        out.loaded["speech_v2"] = False
        out.errors.append(f"speech_v2: {e}")
        _log(f"FAILED to load Speech v2: {e}")

    # Movement v2 (current movement model)
    try:
        move_dir = cfg.resolve_model_dir("movement_v2")
        model_path = move_dir / cfg.models["movement_v2"]["artifact"]
        scaler_path = move_dir / cfg.models["movement_v2"]["scaler"]
        out.paths["movement_v2"] = str(model_path)
        out.paths["movement_v2_scaler"] = str(scaler_path)
        if not model_path.exists():
            raise FileNotFoundError(model_path)
        out.movement_model = _load_joblib(model_path)
        out.movement_scaler = _load_joblib(scaler_path) if scaler_path.exists() else None
        out.loaded["movement_v2"] = True
        _log(f"Loaded Movement v2: {model_path}")
    except Exception as e:
        out.loaded["movement_v2"] = False
        out.errors.append(f"movement_v2: {e}")
        _log(f"FAILED to load Movement v2: {e}")

    return out
