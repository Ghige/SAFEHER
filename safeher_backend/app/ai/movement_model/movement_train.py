"""
SafeHer — Movement Model Training V3

V2 (movement_train.py, superseded) extracted 22 hand-crafted stats per
window and fed them into a Dense classifier over 4 classes
(normal / panic / fall / vehicle). Two problems with that:

  1. Hand-crafted features throw away temporal shape. "Fight" and
     "dragging" don't look like a single number for variance/skew/etc —
     they look like a SEQUENCE (short violent bursts vs. a slow, rhythmic
     drag). A feature vector can't represent that; a sequence model can.
  2. "Panic" as a single class conflates several very different threats
     (a fight, a struggle-drag, a phone being snatched) that call for
     different responses downstream.

V3 changes:
  - Input is the RAW (30, 3) accelerometer window, not hand-crafted stats.
  - Model is Conv1D (local motion patterns) -> BiLSTM (temporal dynamics)
    -> Dense softmax. This is standard for wearable/IMU activity
    recognition (see e.g. the UCI-HAR / WISDM literature).
  - 7 classes replace the old 4, splitting "panic" into named threats:
        0 = walking           (benign)
        1 = running           (benign — includes jogging)
        2 = vehicle           (benign — bus/auto/train/bike vibration)
        3 = fight              (threat)
        4 = dragging           (threat — being pulled/dragged)
        5 = falling            (threat — sudden fall)
        6 = phone_snatching    (threat — sharp grab-and-run motion)
  - Augmentation (rotation, scaling, Gaussian noise, time-warp) is applied
    per-class, weighted more heavily toward threat classes, since those
    will always be the hardest and most expensive to collect real data for.

Usage:
    python movement_train.py --data_dir ./data --epochs 60 --output movement_v3.h5

Data directory structure:
    data/
    ├── walking/          ← walking, standing, sitting CSVs
    ├── running/          ← running, jogging CSVs
    ├── vehicle/          ← bus, auto-rickshaw, train, bike CSVs
    ├── fight/            ← struggle / physical altercation CSVs
    ├── dragging/         ← being pulled or dragged CSVs
    ├── falling/          ← fall recordings (free-fall + impact + stillness)
    └── phone_snatching/  ← sudden grab-and-run motion CSVs

Each CSV: columns timestamp, x, y, z (accelerometer at 10Hz).
Pocket position label is encoded in the filename (same convention as V2):
    walk_front_01.csv    → front pocket
    fight_hand_03.csv    → hand-held
    Supported tags: _hand_ _front_ _back_ _handbag_. Untagged = hand-held.

Output:
    movement_v3.h5         — Keras model
    movement_v3.tflite     — on-device model (see export notes below)
    movement_scaler.pkl    — per-channel StandardScaler (must ship with model)

Model output:
    7-class softmax → [walking, running, vehicle, fight, dragging,
                        falling, phone_snatching]
    movement_inference.py combines fight/dragging/phone_snatching into a
    single threat score, and reads falling separately (needs confirmation
    before firing, same as V2's fall handling).
"""

import argparse
import os
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight
import joblib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Settings ──────────────────────────────────────────────────────────────────

WINDOW_SIZE = 30       # 3 seconds at 10Hz — must match movement_inference.py
STEP_SIZE   = 10       # 1 second step — overlapping windows increase dataset size
N_CHANNELS  = 3        # x, y, z

CLASSES = {
    0: "walking",
    1: "running",
    2: "vehicle",
    3: "fight",
    4: "dragging",
    5: "falling",
    6: "phone_snatching",
}
CLASSES_INV = {v: k for k, v in CLASSES.items()}

THREAT_CLASSES = {"fight", "dragging", "phone_snatching"}   # combined into panic score
BENIGN_CLASSES = {"walking", "running", "vehicle"}

# Pocket position scaling — same values used across the SafeHer codebase.
POCKET_SCALE = {
    "hand":    1.0,
    "front":   1.1,
    "back":    1.3,
    "handbag": 1.5,
}

