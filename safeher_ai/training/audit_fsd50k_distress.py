"""
Quality + content audit of the derived FSD50K distress-adjacent dataset.

Audits ONLY: safeher_ai/data/derived/fsd50k_distress/
Does NOT train, does NOT merge, does NOT relabel anything as DISTRESS.
Clips keep source_label = FSD50K_<classes>; this audit adds an ADVISORY category.

Content categorisation is METADATA/HEURISTIC-BASED: no human listened to the audio
and no audio classifier was run. It uses three signals:
  1. FSD50K's curated labels (human-verified, far cleaner than AudioSet co-labels)
  2. Freesound title/tags (describe the sound itself) and description (noisy)
  3. FSD50K PP/PNP human ratings, which say whether the target class is
     PREDOMINANT in the clip or merely present in the background

Outputs:
  metadata/quality_audit.csv
  metadata/manual_review_list.csv
  ../../training_logs/fsd50k_distress_quality_audit.md
  ../../training_logs/fsd50k_distress_quality_audit.log

Run:
  ..\\venv311\\Scripts\\python.exe training\\audit_fsd50k_distress.py
"""

from __future__ import annotations

import csv
import json
import random
import sys
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_audioset_screaming import analyse_wav, dist_stats, fmt_stats, matched  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "derived" / "fsd50k_distress"
META_DIR = OUT / "metadata"
PROBE_META = DATA / "derived" / "fsd50k_distress_probe" / "extracted" / "FSD50K.metadata"
VOCAB = DATA / "derived" / "fsd50k_distress_probe" / "extracted" / "FSD50K.ground_truth" / "vocabulary.csv"
TRAIN_LOG = DATA / "training_logs"

SRC_CSV = META_DIR / "fsd50k_distress_metadata.csv"
AUDIT_CSV = META_DIR / "quality_audit.csv"
REVIEW_CSV = META_DIR / "manual_review_list.csv"
AUDIT_MD = TRAIN_LOG / "fsd50k_distress_quality_audit.md"
AUDIT_LOG = TRAIN_LOG / "fsd50k_distress_quality_audit.log"

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
# FSD50K clips run 0.3-30 s, so unlike the fixed 10 s AudioSet segments the only
# hard duration floor is "too short to contain a vocalisation".
MIN_DURATION_S = 0.35
SILENCE_PCT_BAD = 85.0
CLIP_PCT_BAD = 5.0
NEAR_SILENT_RMS_DBFS = -50.0

SUSPICIOUS_SILENCE_PCT = 60.0
SUSPICIOUS_CLIP_PCT = 1.0
SUSPICIOUS_RMS_DBFS = -40.0
SUSPICIOUS_SHORT_S = 1.0

TARGET_CLASSES = ["Screaming", "Shout", "Yell", "Crying_and_sobbing", "Gasp"]

# ------------------------------------------------------------ label lexicons
MUSIC_LABELS = {
    "Music", "Singing", "Musical_instrument", "Guitar", "Drum", "Piano",
    "Percussion", "Bass_guitar", "Electric_guitar", "Acoustic_guitar",
    "Drum_kit", "Snare_drum", "Bass_drum", "Cymbal", "Hi-hat", "Rattle_(instrument)",
    "Plucked_string_instrument", "Keyboard_(musical)", "Organ", "Harmonica",
    "Trumpet", "Brass_instrument", "Wind_instrument_and_woodwind_instrument",
    "Bowed_string_instrument", "Violin_and_fiddle", "Chime", "Bell", "Gong",
    "Marimba_and_xylophone", "Glockenspiel", "Mallet_percussion", "Tabla",
    "Harp", "Accordion", "Scratching_(performance_technique)", "Chirp_tone",
}
NON_DISTRESS_LABELS = {
    "Laughter", "Giggle", "Chuckle_and_chortle", "Cheering", "Applause",
    "Crowd", "Clapping", "Chatter", "Conversation", "Child_speech_and_kid_speaking",
    "Babbling", "Whoop", "Booing", "Cough", "Sneeze", "Burping_and_eructation",
    "Hiccup", "Whistling", "Yodeling", "Chant",
}
ANIMAL_LABELS = {
    "Animal", "Dog", "Bark", "Cat", "Meow", "Bird", "Bird_vocalization_and_bird_call_and_bird_song",
    "Chirp_and_tweet", "Livestock_and_farm_animals_and_working_animals",
    "Domestic_animals_and_pets", "Wild_animals", "Rodents_and_rats_and_mice",
    "Growling", "Purr", "Crow", "Caw", "Fowl", "Chicken_and_rooster", "Insect",
    "Cricket", "Frog", "Pigeon_and_dove", "Owl", "Squeak", "Roaring_cats_(lions_and_tigers)",
}
DISTRESS_SUPPORT_LABELS = {
    "Crying_and_sobbing", "Screaming", "Shout", "Yell", "Gasp", "Whispering",
    "Breathing", "Groan", "Sigh",
}
VIOLENCE_LABELS = {
    "Gunshot_and_gunfire", "Explosion", "Siren", "Emergency_vehicle",
    "Police_car_(siren)", "Ambulance_(siren)", "Fire_engine_and_fire_truck_(siren)",
    "Civil_defense_siren", "Glass", "Shatter", "Crushing", "Slam", "Thump_and_thud",
}

