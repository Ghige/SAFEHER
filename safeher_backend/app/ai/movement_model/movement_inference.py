"""
SafeHer — Movement Model Inference V2

Detects panic movement from accelerometer data.
New in V2:
  - Fall detection (sudden drop + impact + stillness)
  - Vehicle baseline suppression (bus, auto, train, bike)
  - Pocket position normalization (front, back, handbag, hand)
  - Jogging suppression (was defined but never called in V1)
  - Continuous soft scoring (no more hard step thresholds)

Output feeds into confidence_scorer.py:
  predict_panic_movement() → 0.0–100.0
  detect_fall()            → bool  (hard signal, bypasses soft score)

Usage:
    from movement_inference import predict_panic_movement, detect_fall, set_context

    # Set context once when it changes (optional but improves accuracy)
    set_context(vehicle="bus", pocket="handbag")

    # Every 3 seconds (30 samples at 10Hz):
    score     = predict_panic_movement(accel_data)
    fell      = detect_fall(accel_data)
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)


# ── Runtime context ───────────────────────────────────────────────────────────
# Set by the app when it knows the user's situation.
# Affects baseline subtraction and suppression thresholds.
#
# vehicle: "none" | "bus" | "auto" | "train" | "bike"
# pocket:  "hand" | "front" | "back" | "handbag"

_context = {
    "vehicle": "none",
    "pocket":  "hand",
}

def set_context(vehicle: str = None, pocket: str = None):
    """
    Update runtime context. Call when vehicle or pocket position changes.

    vehicle — detected via Google Activity Recognition API:
        "none"  = on foot
        "bus"   = in vehicle (high vibration, rhythmic)
        "auto"  = auto-rickshaw (high vibration, irregular)
        "train" = train (very regular low-freq vibration)
        "bike"  = two-wheeler (medium vibration)

    pocket — detected via onboarding or user toggle:
        "hand"    = held in hand (most accurate, default)
        "front"   = front trouser pocket
        "back"    = back trouser pocket (highest noise)
        "handbag" = inside bag (dampened signal)
    """
    if vehicle is not None:
        _context["vehicle"] = vehicle
    if pocket is not None:
        _context["pocket"] = pocket
    logger.debug(f"Context updated: {_context}")


# ── Vehicle baseline profiles ─────────────────────────────────────────────────
# Variance and direction-change baselines observed per vehicle type.
# !! THESE ARE ESTIMATES — measure real values on Indian roads before V2 !!
# Collect: 5 min of bus/auto/train/bike recordings, compute mean variance.
#
# Format: (variance_baseline, direction_change_baseline)

_VEHICLE_BASELINES = {
    "none":  (0.0,  0.0),     # on foot — no subtraction
    "bus":   (30.0, 2.5),     # regular but high vibration
    "auto":  (45.0, 4.0),     # auto-rickshaw — irregular, high
    "train": (15.0, 1.0),     # smooth but constant low vibration
    "bike":  (25.0, 2.0),     # medium vibration, speed-dependent
}

# !! TUNE THESE on a Rs.6,000 Redmi/Realme — not a flagship !!
_VEHICLE_SUPPRESSION_BONUS = {
    "none":  0,
    "bus":   15,   # add to score threshold needed to fire — harder to trigger in bus
    "auto":  20,   # highest suppression — auto vibration looks very panic-like
    "train": 10,
    "bike":  12,
}


# ── Pocket position scaling ───────────────────────────────────────────────────
# Phone in a back pocket or handbag sees dampened or rotated signals.
# Scale raw features UP to compensate for signal loss.
#
# !! MEASURE real dampening factors before V2 — these are starting estimates !!

_POCKET_SCALE = {
    "hand":    1.0,    # baseline — no scaling
    "front":   1.1,    # slight dampening from fabric
    "back":    1.3,    # more dampening + body movement noise
    "handbag": 1.5,    # most dampened — scale up most aggressively
}


# ── Fall detection thresholds ─────────────────────────────────────────────────
# A fall has three phases:
#   1. Free-fall  — magnitude drops close to 0 (weightlessness)
#   2. Impact     — sudden large magnitude spike (hitting ground)
#   3. Stillness  — near-zero movement after impact (person on ground)
#
# !! CALIBRATE with real drop tests on different floor surfaces !!
# Hard floor impact is higher magnitude than carpet/soil.

FALL_FREEFALL_THRESHOLD  = 3.0     # m/s² — below this = free-fall phase
FALL_IMPACT_THRESHOLD    = 30.0    # m/s² — above this = impact
FALL_STILLNESS_THRESHOLD = 2.0     # variance — below this after impact = stillness
FALL_STILLNESS_WINDOW    = 10      # samples to check stillness after impact (1 sec)


# ── Main inference ─────────────────────────────────────────────────────────────

def predict_panic_movement(accelerometer_data: list) -> float:
    """
    Detect panic movement from 3-second accelerometer window.

    Args:
        accelerometer_data: list of (x, y, z) tuples at 10Hz — 30 samples ideal.
                           Minimum 10 samples accepted.

    Returns:
        Confidence score 0.0–100.0.
        confidence_scorer.py uses tiered thresholds on this value:
            < 60  → 0 pts
            60–74 → 20 pts
            75–89 → 30 pts
            ≥ 90  → 40 pts
    """
    if len(accelerometer_data) < 10:
        return 0.0

    try:
        data = np.array(accelerometer_data, dtype=np.float32)  # (N, 3)

        # Step 1: pocket position scaling
        # Compensates for signal dampening when phone is in bag/pocket.
        pocket_scale = _POCKET_SCALE.get(_context["pocket"], 1.0)
        data = data * pocket_scale

        # Step 2: jogging suppression
        # Jogging = high variance + rhythmic. Without this it scores ~70 (false alert).
        # Returns 15 (not 0) so audio can still push combined score over threshold.
        if _is_jogging(data):
            logger.debug("Jogging detected — score suppressed to 15")
            return 15.0

        # Step 3: extract features
        magnitudes        = np.sqrt(np.sum(data ** 2, axis=1))
        variance          = float(np.var(magnitudes))
        diffs             = np.diff(data, axis=0)
        direction_changes = float(np.mean(np.abs(diffs)))
        peak              = float(np.max(magnitudes))

        # Step 4: vehicle baseline subtraction
        # Remove the vehicle's constant vibration signal before scoring.
        v_baseline, d_baseline = _VEHICLE_BASELINES.get(_context["vehicle"], (0.0, 0.0))
        variance          = max(variance - v_baseline, 0.0)
        direction_changes = max(direction_changes - d_baseline, 0.0)

        # Step 5: soft scoring (continuous, not step thresholds)
        # Each feature contributes proportionally up to its cap.
        # Saturates at panic-level values observed in test recordings.
        #
        # Variance: 0–35 pts. Saturates at 200 (strong panic signal).
        variance_score    = min(variance / 200.0, 1.0) * 35.0

        # Direction changes: 0–30 pts. Saturates at mean_abs_diff = 10.
        direction_score   = min(direction_changes / 10.0, 1.0) * 30.0

        # Peak magnitude: 0–20 pts. Saturates at peak = 40.
        peak_score        = min(peak / 40.0, 1.0) * 20.0

        # High-variance bonus: 0–15 pts extra when variance > 150 (very clear panic).
        high_var_bonus    = min(max(variance - 150.0, 0.0) / 100.0, 1.0) * 15.0

        score = variance_score + direction_score + peak_score + high_var_bonus

        # Step 6: vehicle suppression penalty
        # In a vehicle, require higher raw score before treating it as panic.
        # This is a score reduction, not a threshold raise — keeps the math simple.
        vehicle_penalty = _VEHICLE_SUPPRESSION_BONUS.get(_context["vehicle"], 0)
        score = max(score - vehicle_penalty, 0.0)

        return float(min(score, 100.0))

    except Exception as e:
        logger.error(f"Movement inference error: {e}")
        return 0.0


# ── Fall detection ────────────────────────────────────────────────────────────

def detect_fall(accelerometer_data: list) -> dict:
    """
    Detect a sudden fall (free-fall → impact → stillness).

    Returns a dict, not a plain bool, because the caller needs to know
    whether the fall is confirmed or just suspected — they require different
    responses.

    Return values:
        {"detected": False}
            No fall pattern found.

        {"detected": True, "confirmed": False, "reason": "phone_drop_possible"}
            Fall pattern found, but no second signal yet.
            → Escalate to confirm_30s (vibrate, wait for user response).
            → Start 30s no-response timer.
            → Do NOT fire SOS yet.

        {"detected": True, "confirmed": True, "reason": str}
            Fall confirmed by a second signal (audio distress OR no response).
            → Fire immediately.

    Why not a plain bool:
        A phone slipping from a hand and hitting the floor matches the
        fall pattern perfectly: free-fall → impact → stillness.
        Without a second signal, firing SOS for every dropped phone
        would destroy user trust in the first week.

    Second signal options (caller provides — this function only detects motion):
        audio_score >= 60   → distress audio during/after the fall
        no_response = True  → 30s passed with no user cancel on the vibration

    Usage in your sensor fusion loop:
        fall = detect_fall(accel_data)
        if fall["detected"] and not fall["confirmed"]:
            # Start confirmation: vibrate + 30s timer
            start_fall_confirmation_timer(
                on_timeout  = lambda: fire_sos("fall_no_response"),
                on_audio    = lambda score: score >= 60,
                on_cancel   = cancel_alert,
            )
        elif fall["confirmed"]:
            fire_sos(fall["reason"])

    !! VALIDATE thresholds with real drop tests before V2 !!
    Test surfaces: concrete, soil, bus floor, stairs.
    Test positions: hand-held, front pocket, handbag.
    Specifically test: phone-drop-from-hand vs person-falling — measure
    whether post-impact stillness duration separates them reliably.
    """
    if len(accelerometer_data) < 20:
        return {"detected": False}

    try:
        data       = np.array(accelerometer_data, dtype=np.float32)
        magnitudes = np.sqrt(np.sum(data ** 2, axis=1))
        n          = len(magnitudes)

        for i in range(n - FALL_STILLNESS_WINDOW - 2):
            # Phase 1: free-fall — magnitude near zero
            if magnitudes[i] > FALL_FREEFALL_THRESHOLD:
                continue

            # Phase 2: impact — large spike immediately after free-fall
            impact_window = magnitudes[i+1 : i+4]
            if impact_window.max() < FALL_IMPACT_THRESHOLD:
                continue

            # Phase 3: stillness — low variance after impact
            impact_idx      = i + 1 + int(np.argmax(impact_window))
            post_impact_end = min(impact_idx + FALL_STILLNESS_WINDOW, n)
            if post_impact_end <= impact_idx + 2:
                continue

            post_impact = magnitudes[impact_idx + 1 : post_impact_end]
            if np.var(post_impact) < FALL_STILLNESS_THRESHOLD:
                logger.warning(
                    f"Fall pattern detected (unconfirmed): freefall@{i}, "
                    f"impact={magnitudes[impact_idx]:.1f}, "
                    f"post_var={np.var(post_impact):.2f}"
                )
                # Detected but NOT yet confirmed — needs audio or no-response
                return {
                    "detected":  True,
                    "confirmed": False,
                    "reason":    "fall_pattern_needs_confirmation",
                }

        return {"detected": False}

    except Exception as e:
        logger.error(f"Fall detection error: {e}")
        return {"detected": False}


# ── Jogging detection (internal) ──────────────────────────────────────────────

def _is_jogging(data: np.ndarray) -> bool:
    """
    Detect rhythmic jogging via autocorrelation.
    Jogging = strong periodic signal in magnitude over 2–3 seconds.
    Panic   = erratic, non-periodic bursts.

    Not exposed publicly — called inside predict_panic_movement().
    Accepts pre-computed np.ndarray (already scaled for pocket position).
    """
    if len(data) < 20:
        return False

    try:
        magnitudes   = np.sqrt(np.sum(data ** 2, axis=1))
        mag_centered = magnitudes - magnitudes.mean()
        autocorr     = np.correlate(mag_centered, mag_centered, mode="full")
        autocorr     = autocorr[len(autocorr) // 2:]

        # Peak ratio > 0.5 = strong periodic pattern = jogging.
        # !! TEST: measure false-negative rate (missed panic) at peak_ratio 0.4–0.6 !!
        # If real panic is sometimes caught by jogging suppression, lower to 0.4.
        peak_ratio = autocorr[1:10].max() / (autocorr[0] + 1e-6)
        return bool(peak_ratio > 0.5)

    except Exception:
        return False


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    rng = np.random.default_rng(42)

    print("\n── Jogging (rhythmic) ──")
    t = np.linspace(0, 3, 30)
    jogging = [(2*np.sin(2*np.pi*2*ti), 0.5*np.sin(2*np.pi*2*ti), 9.8) for ti in t]
    print(f"  score: {predict_panic_movement(jogging):.1f}  (expect ~15 — suppressed)")

    print("\n── Panic (erratic) ──")
    panic = [(rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(-20, 20))
             for _ in range(30)]
    print(f"  score: {predict_panic_movement(panic):.1f}  (expect 60+)")

    print("\n── Fall ──")
    fall = (
        [(0.1, 0.1, 0.2)] * 3 +           # free-fall (near-zero magnitude)
        [(15.0, 25.0, 20.0)] * 2 +         # impact
        [(0.3, 0.2, 0.1)] * 15             # stillness
    )
    result = detect_fall(fall)
    print(f"  detected:  {result['detected']}   (expect True)")
    print(f"  confirmed: {result.get('confirmed')}  (expect False — needs audio or no-response)")

    print("\n── Bus context ──")
    set_context(vehicle="bus", pocket="handbag")
    bus_vibration = [(rng.uniform(-8, 8), rng.uniform(-8, 8), 9.8 + rng.uniform(-3, 3))
                     for _ in range(30)]
    print(f"  score: {predict_panic_movement(bus_vibration):.1f}  (expect lower due to suppression)")
    set_context(vehicle="none", pocket="hand")
