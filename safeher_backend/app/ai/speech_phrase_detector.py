"""
SafeHer — Emergency phrase / speech detection (text layer).

This component scores emergency-related phrases from a transcript or
ASR hypothesis. It is deliberately catalog-driven so languages/phrases
can be extended without code changes to the Safety Decision Engine.

On-device ASR is optional; when no transcript is available, phrase_score=0
and the distress model + SDE still operate.

Do NOT treat this catalog as the only permanent phrase set.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# Extensible catalog: language -> list of normalized phrase variants
# TEMPORARY seed set — add more via PHRASE_CATALOG / load_phrase_catalog().
DEFAULT_PHRASE_CATALOG: Dict[str, List[str]] = {
    "english": [
        "help me",
        "save me",
        "please help",
        "i need help",
        "need help",
        "call police",
        "call the police",
        "send help",
    ],
    "hindi": [
        "bachao",
        "mujhe bachao",
        "madad karo",
        "madad",
        "police bulao",
    ],
    "marathi": [
        "madat kara",
        "madat karo",
        "mala vachva",
        "vachva",
        "madat",
    ],
}


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).lower().strip()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class PhraseHit:
    phrase: str
    language: str
    score: float


@dataclass
class PhraseDetectionResult:
    phrase_detected: bool
    phrase_score: float
    language: Optional[str] = None
    phrase: Optional[str] = None
    hits: Optional[List[PhraseHit]] = None


def load_phrase_catalog(extra: Optional[Dict[str, List[str]]] = None) -> Dict[str, List[str]]:
    catalog = {lang: list(phrases) for lang, phrases in DEFAULT_PHRASE_CATALOG.items()}
    if extra:
        for lang, phrases in extra.items():
            catalog.setdefault(lang.lower(), [])
            for p in phrases:
                n = normalize_text(p)
                if n and n not in catalog[lang.lower()]:
                    catalog[lang.lower()].append(n)
    return catalog


def detect_emergency_phrase(
    transcript: Optional[str],
    catalog: Optional[Dict[str, List[str]]] = None,
) -> PhraseDetectionResult:
    """
    Match transcript against emergency phrase catalog.

    Scoring:
      exact / contains full phrase → 1.0 (best match)
      partial token overlap → up to 0.7
      no match → 0.0
    """
    catalog = catalog or load_phrase_catalog()
    norm = normalize_text(transcript or "")
    if not norm:
        return PhraseDetectionResult(False, 0.0)

    best: Optional[PhraseHit] = None
    hits: List[PhraseHit] = []

    for language, phrases in catalog.items():
        for phrase in phrases:
            p = normalize_text(phrase)
            if not p:
                continue
            if p in norm or norm in p:
                score = 1.0 if p == norm or p in norm else 0.9
                hit = PhraseHit(phrase=p, language=language, score=score)
                hits.append(hit)
                if best is None or hit.score > best.score:
                    best = hit
                continue

            # Token overlap (order-insensitive soft match)
            p_toks = set(p.split())
            n_toks = set(norm.split())
            if not p_toks:
                continue
            overlap = len(p_toks & n_toks) / len(p_toks)
            if overlap >= 0.67:
                score = 0.55 + 0.35 * overlap
                hit = PhraseHit(phrase=p, language=language, score=round(score, 3))
                hits.append(hit)
                if best is None or hit.score > best.score:
                    best = hit

    if best is None:
        return PhraseDetectionResult(False, 0.0, hits=[])

    return PhraseDetectionResult(
        phrase_detected=best.score >= 0.55,
        phrase_score=round(best.score, 3),
        language=best.language,
        phrase=best.phrase,
        hits=hits,
    )
