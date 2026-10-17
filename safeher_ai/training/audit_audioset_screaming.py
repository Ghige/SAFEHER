"""
Quality + content audit of the derived AudioSet SCREAMING dataset.

Audits ONLY: safeher_ai/data/derived/audioset_screaming/
Does NOT train, does NOT merge, does NOT relabel anything as DISTRESS.
Clips keep source_label = SCREAMING; this audit adds an ADVISORY category only.

The content categorisation is METADATA/HEURISTIC-BASED:
no human listened to the audio and no audio classifier was run.

Outputs:
  metadata/quality_audit.csv
  metadata/manual_review_list.csv
  ../../training_logs/audioset_screaming_quality_audit.md
  ../../training_logs/audioset_screaming_quality_audit.log

Run:
  ..\\venv311\\Scripts\\python.exe training\\audit_audioset_screaming.py
"""

from __future__ import annotations

import csv
import json
import random
import re
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "derived" / "audioset_screaming"
META_DIR = OUT / "metadata"
TRAIN_LOG = DATA / "training_logs"

AUDIT_CSV = META_DIR / "quality_audit.csv"
REVIEW_CSV = META_DIR / "manual_review_list.csv"
AUDIT_MD = TRAIN_LOG / "audioset_screaming_quality_audit.md"
AUDIT_LOG = TRAIN_LOG / "audioset_screaming_quality_audit.log"

SCREAMING_MID = "/m/03qc9zr"
SEED = 1337
REVIEW_PER_CATEGORY = 20

CATEGORIES = [
    "LIKELY_DISTRESS",
    "POSSIBLE_DISTRESS",
    "NON_DISTRESS_SCREAM",
    "MOVIE_OR_MEDIA",
    "MUSIC_RELATED",
    "AMBIGUOUS",
    "LOW_QUALITY",
]

# ---------------------------------------------------------------- thresholds
MIN_DURATION_S = 5.0
SILENCE_FRAME_DBFS = -50.0     # frame considered silent below this
SILENCE_PCT_BAD = 70.0
CLIP_SAMPLE_THRESH = 0.995
CLIP_PCT_BAD = 5.0
NEAR_SILENT_RMS_DBFS = -50.0

# suspicious (flag for review, not necessarily LOW_QUALITY)
SUSPICIOUS_SILENCE_PCT = 40.0
SUSPICIOUS_CLIP_PCT = 1.0
SUSPICIOUS_RMS_DBFS = -40.0

# ---------------------------------------------------------- keyword lexicons
MUSIC_LABELS = {
    "Music", "Singing", "Song", "Musical instrument", "Choir", "Rock music",
    "Heavy metal", "Punk rock", "Rapping", "Hip hop music", "Pop music",
    "Electronic music", "Drum", "Guitar", "Screaming (music)", "Death metal",
    "Grunge", "Progressive rock", "Rock and roll", "Opera", "A capella",
    "Background music", "Theme music", "Soundtrack music", "Jingle (music)",
}
NON_DISTRESS_LABELS = {
    "Laughter", "Giggle", "Chuckle, chortle", "Snicker", "Belly laugh",
    "Baby laughter", "Children playing", "Cheering", "Applause", "Crowd",
    "Whoop", "Clapping", "Chatter", "Hubbub, speech noise, speech babble",
    "Children shouting", "Booing",
}
ANIMAL_LABELS = {
    "Animal", "Dog", "Cat", "Bird", "Monkey", "Pig", "Horse", "Cattle, bovinae",
    "Roaring cats (lions, tigers)", "Bird vocalization, bird call, bird song",
    "Livestock, farm animals, working animals", "Domestic animals, pets",
    "Goat", "Sheep", "Chicken, rooster", "Fowl", "Wild animals", "Rodents, rats, mice",
}
DISTRESS_SUPPORT_LABELS = {
    "Crying, sobbing", "Baby cry, infant cry", "Whimper", "Wail, moan",
    "Shout", "Yell", "Bellow", "Screaming", "Groan", "Gasp",
}
VIOLENCE_LABELS = {
    "Gunshot, gunfire", "Explosion", "Machine gun", "Artillery fire",
    "Siren", "Civil defense siren", "Emergency vehicle", "Police car (siren)",
    "Ambulance (siren)", "Fire engine, fire truck (siren)", "Smash, crash",
    "Glass", "Shatter", "Breaking",
}