# How many augmented copies to generate per real window, per class.
# Threat classes get far more augmentation because real recordings of
# fights/dragging/phone-snatching will always be scarce and hard to collect
# safely, while walking/running/vehicle data is comparatively easy to gather.
#
# !! REVIEW after your first real data collection round — these are
#    starting multipliers, not tuned values. !!
AUGMENT_MULTIPLIER = {
    "walking":         1,   # real data plentiful — little augmentation needed
    "running":         1,
    "vehicle":         2,   # some augmentation helps cover more vehicle types
    "fight":           6,
    "dragging":        6,
    "falling":         6,
    "phone_snatching": 6,
}


# ── Augmentation ──────────────────────────────────────────────────────────────
# All augmentations operate on a (WINDOW_SIZE, 3) raw window and return a
# window of the same shape. Applied to TRAIN windows only — never to val
# windows, or validation accuracy stops meaning "real generalisation".

def _augment_rotation(window: np.ndarray, max_angle_deg: float = 20.0) -> np.ndarray:
    """
    Rotate the (x, y, z) vectors by a small random 3D rotation.

    Simulates the phone being held/carried at a slightly different angle
    each time — the model should recognise "fight" regardless of exact
    phone orientation, not memorise one fixed axis alignment.
    """
    angles = np.radians(np.random.uniform(-max_angle_deg, max_angle_deg, size=3))
    cx, cy, cz = np.cos(angles)
    sx, sy, sz = np.sin(angles)

    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    R = Rz @ Ry @ Rx

    return (window @ R.T).astype(np.float32)


def _augment_scale(window: np.ndarray, scale_range=(0.85, 1.15)) -> np.ndarray:
    """
    Multiply the whole window by a random scalar.

    Simulates sensor gain variation across different phone models and
    slightly different force/intensity between real events of the same type.
    """
    scale = np.random.uniform(*scale_range)
    return (window * scale).astype(np.float32)


def _augment_noise(window: np.ndarray, noise_std: float = 0.4) -> np.ndarray:
    """
    Add Gaussian sensor noise.

    Real accelerometers are noisier than clean recordings, especially on
    low-end devices — this narrows the train/deployment distribution gap.
    """
    noise = np.random.normal(0, noise_std, size=window.shape)
    return (window + noise).astype(np.float32)


def _augment_time_warp(window: np.ndarray, sigma: float = 0.2) -> np.ndarray:
    """
    Stretch/compress the time axis with a smooth random warp, then
    resample back to WINDOW_SIZE samples.

    Simulates the same event happening slightly faster or slower — a
    fight or a fall doesn't unfold at exactly the same speed every time.
    """
    n = len(window)
    # Smooth random warp curve: cumulative sum of random steps, normalised
    # back to the original time range [0, n-1].
    steps = np.random.normal(1.0, sigma, size=n)
    steps = np.clip(steps, 0.1, None)
    warped_time = np.cumsum(steps)
    warped_time = (warped_time - warped_time.min()) / (warped_time.max() - warped_time.min()) * (n - 1)

    original_time = np.arange(n)
    out = np.zeros_like(window)
    for ch in range(window.shape[1]):
        out[:, ch] = np.interp(original_time, warped_time, window[:, ch])
    return out.astype(np.float32)


def augment_window(window: np.ndarray) -> np.ndarray:
    """
    Apply a random combination of the four augmentations above.
    Each is applied independently with 50% probability, except at least
    one is guaranteed so augmented copies always differ from the original.
    """
    augmentations = [_augment_rotation, _augment_scale, _augment_noise, _augment_time_warp]
    applied = [f for f in augmentations if np.random.random() < 0.5]
    if not applied:
        applied = [np.random.choice(augmentations)]

    out = window.copy()
    for fn in applied:
        out = fn(out)
    return out


# ── Data loading ──────────────────────────────────────────────────────────────

