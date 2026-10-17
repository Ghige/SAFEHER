"""
Metadata helpers for SafeHer multi-signal audio datasets.

Preserves detailed labels (source, language, phrase, emotion, signal_type)
while still allowing binary NORMAL/DISTRESS training targets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional


EMOTIONAL_SOURCES = {"ravdess", "RAVDESS"}
ACOUSTIC_MARKERS = {"screaming", "scream", "distress_scream"}


def infer_metadata(wav_path: Path, raw_root: Optional[Path] = None) -> Dict[str, str]:
    """
    Infer rich metadata from path without destroying folder layout.

    Examples:
      data/raw/distress/Screaming/x.wav
        → signal_type=acoustic_distress, class=DISTRESS, emotion=
      data/speech/emergency_phrases/english/help_me/x.wav
        → signal_type=emergency_phrase, language=english, phrase=help_me, class=DISTRESS
      data/speech/normal/hindi/x.wav
        → signal_type=normal_speech, language=hindi, class=NORMAL
      data/raw/emotional/ravdess/fearful/x.wav
        → signal_type=emotional_speech, source=ravdess, emotion=fearful, class=SUPPORT
          (NOT auto-mapped to emergency)
    """
    parts = [p.lower() for p in wav_path.parts]
    name = wav_path.stem

    meta = {
        "file_path": str(wav_path),
        "source": "unknown",
        "language": "",
        "phrase": "",
        "emotion": "",
        "activity": "",
        "class": "UNKNOWN",
        "signal_type": "unknown",
        "participant_id": "spk000",
        "session_id": "",
    }

    # Speaker from naming convention
    for token in name.split("_"):
        if token.startswith("spk"):
            meta["participant_id"] = token
            break

    # RAVDESS / emotional speech — supporting only
    if "ravdess" in parts or "emotional" in parts or "emotional_speech" in parts:
        meta["source"] = "ravdess" if "ravdess" in parts else "emotional_speech"
        meta["signal_type"] = "emotional_speech"
        meta["class"] = "SUPPORT"  # do NOT auto-label as DISTRESS
        for emo in ("fearful", "angry", "sad", "happy", "calm", "neutral", "surprised", "disgust"):
            if emo in parts:
                meta["emotion"] = emo
                break
        return meta

    # Emergency phrases layout
    if "emergency_phrases" in parts or "speech" in parts:
        meta["signal_type"] = "emergency_phrase" if "emergency_phrases" in parts or "emergency" in parts else "speech"
        for lang in ("english", "hindi", "marathi"):
            if lang in parts:
                meta["language"] = lang
                break
        # phrase folder name is usually the parent of the file
        parent = wav_path.parent.name.lower().replace(" ", "_")
        if parent not in ("english", "hindi", "marathi", "normal", "emergency_phrases", "speech"):
            meta["phrase"] = parent
        if "normal" in parts:
            meta["class"] = "NORMAL"
            meta["signal_type"] = "normal_speech"
        else:
            meta["class"] = "DISTRESS"
            meta["signal_type"] = "emergency_phrase"
        return meta

    # Acoustic distress (Screaming etc.)
    if "distress" in parts:
        meta["class"] = "DISTRESS"
        if any(m in parts for m in ACOUSTIC_MARKERS) or "screaming" in parts:
            meta["signal_type"] = "acoustic_distress"
            meta["phrase"] = "scream"
        else:
            # phrase subfolders still under distress/
            meta["signal_type"] = "emergency_phrase"
            meta["phrase"] = wav_path.parent.name.lower().replace(" ", "_")
        return meta

    if "normal" in parts:
        meta["class"] = "NORMAL"
        meta["signal_type"] = "environmental_or_normal"
        return meta

    if "noise" in parts:
        meta["class"] = "NOISE"
        meta["signal_type"] = "noise"
        return meta

    return meta


def binary_train_label(meta: Dict[str, str]) -> Optional[int]:
    """
    Map rich metadata → binary training target.
    SUPPORT (RAVDESS) returns None — exclude from binary distress head by default.
    """
    cls = meta.get("class", "")
    if cls == "DISTRESS":
        return 1
    if cls == "NORMAL":
        return 0
    return None