MUSIC_KW = [
    "official video", "official music video", "official audio", "lyrics",
    "lyric video", "song", "album", "remix", "band", "concert", "live at",
    "feat", "guitar", "drum cover", "metal", "hardcore", "screamo",
    "vocals", "singing", "karaoke", "instrumental", "soundtrack", "ost",
    "music video", "acoustic", "mixtape", "rapper", "beats",
]
MEDIA_KW = [
    "trailer", "movie", "film", "scene", "full episode", "episode", "season ",
    "anime", "cartoon", "animation", "tv show", "series", "netflix", "teaser",
    "gameplay", "walkthrough", "let's play", "lets play", "playthrough",
    "no commentary", "speedrun", "wwe", "wrestling", "raw ", "smackdown",
    "horror game", "amnesia", "fnaf", "five nights", "outlast", "resident evil",
    "clip from", "movie clip", "best scenes", "compilation", "reaction",
    "montage", "short film", "fan made", "parody", "sketch", "stand up",
    "drama", "web series", "trailer 2", "official teaser", "behind the scenes",
]
NON_DISTRESS_KW = [
    "prank", "pranks", "funny", "hilarious", "fail compilation", "epic fail",
    "roller coaster", "rollercoaster", "theme park", "haunted house",
    "scare cam", "jump scare", "scaring", "kids playing", "playground",
    "birthday", "gender reveal", "crowd cheering", "cheering", "cheers",
    "stadium", "touchdown", "concert crowd", "laughing", "laughter", "joke",
    "comedy", "trolling", "asmr", "scream contest", "screaming contest",
    "screaming goat", "goat scream", "monkey", "animal", "water slide",
    "amusement park", "bungee", "skydiving", "haunted maze", "fun house",
]
STRONG_DISTRESS_KW = [
    "help me", "cries for help", "screams for help", "attacked", "attack on",
    "assault", "assaulted", "robbery", "robbed", "mugging", "mugged",
    "kidnap", "kidnapped", "abduction", "abducted", "molest", "harassment",
    "harassed", "domestic violence", "rape", "stabbed", "stabbing",
    "murder", "shooting victim", "victim screams", "distress call",
    "emergency call", "911 call", "rescue", "trapped", "kidnapping",
    "eve teasing", "chain snatching", "acid attack",
]
MODERATE_DISTRESS_KW = [
    "cctv", "caught on camera", "caught on cctv", "real footage", "shocking",
    "emergency", "panic", "terrified", "terrifying", "screaming for help",
    "police", "fight", "brawl", "accident", "crash", "fire", "disaster",
    "news", "breaking news", "viral video", "incident", "chaos", "evacuation",
    "distress", "victim", "crime", "arrested", "hospital",
]


def log_factory(fh):
    def log(msg: str):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        try:
            print(line, flush=True)
        except UnicodeEncodeError:
            print(line.encode("ascii", "replace").decode("ascii"), flush=True)
        fh.write(line + "\n")
        fh.flush()
    return log