def _pocket_from_filename(fname: str) -> str:
    """Infer pocket position from filename tag. Default = hand."""
    fname = fname.lower()
    for tag in ["handbag", "front", "back", "hand"]:
        if f"_{tag}_" in fname or fname.endswith(f"_{tag}.csv"):
            return tag
    return "hand"


def load_csv_file(path: str) -> np.ndarray:
    """Load accelerometer CSV — expects columns x, y, z (timestamp optional)."""
    df = pd.read_csv(path)
    for col_set in [["x", "y", "z"], ["X", "Y", "Z"], ["acc_x", "acc_y", "acc_z"]]:
        if all(c in df.columns for c in col_set):
            return df[col_set].values.astype(np.float32)
    raise ValueError(f"Could not find x,y,z columns in {path}")


def sliding_windows(data: np.ndarray, window_size: int, step: int):
    for i in range(0, len(data) - window_size, step):
        yield data[i : i + window_size]


def load_dataset(data_dir: str, val_split: float = 0.2):
    """
    Load all CSV files from data/{walking,running,vehicle,fight,dragging,
    falling,phone_snatching}/.

    File-level train/val split (same rationale as V2): split the FILE LIST
    first, THEN window each half separately, so no validation window shares
    samples with a training window from the same recording.

    Augmentation is applied AFTER the split, to train windows only.

    Returns:
        X_train, X_val: np.ndarray, shape (n, WINDOW_SIZE, 3) — raw windows
        y_train, y_val: np.ndarray, shape (n,) — integer class labels
    """
    rng = np.random.default_rng(42)

    files_by_class: dict = {label: [] for label in CLASSES}
    for label, class_name in CLASSES.items():
        class_dir = os.path.join(data_dir, class_name)
        if not os.path.exists(class_dir):
            logger.warning(f"Missing directory: {class_dir} — skipping class '{class_name}'")
            continue
        for root, _, files in os.walk(class_dir):
            files_by_class[label].extend(
                os.path.join(root, f) for f in files if f.endswith(".csv")
            )

    X_train, y_train = [], []
    X_val,   y_val   = [], []

    for label, fpaths in files_by_class.items():
        if not fpaths:
            continue

        class_name = CLASSES[label]
        fpaths = list(rng.permutation(fpaths))
        n_val  = max(1, int(len(fpaths) * val_split))
        val_files   = fpaths[:n_val]
        train_files = fpaths[n_val:]

        logger.info(f"  {class_name:16s}: {len(train_files)} train files, {len(val_files)} val files")

        # ── Validation windows: no augmentation ──
        for fpath in val_files:
            try:
                pocket = _pocket_from_filename(os.path.basename(fpath))
                scale  = POCKET_SCALE.get(pocket, 1.0)
                data   = load_csv_file(fpath) * scale
                for window in sliding_windows(data, WINDOW_SIZE, STEP_SIZE):
                    if len(window) == WINDOW_SIZE:
                        X_val.append(window)
                        y_val.append(label)
            except Exception as e:
                logger.warning(f"Failed to load {fpath}: {e}")

        # ── Training windows: original + augmented copies ──
        multiplier = AUGMENT_MULTIPLIER.get(class_name, 1)
        for fpath in train_files:
            try:
                pocket = _pocket_from_filename(os.path.basename(fpath))
                scale  = POCKET_SCALE.get(pocket, 1.0)
                data   = load_csv_file(fpath) * scale
                for window in sliding_windows(data, WINDOW_SIZE, STEP_SIZE):
                    if len(window) != WINDOW_SIZE:
                        continue
                    X_train.append(window)
                    y_train.append(label)
                    for _ in range(multiplier - 1):
                        X_train.append(augment_window(window))
                        y_train.append(label)
            except Exception as e:
                logger.warning(f"Failed to load {fpath}: {e}")

    if len(X_train) == 0:
        empty = np.zeros((0, WINDOW_SIZE, N_CHANNELS), dtype=np.float32)
        return empty, empty, np.array([], dtype=np.int32), np.array([], dtype=np.int32)

    return (
        np.array(X_train, dtype=np.float32), np.array(X_val, dtype=np.float32),
        np.array(y_train, dtype=np.int32),   np.array(y_val,  dtype=np.int32),
    )