# --------------------------------------------------------- keyword lexicons
# Freesound titles/tags describe the sound itself, so they are much more
# informative than YouTube titles were for AudioSet.
# NOTE: "vocal"/"vocals" are deliberately absent. On Freesound those tag any
# human-voice recording, not music, and including them mislabelled ~110 plain
# screams and cries as MUSIC_RELATED.
MUSIC_KW = [
    "song", "album", "remix", "band", "concert", "melody", "chord", "riff",
    "guitar", "drum", "piano", "synth", "bass", "beat", "loop", "bpm",
    "singing", "sing", "choir", "karaoke", "instrumental",
    "metal", "screamo", "hardcore", "rap", "acapella", "a capella", "harmony",
]
# Provenance words: the clip really is from/for a game, film or cartoon.
MEDIA_STRONG_KW = [
    "game", "gaming", "videogame", "video game", "rpg", "fps", "arcade",
    "monster", "zombie", "demon", "creature", "beast", "orc", "goblin", "troll",
    "alien", "ghost", "witch", "vampire", "werewolf", "dragon", "mutant",
    "cartoon", "anime", "animation", "comic", "movie", "film", "trailer",
    "sword", "magic", "spell", "boss", "npc", "character", "war cry", "warcry",
]
# Genre/production words. On Freesound these usually describe intended USE
# ("this scream suits horror") or post-processing, not that the clip came from
# a film, so one of them alone is not enough to call a clip media-derived.
MEDIA_WEAK_KW = [
    "horror", "sci-fi", "scifi", "fantasy", "cinematic", "epic", "battle",
    "processed", "pitched", "reverb", "distorted", "layered", "designed",
    "sound design", "sfx", "fx", "effect", "synthesized", "synthetic",
]
NON_DISTRESS_KW = [
    "laugh", "laughing", "laughter", "giggle", "chuckle", "funny", "comedy",
    "joke", "cheer", "cheering", "crowd", "applause", "clapping", "audience",
    "stadium", "sport", "sports", "football", "soccer", "goal", "celebration",
    "celebrating", "party", "fun", "excited", "excitement", "happy", "joy",
    "yay", "woohoo", "hooray", "victory", "win", "winning", "chant", "chanting",
    "protest", "rally", "march", "singing crowd", "kids playing", "playground",
    "children playing", "roller coaster", "rollercoaster", "amusement",
    "goat", "monkey", "animal", "dog", "cat", "bird", "pig", "seagull",
    "burp", "sneeze", "cough", "yawn", "snore", "hiccup", "whistle",
]
STRONG_DISTRESS_KW = [
    "help", "help me", "helpme", "cry for help", "screaming for help",
    "distress", "terror", "terrified", "terrifying", "panic", "panicked",
    "agony", "agonizing", "anguish", "painful", "in pain", "hurt", "hurting",
    "suffering", "torture", "tortured", "victim", "attacked", "attack",
    "assault", "murder", "kidnap", "abduction", "emergency", "rescue",
    "desperate", "despair", "begging", "plead", "pleading", "frightened",
    "scared", "afraid", "fear", "fearful", "horrified", "distressed",
    "danger", "dangerous", "threat", "threatened", "trapped", "abuse",
]
MODERATE_DISTRESS_KW = [
    "scream", "screaming", "screams", "shriek", "shrieking", "wail", "wailing",
    "sob", "sobbing", "crying", "cry", "weep", "weeping", "moan", "moaning",
    "whimper", "whimpering", "yell", "yelling", "shout", "shouting",
    "gasp", "gasping", "shock", "shocked", "surprise", "startled", "alarm",
    "female scream", "woman scream", "girl scream", "male scream",
]
# Freesound is a sound-effects library; these words mark deliberately performed
# or studio-produced material rather than a captured real event.
ACTED_KW = [
    "acted", "acting", "actor", "actress", "voice acting", "voice over",
    "voiceover", "recorded", "recording", "studio", "microphone", "mic",
    "foley", "library", "sample pack", "sound library", "sound pack",
    "take 1", "take 2", "take 3", "performance", "performed", "improvised",
    "zoom h4n", "zoom h5", "h6", "rode", "shure", "sennheiser", "condenser",
    "field recording", "48khz", "96khz", "24bit", "44.1",
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


def load_vocab_mids() -> dict[str, str]:
    """display_name -> mid"""
    out = {}
    if not VOCAB.exists():
        return out
    with open(VOCAB, encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) >= 3:
                out[row[1].strip()] = row[2].strip()
    return out


def load_ratings() -> dict[int, dict[str, list[float]]]:
    p = PROBE_META / "pp_pnp_ratings_FSD50K.json"
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return {int(k): v for k, v in json.load(f).items()}


def predominance(ratings: dict, fid: int, classes: list[str],
                 name2mid: dict[str, str]) -> tuple[str, float | None]:
    """
    FSD50K PP/PNP: 1.0 = present & predominant, 0.5 = present but not predominant,
    0 = not present, -1 = unsure. Take the best-rated target class for the clip.
    """
    rec = ratings.get(fid)
    if not rec:
        return "UNRATED", None
    best = None
    for c in classes:
        mid = name2mid.get(c)
        if not mid or mid not in rec:
            continue
        vals = [v for v in rec[mid] if v is not None and v >= 0]
        if not vals:
            continue
        m = float(np.mean(vals))
        if best is None or m > best:
            best = m
    if best is None:
        return "UNRATED", None
    if best >= 0.875:
        return "PREDOMINANT", best
    if best >= 0.5:
        return "PRESENT_NOT_PREDOMINANT", best
    return "WEAK_OR_ABSENT", best


def categorise(ac: dict, labels: set[str], title: str, tags: str, desc: str,
               pred_flag: str) -> dict:
    """Heuristic, metadata-based advisory category. Never asserts listening."""
    evidence: list[str] = []

    if not ac.get("readable"):
        return {"category": "LOW_QUALITY", "confidence": "HIGH",
                "evidence": f"unreadable: {ac.get('analysis_error')}"}

    dur = ac.get("duration") or 0.0
    sil = ac.get("silence_pct") or 0.0
    clip = ac.get("clipping_pct") or 0.0
    rms_db = ac.get("rms_dbfs")
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
                "evidence": "; ".join(lowq)}

    # Title and tags name the sound; descriptions carry licence boilerplate and
    # gear talk, so they are only ever weak evidence.
    strong_text = f"{title} {tags}".lower()
    desc_text = (desc or "").lower()

    music_lab = labels & MUSIC_LABELS
    nond_lab = labels & NON_DISTRESS_LABELS
    animal_lab = labels & ANIMAL_LABELS
    distress_lab = labels & DISTRESS_SUPPORT_LABELS
    violence_lab = labels & VIOLENCE_LABELS

    music_t, music_d = matched(strong_text, MUSIC_KW), matched(desc_text, MUSIC_KW)
    media_s = matched(strong_text, MEDIA_STRONG_KW)
    media_w = matched(strong_text, MEDIA_WEAK_KW)
    media_t = media_s + media_w
    media_d = matched(desc_text, MEDIA_STRONG_KW)
    nond_t, nond_d = matched(strong_text, NON_DISTRESS_KW), matched(desc_text, NON_DISTRESS_KW)
    strong_kw = matched(strong_text, STRONG_DISTRESS_KW)
    strong_d = matched(desc_text, STRONG_DISTRESS_KW)
    mod_t = matched(strong_text, MODERATE_DISTRESS_KW)

    def ev(tag, t, d):
        if t:
            evidence.append(f"{tag}_title={','.join(t[:5])}")
        elif d:
            evidence.append(f"{tag}_desc={','.join(d[:5])}")

    if music_lab or music_t or len(music_d) >= 3:
        if music_lab:
            evidence.append("fsd_labels=" + ",".join(sorted(music_lab)))
        ev("music_kw", music_t, music_d)
        return {"category": "MUSIC_RELATED",
                "confidence": "MEDIUM" if music_lab else "LOW",
                "evidence": "; ".join(evidence)}

    # one provenance word is enough; genre/production words need corroboration
    if media_s or len(media_w) >= 2 or len(media_d) >= 2:
        if media_s:
            evidence.append("media_kw=" + ",".join(media_s[:5]))
        if media_w:
            evidence.append("media_weak_kw=" + ",".join(media_w[:5]))
        if not media_s and not media_w and media_d:
            evidence.append("media_kw_desc=" + ",".join(media_d[:5]))
        return {"category": "MOVIE_OR_MEDIA",
                "confidence": "MEDIUM" if len(media_s) >= 2 else "LOW",
                "evidence": "; ".join(evidence)}

    if nond_lab or animal_lab or nond_t or len(nond_d) >= 3:
        if nond_lab:
            evidence.append("fsd_labels=" + ",".join(sorted(nond_lab)))
        if animal_lab:
            evidence.append("animal_labels=" + ",".join(sorted(animal_lab)))
        ev("nondistress_kw", nond_t, nond_d)
        return {"category": "NON_DISTRESS_SCREAM",
                "confidence": "MEDIUM" if (nond_lab or animal_lab) else "LOW",
                "evidence": "; ".join(evidence)}

    # a lone genre word must not veto distress evidence either
    contradicted = bool(music_t or media_s or len(media_w) >= 2 or nond_t)

    if strong_kw and not contradicted:
        evidence.append("strong_kw=" + ",".join(strong_kw[:5]))
        evidence.append(f"predominance={pred_flag}")
        if violence_lab:
            evidence.append("context_labels=" + ",".join(sorted(violence_lab)))
        conf = "MEDIUM" if (pred_flag == "PREDOMINANT" and len(strong_kw) >= 2) else "LOW"
        return {"category": "LIKELY_DISTRESS", "confidence": conf,
                "evidence": "; ".join(evidence)}

    if (strong_d and not contradicted) or (mod_t and pred_flag == "PREDOMINANT"):
        if strong_d:
            evidence.append("strong_kw_desc=" + ",".join(strong_d[:5]))
        if mod_t:
            evidence.append("moderate_kw=" + ",".join(mod_t[:5]))
        evidence.append(f"predominance={pred_flag}")
        if distress_lab:
            evidence.append("fsd_labels=" + ",".join(sorted(distress_lab)))
        return {"category": "POSSIBLE_DISTRESS", "confidence": "LOW",
                "evidence": "; ".join(evidence)}

    if mod_t:
        evidence.append("moderate_kw=" + ",".join(mod_t[:5]))
    if distress_lab:
        evidence.append("fsd_labels=" + ",".join(sorted(distress_lab)))
    evidence.append(f"predominance={pred_flag}")
    return {"category": "AMBIGUOUS", "confidence": "LOW",
            "evidence": "; ".join(evidence) or "insufficient_metadata_signal"}