def load_mid_names() -> dict[str, str]:
    names = {}
    p = META_DIR / "class_labels_indices.csv"
    if not p.exists():
        return names
    with open(p, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            names[row["mid"]] = row["display_name"]
    return names


def load_positive_labels() -> dict[tuple[str, float], str]:
    """Map (ytid, start_seconds) -> raw positive label mids from official CSVs."""
    out = {}
    for name in ["balanced_train_segments.csv", "unbalanced_train_segments.csv"]:
        p = META_DIR / name
        if not p.exists():
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if SCREAMING_MID not in line:
                    continue
                try:
                    ytid, start, _end, labels = line.split(", ", 3)
                except ValueError:
                    continue
                out[(ytid.strip(), float(start))] = labels.strip().strip('"')
    return out


def load_youtube_metadata() -> dict[str, dict]:
    out = {}
    p = META_DIR / "youtube_metadata.jsonl"
    if not p.exists():
        return out
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            out[rec.get("ytid", "")] = rec
    return out


def analyse_wav(path: Path) -> dict:
    """Acoustic measurements for one WAV."""
    res = {
        "readable": False, "duration": None, "sample_rate": None, "channels": None,
        "frames": None, "rms": None, "rms_dbfs": None, "peak_amplitude": None,
        "peak_dbfs": None, "loudness_lufs": None, "crest_factor_db": None,
        "clipping_pct": None, "silence_pct": None, "dc_offset": None,
        "spectral_centroid_hz": None, "spectral_flatness": None,
        "zero_crossing_rate": None, "analysis_error": "",
    }
    try:
        info = sf.info(str(path))
        data, sr = sf.read(str(path), always_2d=False, dtype="float64")
    except Exception as e:
        res["analysis_error"] = f"read_error: {e}"
        return res

    if getattr(data, "ndim", 1) > 1:
        data = np.mean(data, axis=1)
    res["readable"] = True
    res["sample_rate"] = int(sr)
    res["channels"] = int(info.channels)
    res["frames"] = int(info.frames)
    n = len(data)
    res["duration"] = float(n / sr) if sr else 0.0
    if n == 0:
        res["analysis_error"] = "empty_file"
        return res

    absx = np.abs(data)
    rms = float(np.sqrt(np.mean(data ** 2)))
    peak = float(absx.max())
    res["rms"] = rms
    res["peak_amplitude"] = peak
    res["rms_dbfs"] = float(20 * np.log10(rms)) if rms > 0 else -120.0
    res["peak_dbfs"] = float(20 * np.log10(peak)) if peak > 0 else -120.0
    res["crest_factor_db"] = float(res["peak_dbfs"] - res["rms_dbfs"])
    res["dc_offset"] = float(np.mean(data))
    res["clipping_pct"] = float(100.0 * np.count_nonzero(absx >= CLIP_SAMPLE_THRESH) / n)

    # frame-wise silence (20 ms frames)
    fl = max(1, int(0.020 * sr))
    nfr = n // fl
    if nfr > 0:
        frames = data[: nfr * fl].reshape(nfr, fl)
        frms = np.sqrt(np.mean(frames ** 2, axis=1))
        with np.errstate(divide="ignore"):
            fdb = 20 * np.log10(np.maximum(frms, 1e-12))
        res["silence_pct"] = float(100.0 * np.count_nonzero(fdb < SILENCE_FRAME_DBFS) / nfr)
    else:
        res["silence_pct"] = 100.0

    # ITU-R BS.1770 loudness where the clip is long enough for a 400 ms block
    try:
        import pyloudnorm as pyln
        if res["duration"] and res["duration"] >= 0.45:
            meter = pyln.Meter(sr)
            lufs = float(meter.integrated_loudness(data))
            if np.isfinite(lufs):
                res["loudness_lufs"] = lufs
    except Exception as e:
        res["analysis_error"] = (res["analysis_error"] + f" lufs_error: {e}").strip()

    try:
        import librosa
        y = data.astype(np.float32)
        res["spectral_centroid_hz"] = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
        res["spectral_flatness"] = float(np.mean(librosa.feature.spectral_flatness(y=y)))
        res["zero_crossing_rate"] = float(np.mean(librosa.feature.zero_crossing_rate(y=y)))
    except Exception as e:
        res["analysis_error"] = (res["analysis_error"] + f" spectral_error: {e}").strip()

    return res


_KW_RE_CACHE: dict[str, "re.Pattern"] = {}


def _kw_regex(kw: str):
    """Word-boundary matcher so 'ride' does not match 'pride'."""
    rx = _KW_RE_CACHE.get(kw)
    if rx is None:
        rx = re.compile(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])")
        _KW_RE_CACHE[kw] = rx
    return rx


def matched(text: str, keywords: list[str]) -> list[str]:
    if not text:
        return []
    return [k for k in keywords if _kw_regex(k).search(text)]