# ── Model ─────────────────────────────────────────────────────────────────────

def build_model(window_size: int = WINDOW_SIZE, n_channels: int = N_CHANNELS,
                 n_classes: int = len(CLASSES)) -> tf.keras.Model:
    """
    1D CNN + BiLSTM classifier over raw accelerometer windows.

    Conv1D layers learn local motion signatures (a sharp jerk, a rhythmic
    step) directly from the waveform. The BiLSTM on top learns how those
    local patterns evolve over the full 3-second window in both directions
    — useful because e.g. "dragging" is defined by a sustained pattern,
    while "phone_snatching" is a brief event that can occur anywhere in
    the window.

    NOTE ON TFLITE EXPORT: standard (unidirectional) LSTM converts cleanly
    to TFLite's fused UnidirectionalSequenceLSTM op. Bidirectional LSTM
    does not always have an equivalent fused op and may require allowing
    SELECT_TF_OPS during conversion (see the export step in train()) or,
    if that proves unreliable on your target devices, dropping to a plain
    (unidirectional) LSTM — try Bidirectional first since accuracy is
    usually meaningfully better, and fall back only if on-device
    conversion or latency becomes a real blocker.
    """
    inputs = tf.keras.Input(shape=(window_size, n_channels), name="accel_window")

    x = tf.keras.layers.Conv1D(64, kernel_size=5, padding="same", activation="relu")(inputs)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Conv1D(128, kernel_size=3, padding="same", activation="relu")(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Dropout(0.3)(x)

    x = tf.keras.layers.Bidirectional(
        tf.keras.layers.LSTM(64, return_sequences=False)
    )(x)

    x = tf.keras.layers.Dense(64, activation="relu")(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    outputs = tf.keras.layers.Dense(n_classes, activation="softmax", name="movement_output")(x)

    model = tf.keras.Model(inputs=inputs, outputs=outputs, name="movement_classifier_v3")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


# ── Training ──────────────────────────────────────────────────────────────────

def train(data_dir: str, epochs: int = 60, output_path: str = "movement_v3.h5"):
    logger.info("Loading dataset (file-level split, train-only augmentation)...")
    X_train, X_val, y_train, y_val = load_dataset(data_dir)

    if len(X_train) == 0:
        logger.error(
            "No data found!\nAdd CSV files to:\n"
            + "\n".join(f"  data/{name}/" for name in CLASSES.values())
        )
        return

    logger.info("Train windows (post-augmentation):")
    for label, name in CLASSES.items():
        logger.info(f"  {name:16s}: {int(np.sum(y_train == label)):6d} train  "
                    f"{int(np.sum(y_val == label)):5d} val")

    # ── Per-channel standardisation ──
    # Fit on TRAIN only (post-augmentation), flatten (n, window, 3) -> (n*window, 3)
    # so all three axes share one scaler fit across the whole time series.
    scaler = StandardScaler()
    n_train = X_train.shape[0]
    X_train_flat = scaler.fit_transform(X_train.reshape(-1, N_CHANNELS))
    X_train = X_train_flat.reshape(n_train, WINDOW_SIZE, N_CHANNELS)

    n_val = X_val.shape[0]
    X_val_flat = scaler.transform(X_val.reshape(-1, N_CHANNELS))
    X_val = X_val_flat.reshape(n_val, WINDOW_SIZE, N_CHANNELS)

    joblib.dump(scaler, "movement_scaler.pkl")
    logger.info("Scaler saved → movement_scaler.pkl")

    # ── Class weights ──
    # Auto-computed from distribution, with a hard floor on threat classes
    # so a lucky class balance doesn't under-weight the events that matter most.
    raw_weights = compute_class_weight("balanced", classes=np.unique(y_train), y=y_train)
    class_weight = dict(enumerate(raw_weights))
    for threat_name in THREAT_CLASSES:
        idx = CLASSES_INV[threat_name]
        class_weight[idx] = max(class_weight.get(idx, 1.0), 2.5)
    class_weight[CLASSES_INV["falling"]] = max(class_weight.get(CLASSES_INV["falling"], 1.0), 3.0)
    logger.info(f"Class weights: {class_weight}")

    model = build_model()
    model.summary(print_fn=logger.info)

    callbacks = [
        tf.keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True, monitor="val_accuracy"),
        tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=5, min_lr=1e-5),
        tf.keras.callbacks.ModelCheckpoint(output_path, save_best_only=True, monitor="val_accuracy"),
    ]

    logger.info(f"Training for up to {epochs} epochs...")
    model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=32,
        callbacks=callbacks,
        class_weight=class_weight,
    )

    model.save(output_path)
    logger.info(f"Keras model saved → {output_path}")

    # ── TFLite export ──
    # Try the straightforward conversion first; Bidirectional LSTM can need
    # SELECT_TF_OPS. Fall back progressively rather than failing outright.
    tflite_path = output_path.replace(".h5", ".tflite")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]

    try:
        tflite_model = converter.convert()
        logger.info("TFLite conversion succeeded with default ops.")
    except Exception as e:
        logger.warning(f"Default TFLite conversion failed ({e}); retrying with SELECT_TF_OPS...")
        converter.target_spec.supported_ops = [
            tf.lite.OpsSet.TFLITE_BUILTINS,
            tf.lite.OpsSet.SELECT_TF_OPS,
        ]
        tflite_model = converter.convert()
        logger.info("TFLite conversion succeeded with SELECT_TF_OPS fallback.")

    with open(tflite_path, "wb") as f:
        f.write(tflite_model)
    logger.info(f"TFLite model saved → {tflite_path}")

    # ── Per-class report ──
    val_loss, val_acc = model.evaluate(X_val, y_val, verbose=0)
    logger.info(f"Overall validation accuracy: {val_acc:.2%}")

    y_pred = np.argmax(model.predict(X_val, verbose=0), axis=1)
    for label, name in CLASSES.items():
        mask = y_val == label
        if mask.sum() == 0:
            continue
        cls_acc = np.mean(y_pred[mask] == label)
        fn_rate = np.mean(y_pred[mask] != label)
        tag = " (THREAT)" if name in THREAT_CLASSES or name == "falling" else ""
        logger.info(f"  {name:16s}  acc={cls_acc:.2%}  false-negative={fn_rate:.2%}{tag}")

    logger.info(
        "\nShip checklist:\n"
        "  [ ] movement_v3.tflite\n"
        "  [ ] movement_scaler.pkl\n"
        "  [ ] Validate on a Redmi/Realme device (not a flagship) — check\n"
        "      inference latency, since BiLSTM is heavier than the old Dense head\n"
        "  [ ] Confirm TFLite conversion didn't silently fall back to SELECT_TF_OPS\n"
        "      in a way that breaks on-device execution — test the .tflite file\n"
        "      directly on a phone, not just in this script\n"
        "  [ ] Re-tune AUGMENT_MULTIPLIER once you see real per-class false-negative rates\n"
        "  [ ] Test all four pocket positions for each threat class, not just walking/running\n"
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train SafeHer movement model V3 (CNN+BiLSTM, 7-class)")
    parser.add_argument("--data_dir", default="./data",          help="Root data directory")
    parser.add_argument("--epochs",   default=60,   type=int,    help="Max training epochs")
    parser.add_argument("--output",   default="movement_v3.h5",  help="Output model path")
    args = parser.parse_args()

    train(args.data_dir, args.epochs, args.output)