def main():
    TRAIN_LOG.mkdir(parents=True, exist_ok=True)
    fh = open(AUDIT_LOG, "w", encoding="utf-8")
    log = log_factory(fh)
    started = datetime.now()

    try:
        log("=" * 70)
        log("FSD50K distress-adjacent - quality + content audit (NO TRAINING, NO MERGE)")
        log(f"Start: {started.isoformat()}")
        log(f"Dataset: {OUT}")
        log("source_label stays FSD50K_<classes>; categories below are ADVISORY ONLY.")
        log("Categories are METADATA/HEURISTIC-BASED - audio was NOT listened to.")

        name2mid = load_vocab_mids()
        ratings = load_ratings()
        log(f"Vocabulary mids={len(name2mid)} pp_pnp_rated_clips={len(ratings)}")

        rows = list(csv.DictReader(open(SRC_CSV, encoding="utf-8")))
        log(f"Clips in metadata: {len(rows)}")

        fields = [
            "freesound_id", "wav_path", "source_label", "matched_classes", "all_labels",
            "set", "split", "license", "attribution_required", "uploader", "title",
            "tags", "freesound_url",
            "duration", "sample_rate", "channels", "frames",
            "rms", "rms_dbfs", "peak_amplitude", "peak_dbfs", "loudness_lufs",
            "crest_factor_db", "clipping_pct", "silence_pct", "dc_offset",
            "spectral_centroid_hz", "spectral_flatness", "zero_crossing_rate",
            "file_valid", "suspicious", "suspicious_reasons",
            "predominance", "predominance_score",
            "content_category", "category_confidence", "category_evidence",
            "category_basis", "analysis_error",
        ]

        audited = []
        with open(AUDIT_CSV, "w", encoding="utf-8", newline="") as af:
            w = csv.DictWriter(af, fieldnames=fields, extrasaction="ignore")
            w.writeheader()

            for i, r in enumerate(rows, 1):
                wav = ROOT / r["wav_path"]
                ac = analyse_wav(wav) if wav.exists() else {
                    "readable": False, "analysis_error": "file_missing_on_disk"}

                fid = int(r["freesound_id"])
                labels = {x for x in (r["all_labels"] or "").split("|") if x}
                classes = [x for x in (r["matched_classes"] or "").split("|") if x]
                pred_flag, pred_score = predominance(ratings, fid, classes, name2mid)

                cat = categorise(ac, labels, r.get("title", ""), r.get("tags", ""),
                                 r.get("description", ""), pred_flag)

                reasons = []
                if ac.get("readable"):
                    if (ac.get("silence_pct") or 0) > SUSPICIOUS_SILENCE_PCT:
                        reasons.append(f"silence={ac['silence_pct']:.1f}%")
                    if (ac.get("clipping_pct") or 0) > SUSPICIOUS_CLIP_PCT:
                        reasons.append(f"clipping={ac['clipping_pct']:.2f}%")
                    if ac.get("rms_dbfs") is not None and ac["rms_dbfs"] < SUSPICIOUS_RMS_DBFS:
                        reasons.append(f"quiet_rms={ac['rms_dbfs']:.1f}dBFS")
                    if (ac.get("duration") or 0) < SUSPICIOUS_SHORT_S:
                        reasons.append(f"short={ac['duration']:.2f}s")
                else:
                    reasons.append("unreadable")

                out = dict(r)
                out.update({
                    "file_valid": bool(ac.get("readable")),
                    "suspicious": bool(reasons),
                    "suspicious_reasons": "; ".join(reasons),
                    "predominance": pred_flag,
                    "predominance_score": "" if pred_score is None else round(pred_score, 3),
                    "content_category": cat["category"],
                    "category_confidence": cat["confidence"],
                    "category_evidence": cat["evidence"],
                    "category_basis": "metadata_heuristic_only__not_listened",
                })
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
                review[a["freesound_id"]] = a2
        # every high-value candidate gets reviewed, not just a sample
        for a in audited:
            if a["content_category"] in ("LIKELY_DISTRESS", "POSSIBLE_DISTRESS") \
                    and a["predominance"] == "PREDOMINANT" and a["freesound_id"] not in review:
                a2 = dict(a)
                a2["review_reason"] = f"priority_candidate:{a['content_category']}_predominant"
                review[a["freesound_id"]] = a2
        for c, items in by_cat.items():
            if not items:
                continue
            for a in rnd.sample(items, min(REVIEW_PER_CATEGORY, len(items))):
                if a["freesound_id"] in review:
                    continue
                a2 = dict(a)
                a2["review_reason"] = f"random_sample:{c}"
                review[a["freesound_id"]] = a2

        review_fields = ["freesound_id", "wav_path", "matched_classes", "set", "license",
                         "content_category", "category_confidence", "predominance",
                         "review_reason", "duration", "rms_dbfs", "loudness_lufs",
                         "clipping_pct", "silence_pct", "title", "tags",
                         "all_labels", "category_evidence", "freesound_url",
                         "manual_verdict", "manual_notes"]
        with open(REVIEW_CSV, "w", encoding="utf-8", newline="") as rf:
            rw = csv.DictWriter(rf, fieldnames=review_fields, extrasaction="ignore")
            rw.writeheader()
            for a in sorted(review.values(),
                            key=lambda x: (x["content_category"], int(x["freesound_id"]))):
                a = dict(a)
                a["manual_verdict"] = ""   # DISTRESS | REJECT | HARD_NEGATIVE | AMBIGUOUS
                a["manual_notes"] = ""
                rw.writerow(a)
        log(f"Wrote {REVIEW_CSV} ({len(review)} rows for manual review)")

        # -------------------------------------------------------------- summary
        counts = {c: len(by_cat.get(c, [])) for c in CATEGORIES}
        valid = [a for a in audited if a["file_valid"]]
        durations = [a["duration"] for a in valid]
        lufs = [a["loudness_lufs"] for a in valid if a["loudness_lufs"] not in ("", None)]
        rmsdb = [a["rms_dbfs"] for a in valid]
        peaks = [a["peak_amplitude"] for a in valid]
        clips = [a["clipping_pct"] for a in valid]
        sils = [a["silence_pct"] for a in valid]

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
        srs = sorted({a["sample_rate"] for a in valid})
        chs = sorted({a["channels"] for a in valid})

        pred_counts = Counter(a["predominance"] for a in audited)
        lic_counts = Counter(a["license"] for a in audited)
        set_counts = Counter(a["set"] for a in audited)
        conf_counts = Counter(f"{a['content_category']}|{a['category_confidence']}"
                              for a in audited)

        class_counts = Counter()
        for a in audited:
            for c in (a["matched_classes"] or "").split("|"):
                if c:
                    class_counts[c] += 1

        # how much of this is studio/library material rather than captured events
        acted = [a for a in audited
                 if matched(f"{a.get('title','')} {a.get('tags','')}".lower(), ACTED_KW)]

        predominant_distress = [a for a in audited
                                if a["predominance"] == "PREDOMINANT"
                                and a["content_category"] in ("LIKELY_DISTRESS",
                                                              "POSSIBLE_DISTRESS")]
        likely = by_cat.get("LIKELY_DISTRESS", [])
        likely_examples = "\n".join(
            f"- `{a['freesound_id']}` [{a['predominance']}] {(a.get('title') or '')[:70]}"
            for a in sorted(likely, key=lambda x: x["predominance"] != "PREDOMINANT")[:12]
        ) or "- none"

        hard_neg = counts.get("NON_DISTRESS_SCREAM", 0) + counts.get("MOVIE_OR_MEDIA", 0) \
            + counts.get("MUSIC_RELATED", 0)

        log("CATEGORY COUNTS: " + json.dumps(counts))
        log("PREDOMINANCE: " + json.dumps(dict(pred_counts)))
        log(f"suspicious={n_susp} invalid={n_invalid} total_duration_h={total_dur/3600:.3f}")

        def table(d: dict, header: str) -> str:
            n = len(audited) or 1
            lines = [f"| {header} | Count | % |", "|---|---:|---:|"]
            for k, v in (d.items() if isinstance(d, dict) else d):
                lines.append(f"| {k} | {v} | {100.0*v/n:.1f}% |")
            return "\n".join(lines)

        cat_lines = ["| Category | Count | % of total |", "|---|---:|---:|"]
        for c in CATEGORIES:
            cat_lines.append(f"| {c} | {counts.get(c,0)} | {100.0*counts.get(c,0)/(len(audited) or 1):.1f}% |")
        cat_lines.append(f"| **TOTAL** | **{len(audited)}** | 100% |")
        cat_table = "\n".join(cat_lines)

        ended = datetime.now()
        AUDIT_MD.write_text(f"""# FSD50K distress-adjacent - Quality & Content Audit

Run: {started.isoformat(timespec='seconds')} -> {ended.isoformat(timespec='seconds')}  
Dataset audited: `{OUT}`  
Files audited: **{len(audited)}** ({', '.join(f'{k} {v}' for k, v in set_counts.items())})  
All clips are commercial-safe (CC0 / CC-BY); NC and Sampling+ were never downloaded.

## Method and its limits

- Acoustic measurements are computed directly from the WAV files (objective).
- **Content categories are metadata/heuristic-based only.** They combine FSD50K's
  curated labels, Freesound title/tags/description text, and the FSD50K PP/PNP
  human ratings.
- **No human listened to any clip and no audio classifier was run.** Categories are
  advisory and will contain errors.
- `source_label` remains `FSD50K_<classes>`. Nothing was relabelled DISTRESS, nothing
  was merged into SafeHer training data, no model was trained.

## Content categories (heuristic)

{cat_table}

Confidence breakdown: `{json.dumps(dict(conf_counts), sort_keys=True)}`

## Predominance (FSD50K human ratings)

This is the signal AudioSet did not have. PP/PNP tells us whether the target class is
the *predominant* sound in the clip or merely audible in the background.

{table(dict(pred_counts), "Predominance")}

**{len(predominant_distress)}** clips are both distress-categorised and PREDOMINANT -
these are the strongest positive candidates in the set.

## Class coverage

{table(dict(class_counts.most_common()), "FSD50K class")}

Classes overlap, so these sum to more than {len(audited)}.

## The acted-material caveat

Freesound is a sound-effects library. **{len(acted)}** of {len(audited)} clips carry
explicit studio/library/recording-gear wording in the title or tags, and the true
proportion of performed rather than captured material is certainly higher. As with
AudioSet Screaming, this dataset is best understood as:

- a good source of **hard negatives** ({hard_neg} clips categorised as music, media or
  non-distress screaming) that must never trigger SOS, and
- a pool of **acted distress candidates** ({counts.get('LIKELY_DISTRESS',0)} likely +
  {counts.get('POSSIBLE_DISTRESS',0)} possible) that still need human review, and which
  will not close the domain gap to real phone-microphone emergency audio on their own.

Highest-value LIKELY_DISTRESS examples:

{likely_examples}

## Technical validity

- Valid/readable WAV: **{len(valid)}**
- Invalid/unreadable: **{n_invalid}**
- Sample rates present: {srs} Hz
- Channels present: {chs}
- Total audio duration: **{total_dur/3600:.3f} h** ({total_dur:.1f} s)
- Flagged suspicious (any reason): **{n_susp}**

## Licensing

{table(dict(lic_counts), "License")}

CC-BY clips require attribution if shipped; see `data/derived/fsd50k_distress/ATTRIBUTION.md`.

## Duration distribution (seconds)

{fmt_stats("duration", d_stats, "s")}

Unlike the fixed 10 s AudioSet segments, FSD50K clip length varies, so duration is a
real variable here and short clips are normal rather than defective.

## Loudness distribution

{fmt_stats("integrated loudness (LUFS)", l_stats, " LUFS")}
{fmt_stats("RMS level (dBFS)", r_stats, " dBFS")}
{fmt_stats("peak amplitude (linear)", p_stats)}

## Clipping

{fmt_stats("clipping percentage", c_stats, "%")}
- Clips with any clipped samples: **{n_clip_any}**
- Clips with >1% clipped samples: **{n_clip_1}**

## Silence

{fmt_stats("silence percentage", s_stats, "%")}
- Clips with >40% silence: **{n_sil_40}**
- Clips with >70% silence: **{n_sil_70}**

## Manual review list

`{REVIEW_CSV}` - **{len(review)}** clips: every suspicious/low-quality clip, every
distress-categorised clip rated PREDOMINANT, plus up to {REVIEW_PER_CATEGORY} random
samples per category (seed {SEED}). Empty `manual_verdict` / `manual_notes` columns are
there for DISTRESS / REJECT / HARD_NEGATIVE / AMBIGUOUS decisions.

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
        log("STATUS=AUDIT_COMPLETE")

        print("===FSD50K_AUDIT===")
        print(json.dumps({
            "total": len(audited), "counts": counts,
            "predominance": dict(pred_counts),
            "predominant_distress": len(predominant_distress),
            "invalid": n_invalid, "suspicious": n_susp, "review_list": len(review),
            "total_duration_h": round(total_dur / 3600.0, 3),
            "acted_wording": len(acted),
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