def categorise(acoustic: dict, label_names: list[str], yt: dict | None) -> dict:
    """
    Heuristic, metadata-based advisory category.
    Never asserts the audio was listened to.
    """
    evidence: list[str] = []

    # 1) technical quality first
    if not acoustic.get("readable"):
        return {"category": "LOW_QUALITY", "confidence": "HIGH",
                "evidence": f"unreadable: {acoustic.get('analysis_error')}",
                "metadata_available": bool(yt and yt.get("status") == "OK")}

    dur = acoustic.get("duration") or 0.0
    sil = acoustic.get("silence_pct") or 0.0
    clip = acoustic.get("clipping_pct") or 0.0
    rms_db = acoustic.get("rms_dbfs")
    lowq = []
    if dur < MIN_DURATION_S:
        lowq.append(f"short_duration={dur:.2f}s")
    if sil > SILENCE_PCT_BAD:
        lowq.append(f"silence={sil:.1f}%")
    if clip > CLIP_PCT_BAD:
        lowq.append(f"clipping={clip:.2f}%")
    if rms_db is not None and rms_db < NEAR_SILENT_RMS_DBFS:
        lowq.append(f"near_silent_rms={rms_db:.1f}dBFS")
    if lowq:
        return {"category": "LOW_QUALITY", "confidence": "HIGH",
                "evidence": "; ".join(lowq),
                "metadata_available": bool(yt and yt.get("status") == "OK")}

    labels = set(label_names)
    has_meta = bool(yt and yt.get("status") == "OK" and (yt.get("title") or yt.get("description")))

    # Title/tags/category carry the signal; descriptions are full of channel
    # boilerplate ("subscribe for funny videos"), so they only count as weak.
    title_text = " ".join([
        (yt or {}).get("title", ""),
        " ".join((yt or {}).get("tags") or []),
        " ".join((yt or {}).get("categories") or []),
    ]).lower()
    desc_text = ((yt or {}).get("description", "") or "").lower()
    yt_categories = {c.lower() for c in ((yt or {}).get("categories") or [])}

    music_lab = labels & MUSIC_LABELS
    nond_lab = labels & NON_DISTRESS_LABELS
    animal_lab = labels & ANIMAL_LABELS
    distress_lab = (labels & DISTRESS_SUPPORT_LABELS) - {"Screaming"}
    violence_lab = labels & VIOLENCE_LABELS

    def hits(kws):
        return matched(title_text, kws), matched(desc_text, kws)

    music_t, music_d = hits(MUSIC_KW)
    media_t, media_d = hits(MEDIA_KW)
    nond_t, nond_d = hits(NON_DISTRESS_KW)
    strong_t, strong_d = hits(STRONG_DISTRESS_KW)
    mod_t, mod_d = hits(MODERATE_DISTRESS_KW)

    def ev(tag, t, d):
        if t:
            evidence.append(f"{tag}_title={','.join(t[:5])}")
        elif d:
            evidence.append(f"{tag}_desc={','.join(d[:5])}")

    # 2) music
    if music_lab or "music" in yt_categories or music_t or len(music_d) >= 2:
        if music_lab:
            evidence.append("audioset_labels=" + ",".join(sorted(music_lab)))
        if "music" in yt_categories:
            evidence.append("yt_category=Music")
        ev("music_kw", music_t, music_d)
        return {"category": "MUSIC_RELATED",
                "confidence": "MEDIUM" if (music_lab or "music" in yt_categories) else "LOW",
                "evidence": "; ".join(evidence), "metadata_available": has_meta}

    # 3) movie / media / gaming
    if media_t or (yt_categories & {"film & animation", "gaming"}) or len(media_d) >= 2:
        ev("media_kw", media_t, media_d)
        cross = yt_categories & {"film & animation", "gaming"}
        if cross:
            evidence.append("yt_category=" + ",".join(sorted(cross)))
        return {"category": "MOVIE_OR_MEDIA",
                "confidence": "MEDIUM" if (media_t and cross) else "LOW",
                "evidence": "; ".join(evidence), "metadata_available": has_meta}

    # 4) clearly non-distress screaming (fun, crowds, animals)
    if nond_lab or animal_lab or nond_t or len(nond_d) >= 2:
        if nond_lab:
            evidence.append("audioset_labels=" + ",".join(sorted(nond_lab)))
        if animal_lab:
            evidence.append("animal_labels=" + ",".join(sorted(animal_lab)))
        ev("nondistress_kw", nond_t, nond_d)
        return {"category": "NON_DISTRESS_SCREAM",
                "confidence": "MEDIUM" if (nond_lab or animal_lab) else "LOW",
                "evidence": "; ".join(evidence), "metadata_available": has_meta}

    # 5) distress tiers — explicit textual evidence only, no contradicting cues
    contradicted = bool(music_t or media_t or nond_t)
    if strong_t and not contradicted:
        evidence.append("strong_kw_title=" + ",".join(strong_t[:5]))
        if distress_lab:
            evidence.append("audioset_labels=" + ",".join(sorted(distress_lab)))
        if violence_lab:
            evidence.append("context_labels=" + ",".join(sorted(violence_lab)))
        conf = "MEDIUM" if (len(strong_t) >= 2 or distress_lab or violence_lab) else "LOW"
        return {"category": "LIKELY_DISTRESS", "confidence": conf,
                "evidence": "; ".join(evidence), "metadata_available": has_meta}

    if (strong_d and not contradicted) or len(mod_t) >= 2 or (distress_lab and (mod_t or mod_d)) \
            or (distress_lab and violence_lab):
        if strong_d:
            evidence.append("strong_kw_desc=" + ",".join(strong_d[:5]))
        ev("moderate_kw", mod_t, mod_d)
        if distress_lab:
            evidence.append("audioset_labels=" + ",".join(sorted(distress_lab)))
        if violence_lab:
            evidence.append("context_labels=" + ",".join(sorted(violence_lab)))
        return {"category": "POSSIBLE_DISTRESS", "confidence": "LOW",
                "evidence": "; ".join(evidence), "metadata_available": has_meta}

    # 6) not determinable from metadata
    if not has_meta:
        evidence.append("no_youtube_metadata")
    if labels - {"Screaming"}:
        evidence.append("audioset_labels=" + ",".join(sorted(labels - {"Screaming"}))[:180])
    if mod_t or mod_d:
        evidence.append("weak_kw=" + ",".join((mod_t or mod_d)[:3]))
    return {"category": "AMBIGUOUS", "confidence": "LOW",
            "evidence": "; ".join(evidence) or "insufficient_metadata_signal",
            "metadata_available": has_meta}


def dist_stats(values: list[float]) -> dict:
    vals = [v for v in values if v is not None and np.isfinite(v)]
    if not vals:
        return {"n": 0}
    arr = np.array(vals, dtype=float)
    return {
        "n": len(vals),
        "min": float(arr.min()), "p05": float(np.percentile(arr, 5)),
        "p25": float(np.percentile(arr, 25)), "median": float(np.median(arr)),
        "p75": float(np.percentile(arr, 75)), "p95": float(np.percentile(arr, 95)),
        "max": float(arr.max()), "mean": float(arr.mean()),
    }


def fmt_stats(name: str, s: dict, unit: str = "") -> str:
    if not s.get("n"):
        return f"- {name}: no data"
    return (f"- {name}: min {s['min']:.2f}{unit}, p05 {s['p05']:.2f}{unit}, "
            f"p25 {s['p25']:.2f}{unit}, median {s['median']:.2f}{unit}, "
            f"p75 {s['p75']:.2f}{unit}, p95 {s['p95']:.2f}{unit}, "
            f"max {s['max']:.2f}{unit}, mean {s['mean']:.2f}{unit} (n={s['n']})")


def main():
    TRAIN_LOG.mkdir(parents=True, exist_ok=True)
    fh = open(AUDIT_LOG, "w", encoding="utf-8")
    log = log_factory(fh)
    started = datetime.now()

    try:
        log("=" * 70)
        log("AudioSet SCREAMING — quality + content audit (NO TRAINING, NO MERGE)")
        log(f"Start: {started.isoformat()}")
        log(f"Dataset: {OUT}")
        log("source_label stays SCREAMING; categories below are ADVISORY ONLY.")
        log("Content categories are METADATA/HEURISTIC-BASED — audio was NOT listened to,")
        log("and no audio classifier was used for categorisation.")

        mid_names = load_mid_names()
        pos_labels = load_positive_labels()
        yt_meta = load_youtube_metadata()
        log(f"Loaded class map={len(mid_names)} positive_label rows={len(pos_labels)} "
            f"youtube_metadata records={len(yt_meta)}")
        yt_ok = sum(1 for v in yt_meta.values() if v.get("status") == "OK")
        log(f"YouTube metadata usable: {yt_ok}")

        # source-of-truth rows: successfully downloaded clips
        rows = []
        with open(META_DIR / "screaming_metadata.csv", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("downloaded_status") == "SUCCESS":
                    rows.append(r)
        log(f"Clips marked SUCCESS in metadata: {len(rows)}")

        fields = [
            "clip_id", "ytid", "local_wav_path", "source_split", "audioset_class",
            "audioset_mid", "source_label", "start_seconds", "end_seconds",
            "duration", "sample_rate", "channels", "frames",
            "rms", "rms_dbfs", "peak_amplitude", "peak_dbfs", "loudness_lufs",
            "crest_factor_db", "clipping_pct", "silence_pct", "dc_offset",
            "spectral_centroid_hz", "spectral_flatness", "zero_crossing_rate",
            "file_valid", "suspicious", "suspicious_reasons",
            "audioset_positive_labels", "youtube_title", "youtube_categories",
            "youtube_metadata_status", "content_category", "category_confidence",
            "category_evidence", "category_basis", "analysis_error",
        ]

        audited = []
        invalid = []
        with open(AUDIT_CSV, "w", encoding="utf-8", newline="") as af:
            w = csv.DictWriter(af, fieldnames=fields)
            w.writeheader()

            for i, r in enumerate(rows, 1):
                wav = ROOT / r["local_wav_path"]
                ac = analyse_wav(wav) if wav.exists() else {
                    "readable": False, "analysis_error": "file_missing_on_disk"}

                start = float(r["start_seconds"])
                raw_labels = pos_labels.get((r["ytid"], start), "")
                label_names = [mid_names.get(m.strip(), m.strip())
                               for m in raw_labels.split(",") if m.strip()]
                yt = yt_meta.get(r["ytid"])
                cat = categorise(ac, label_names, yt)

                reasons = []
                if ac.get("readable"):
                    if (ac.get("silence_pct") or 0) > SUSPICIOUS_SILENCE_PCT:
                        reasons.append(f"silence={ac['silence_pct']:.1f}%")
                    if (ac.get("clipping_pct") or 0) > SUSPICIOUS_CLIP_PCT:
                        reasons.append(f"clipping={ac['clipping_pct']:.2f}%")
                    if ac.get("rms_dbfs") is not None and ac["rms_dbfs"] < SUSPICIOUS_RMS_DBFS:
                        reasons.append(f"quiet_rms={ac['rms_dbfs']:.1f}dBFS")
                    if (ac.get("duration") or 0) < 9.5:
                        reasons.append(f"short={ac['duration']:.2f}s")
                else:
                    reasons.append("unreadable")
                    invalid.append((r["clip_id"], ac.get("analysis_error")))

                out = {
                    "clip_id": r["clip_id"], "ytid": r["ytid"],
                    "local_wav_path": r["local_wav_path"],
                    "source_split": r["source_split"],
                    "audioset_class": r["audioset_class"], "audioset_mid": r["audioset_mid"],
                    "source_label": r["source_label"],
                    "start_seconds": r["start_seconds"], "end_seconds": r["end_seconds"],
                    "file_valid": bool(ac.get("readable")),
                    "suspicious": bool(reasons), "suspicious_reasons": "; ".join(reasons),
                    "audioset_positive_labels": "|".join(label_names),
                    "youtube_title": (yt or {}).get("title", ""),
                    "youtube_categories": ",".join((yt or {}).get("categories") or []),
                    "youtube_metadata_status": (yt or {}).get("status", "NOT_FETCHED"),
                    "content_category": cat["category"],
                    "category_confidence": cat["confidence"],
                    "category_evidence": cat["evidence"],
                    "category_basis": "metadata_heuristic_only__not_listened",
                }
                for k in ["duration", "sample_rate", "channels", "frames", "rms", "rms_dbfs",
                          "peak_amplitude", "peak_dbfs", "loudness_lufs", "crest_factor_db",
                          "clipping_pct", "silence_pct", "dc_offset", "spectral_centroid_hz",
                          "spectral_flatness", "zero_crossing_rate", "analysis_error"]:
                    out[k] = ac.get(k, "")
                w.writerow(out)
                audited.append(out)

                if i % 100 == 0:
                    af.flush()
                    log(f"Audited {i}/{len(rows)}")

        log(f"Wrote {AUDIT_CSV} ({len(audited)} rows)")

        # ------------------------------------------------------------ review list
        rnd = random.Random(SEED)
        by_cat: dict[str, list[dict]] = {c: [] for c in CATEGORIES}
        for a in audited:
            by_cat.setdefault(a["content_category"], []).append(a)

        review: dict[str, dict] = {}
        for a in audited:
            if a["suspicious"] or not a["file_valid"] or a["content_category"] == "LOW_QUALITY":
                a2 = dict(a)
                a2["review_reason"] = "suspicious_or_low_quality: " + (a["suspicious_reasons"] or "n/a")
                review[a["clip_id"]] = a2
        for c, items in by_cat.items():
            if not items:
                continue
            k = min(REVIEW_PER_CATEGORY, len(items))
            for a in rnd.sample(items, k):
                if a["clip_id"] in review:
                    continue
                a2 = dict(a)
                a2["review_reason"] = f"random_sample:{c}"
                review[a["clip_id"]] = a2

        review_fields = ["clip_id", "ytid", "local_wav_path", "source_split",
                         "content_category", "category_confidence", "review_reason",
                         "duration", "rms_dbfs", "loudness_lufs", "peak_amplitude",
                         "clipping_pct", "silence_pct", "youtube_title",
                         "audioset_positive_labels", "category_evidence",
                         "manual_verdict", "manual_notes"]
        with open(REVIEW_CSV, "w", encoding="utf-8", newline="") as rf:
            rw = csv.DictWriter(rf, fieldnames=review_fields, extrasaction="ignore")
            rw.writeheader()
            for a in sorted(review.values(), key=lambda x: (x["content_category"], x["clip_id"])):
                a = dict(a)
                a["manual_verdict"] = ""   # DISTRESS | REJECT | HARD_NEGATIVE | AMBIGUOUS
                a["manual_notes"] = ""
                rw.writerow(a)
        log(f"Wrote {REVIEW_CSV} ({len(review)} rows for manual review)")

        # -------------------------------------------------------------- summary
        counts = {c: len(by_cat.get(c, [])) for c in CATEGORIES}
        for c, items in by_cat.items():
            counts.setdefault(c, len(items))
        split_counts = {}
        for a in audited:
            split_counts.setdefault(a["source_split"], 0)
            split_counts[a["source_split"]] += 1

        durations = [a["duration"] for a in audited if a["file_valid"]]
        lufs = [a["loudness_lufs"] for a in audited if a["file_valid"] and a["loudness_lufs"] not in ("", None)]
        rmsdb = [a["rms_dbfs"] for a in audited if a["file_valid"]]
        peaks = [a["peak_amplitude"] for a in audited if a["file_valid"]]
        clips = [a["clipping_pct"] for a in audited if a["file_valid"]]
        sils = [a["silence_pct"] for a in audited if a["file_valid"]]

        d_stats, l_stats = dist_stats(durations), dist_stats(lufs)
        r_stats, p_stats = dist_stats(rmsdb), dist_stats(peaks)
        c_stats, s_stats = dist_stats(clips), dist_stats(sils)

        total_dur = float(np.nansum([d for d in durations if d]))
        n_clip_any = sum(1 for c in clips if c and c > 0)
        n_clip_1 = sum(1 for c in clips if c and c > 1.0)
        n_sil_40 = sum(1 for s in sils if s and s > 40)
        n_sil_70 = sum(1 for s in sils if s and s > 70)
        n_susp = sum(1 for a in audited if a["suspicious"])
        n_invalid = sum(1 for a in audited if not a["file_valid"])
        srs = sorted({a["sample_rate"] for a in audited if a["file_valid"]})
        chs = sorted({a["channels"] for a in audited if a["file_valid"]})
        meta_ok = sum(1 for a in audited if a["youtube_metadata_status"] == "OK")

        log("CATEGORY COUNTS: " + json.dumps(counts))
        log(f"suspicious={n_susp} invalid={n_invalid} total_duration_sec={total_dur:.1f}")

        conf_counts = {}
        for a in audited:
            key = f"{a['content_category']}|{a['category_confidence']}"
            conf_counts[key] = conf_counts.get(key, 0) + 1

        def cat_table() -> str:
            lines = ["| Category | Count | % of total |", "|---|---:|---:|"]
            n = len(audited) or 1
            for c in CATEGORIES:
                lines.append(f"| {c} | {counts.get(c, 0)} | {100.0 * counts.get(c, 0) / n:.1f}% |")
            lines.append(f"| **TOTAL** | **{len(audited)}** | 100% |")
            return "\n".join(lines)

        top_labels = {}
        for a in audited:
            for lbl in (a["audioset_positive_labels"] or "").split("|"):
                if lbl and lbl != "Screaming":
                    top_labels[lbl] = top_labels.get(lbl, 0) + 1
        top_lbl_lines = "\n".join(
            f"- {k}: {v}" for k, v in sorted(top_labels.items(), key=lambda x: -x[1])[:20]
        ) or "- none"

        # Why so few distress candidates? Measure the raw keyword base rate so the
        # result can be checked independently of the category precedence rules.
        strong_title = [a for a in audited if matched((a["youtube_title"] or "").lower(),
                                                      STRONG_DISTRESS_KW)]
        strong_any = [a for a in audited
                      if matched(((a["youtube_title"] or "") + " " + (a["category_evidence"] or "")).lower(),
                                 STRONG_DISTRESS_KW)]
        music_label_only = [a for a in audited
                            if a["content_category"] == "MUSIC_RELATED"
                            and "audioset_labels=Music" in (a["category_evidence"] or "")
                            and "music_kw" not in (a["category_evidence"] or "")
                            and "yt_category=Music" not in (a["category_evidence"] or "")]
        strong_title_lines = "\n".join(
            f"- `{a['clip_id']}` — {a['youtube_title'][:90]} → {a['content_category']}"
            for a in strong_title[:10]) or "- none"
        no_meta_n = sum(1 for a in audited if a["youtube_metadata_status"] != "OK")
        amb_no_meta_n = sum(1 for a in audited if a["content_category"] == "AMBIGUOUS"
                            and a["youtube_metadata_status"] != "OK")

        ended = datetime.now()
        AUDIT_MD.write_text(f"""# AudioSet Screaming — Quality & Content Audit

Run: {started.isoformat(timespec='seconds')} → {ended.isoformat(timespec='seconds')}  
Dataset audited: `{OUT}`  
Files audited: **{len(audited)}** (balanced_train {split_counts.get('balanced_train', 0)}, unbalanced_train {split_counts.get('unbalanced_train', 0)})

## Method and its limits

- Acoustic measurements are computed directly from the WAV files (objective).
- **Content categories are metadata/heuristic-based only.** They come from
  AudioSet co-occurring labels plus YouTube title/description/tags/category text.
- **No human listened to any clip and no audio classifier was run for
  categorisation.** The categories are advisory and are expected to contain errors.
- YouTube metadata was retrievable for **{meta_ok}/{len(audited)}** clips.
- `source_label` remains **SCREAMING** for every clip. Nothing was relabelled
  DISTRESS, nothing was merged into SafeHer training data, no model was trained.

## Content categories (heuristic)

{cat_table()}

Confidence breakdown (category|confidence): `{json.dumps(conf_counts, sort_keys=True)}`

## Key finding: almost no real-emergency material

Only **{len(strong_title)}** of {len(audited)} clips carry an explicit real-distress
term (assault / robbery / kidnap / "help me" / etc.) in the YouTube title, and
**{len(strong_any)}** carry one in the title or matched evidence. This is a property of
the corpus, not of the category precedence rules: AudioSet "Screaming" is dominated by
entertainment media, music, comedy and crowd/fun screaming.

{strong_title_lines}

Practical implication for SafeHer: this dataset is **not** a source of DISTRESS
positives. Its realistic value is as **hard negatives** (screams that must not trigger
SOS) plus a small number of clips that may survive manual review as genuine distress.

## How to read these categories

- `MUSIC_RELATED` ({counts.get('MUSIC_RELATED', 0)}) is triggered mostly by the AudioSet
  `Music` co-label ({len(music_label_only)} clips have that as their only music evidence).
  That co-label usually means *music is audible in the clip*, not that the scream itself
  is musical. Treat it as "contaminated with music", not as a genre judgement.
- `MOVIE_OR_MEDIA` and `NON_DISTRESS_SCREAM` rest largely on title/tag wording, which is
  noisy; the exact trigger for every clip is in the `category_evidence` column.
- `AMBIGUOUS` ({counts.get('AMBIGUOUS', 0)}) means the metadata carried no usable signal.
  {amb_no_meta_n} of them have no YouTube metadata at all (video now inaccessible);
  the rest had metadata that matched no lexicon. Ambiguous does **not** mean distress.
- `LOW_QUALITY` is purely technical (short / clipped / mostly silent) and is decided
  before any content rule, so a low-quality clip is never also categorised by content.

## Technical validity

- Valid/readable WAV: **{len(audited) - n_invalid}**
- Invalid/unreadable: **{n_invalid}**
- Sample rates present: {srs} Hz
- Channels present: {chs}
- Total audio duration: **{total_dur / 3600:.3f} h** ({total_dur:.1f} s)
- Flagged suspicious (any reason): **{n_susp}**

## Duration distribution (seconds)

{fmt_stats("duration", d_stats, "s")}

## Loudness distribution

{fmt_stats("integrated loudness (LUFS)", l_stats, " LUFS")}
{fmt_stats("RMS level (dBFS)", r_stats, " dBFS")}
{fmt_stats("peak amplitude (linear)", p_stats)}

## Clipping

{fmt_stats("clipping percentage", c_stats, "%")}
- Clips with any clipped samples: **{n_clip_any}**
- Clips with >1% clipped samples: **{n_clip_1}**

## Silence

{fmt_stats("silence percentage (frames < {:.0f} dBFS)".format(SILENCE_FRAME_DBFS), s_stats, "%")}
- Clips with >40% silence: **{n_sil_40}**
- Clips with >70% silence: **{n_sil_70}**

## Most common co-occurring AudioSet labels (excluding Screaming)

{top_lbl_lines}

## Manual review list

`{REVIEW_CSV}` — **{len(review)}** clips:
all suspicious/low-quality clips plus up to {REVIEW_PER_CATEGORY} random samples per category
(seed {SEED}). It has empty `manual_verdict` / `manual_notes` columns for
DISTRESS / REJECT / HARD_NEGATIVE / AMBIGUOUS decisions.

## Outputs

- `{AUDIT_CSV}`
- `{REVIEW_CSV}`
- `{AUDIT_MD}`
- `{AUDIT_LOG}`

## Not done (by instruction)

- No training (no Audio v5).
- No merge into the SafeHer training dataset.
- No changes to raw audio, audio_v2/v3/v4, Speech, Movement, SOS, Android, backend.
""", encoding="utf-8")

        log(f"Wrote {AUDIT_MD}")
        log(f"End: {ended.isoformat()}")
        log("STATUS=AUDIT_COMPLETE")

        print("===AUDIT_SUMMARY===")
        print(json.dumps({
            "total": len(audited), "counts": counts, "invalid": n_invalid,
            "suspicious": n_susp, "review_list": len(review),
            "total_duration_h": total_dur / 3600.0,
            "youtube_metadata_ok": meta_ok,
        }, indent=2))
    except Exception:
        log("ERROR")
        log(traceback.format_exc())
        log("STATUS=FAILED")
        raise
    finally:
        fh.close()


if __name__ == "__main__":
    main()
