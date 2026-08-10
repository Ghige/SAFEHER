"""
SafeHer — Step 2: Model Training (Embedding-based)
=====================================================

Fine-tunes a small classifier on top of frozen YAMNet embeddings.

WHY THIS APPROACH (and not YAMNet wired directly into a Keras Functional
model):
    YAMNet's TF-Hub module is built to take ONE 1-D waveform tensor per
    call (arbitrary length in, a variable number of ~0.96s frames out).
    It is not a normal batched Keras layer — feeding it a
    `tf.keras.Input(shape=(16000,))` batch tensor (shape (B, 16000)) does
    not do what GlobalAveragePooling1D / the rest of the model assumes,
    and trying to fine-tune it end-to-end inside that graph is unreliable.

    The pattern Google's own YAMNet transfer-learning guide uses instead:
        1. Run every audio chunk through YAMNet ONCE to get its 1024-dim
           embedding (mean-pooled across frames).
        2. Cache those embeddings to disk (they never change — YAMNet
           stays frozen).
        3. Train an ordinary small Dense classifier on the embeddings.

    This is simpler, trains in minutes instead of hours, sidesteps the
    batching problem entirely, and is what 03_evaluate_model.py and
    04_export_tflite.py in this update now assume.

    One consequence: there is no more "Phase 2: unfreeze YAMNet and
    fine-tune" step. For a dataset this size (hundreds–low thousands of
    samples) fine-tuning YAMNet's backbone risks overfitting anyway —
    training only the head on top of frozen embeddings is the safer and
    recommended choice.

What this produces:
    data/embeddings/train.npz, val.npz   → cached YAMNet embeddings
    models/checkpoints/                  → saved during training
    models/final/                        → best classifier head (.keras)
    logs/training.log                    → full training history

Run AFTER 01_prepare_dataset.py:
    pip install tensorflow tensorflow-hub numpy pandas scikit-learn tqdm
    python 02_train_model.py
"""

import logging
import numpy as np
import pandas as pd
import tensorflow as tf
import tensorflow_hub as hub
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

# ── Config ────────────────────────────────────────────────────────────────────

SAMPLE_RATE   = 16000
CHUNK_SAMPLES = SAMPLE_RATE * 1     # 1 second, must match 01_prepare_dataset.py

TRAIN_CSV = Path("data/splits/train.csv")
VAL_CSV   = Path("data/splits/val.csv")

EMBED_DIR      = Path("data/embeddings")
CHECKPOINT_DIR = Path("models/checkpoints")
FINAL_DIR      = Path("models/final")
LOG_DIR        = Path("logs")

YAMNET_URL = "https://tfhub.dev/google/yamnet/1"
EMBED_DIM  = 1024   # YAMNet embedding size — fixed, do not change

BATCH_SIZE    = 32
EPOCHS        = 50
LEARNING_RATE = 1e-3

# Class weights — distress (1) weighted higher because missing real
# danger is worse than a false alarm
CLASS_WEIGHT = {0: 1.0, 1: 2.0}

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "training.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


# ── YAMNet embedding extraction ────────────────────────────────────────────────

_yamnet_model = None


def get_yamnet():
    """Load YAMNet once and reuse it (downloads/caches on first run)."""
    global _yamnet_model
    if _yamnet_model is None:
        log.info("Loading YAMNet from TF Hub (cached locally after first run)...")
        _yamnet_model = hub.load(YAMNET_URL)
    return _yamnet_model


def load_wav(filepath: str) -> np.ndarray:
    """Load a WAV file → float32 numpy array at 16kHz mono."""
    audio = tf.io.read_file(filepath)
    audio, _ = tf.audio.decode_wav(audio, desired_channels=1)
    audio = tf.squeeze(audio, axis=-1)
    return audio.numpy().astype(np.float32)


def embed_file(yamnet, filepath: str) -> np.ndarray:
    """
    Run one audio chunk through YAMNet and return a single 1024-dim
    embedding (mean-pooled across the frame axis).
    """
    waveform = load_wav(filepath)

    if len(waveform) < CHUNK_SAMPLES:
        waveform = np.pad(waveform, (0, CHUNK_SAMPLES - len(waveform)))
    else:
        waveform = waveform[:CHUNK_SAMPLES]

    # yamnet(waveform) expects a single 1-D tensor — this is the
    # supported call signature, unlike wrapping it as a batched KerasLayer.
    _, embeddings, _ = yamnet(waveform)     # embeddings: (frames, 1024)
    return embeddings.numpy().mean(axis=0)  # → (1024,)


def build_or_load_embeddings(csv_path: Path, cache_name: str):
    """
    Build (or load cached) YAMNet embeddings for every file in a CSV
    manifest. Returns (X, y) numpy arrays.
    """
    cache_path = EMBED_DIR / cache_name

    if cache_path.exists():
        log.info(f"  Loading cached embeddings: {cache_path.name}")
        data = np.load(cache_path)
        return data["X"], data["y"]

    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} not found — run 01_prepare_dataset.py first")

    df = pd.read_csv(csv_path)
    log.info(f"  Embedding {len(df)} files from {csv_path.name} "
              f"(distress: {df['label'].sum()}, normal: {(df['label']==0).sum()})")

    yamnet = get_yamnet()

    X, y = [], []
    for _, row in tqdm(df.iterrows(), total=len(df), desc=f"  {csv_path.stem}"):
        try:
            emb = embed_file(yamnet, row["filepath"])
            X.append(emb)
            y.append(row["label"])
        except Exception as e:
            log.warning(f"  Skipped {row['filepath']}: {e}")

    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.int32)

    EMBED_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(cache_path, X=X, y=y)
    log.info(f"  Cached {len(X)} embeddings → {cache_path}")

    return X, y


# ── Model ─────────────────────────────────────────────────────────────────────

def build_classifier() -> tf.keras.Model:
    """
    Small classifier head trained on top of frozen YAMNet embeddings.

    Architecture:
      Input: YAMNet embedding (1024-dim, already mean-pooled)
        ↓
      Dense 256 → ReLU → Dropout 0.4
        ↓
      Dense 64  → ReLU → Dropout 0.3
        ↓
      Dense 1   → Sigmoid → distress probability [0, 1]

    Output: single float. >0.5 = distress detected.
    Multiply by 100 → confidence score (0-100), as used in inference.py.
    """
    inputs = tf.keras.Input(shape=(EMBED_DIM,), name="yamnet_embedding")
    x = tf.keras.layers.Dense(256, activation="relu", name="dense1")(inputs)
    x = tf.keras.layers.Dropout(0.4, name="dropout1")(x)
    x = tf.keras.layers.Dense(64, activation="relu", name="dense2")(x)
    x = tf.keras.layers.Dropout(0.3, name="dropout2")(x)
    output = tf.keras.layers.Dense(1, activation="sigmoid", name="output")(x)

    return tf.keras.Model(inputs=inputs, outputs=output, name="SafeHerAudioClassifier")


# ── Training ──────────────────────────────────────────────────────────────────

def train():
    log.info("=" * 55)
    log.info("  SafeHer — Model Training (YAMNet embeddings)")
    log.info("=" * 55)

    if not TRAIN_CSV.exists():
        log.error(f"❌ {TRAIN_CSV} not found. Run 01_prepare_dataset.py first.")
        return

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    # ── Step 1: build/load embeddings ──────────────────────────────────────
    log.info("\nStep 1/2: Extracting YAMNet embeddings (cached after first run)...")
    X_train, y_train = build_or_load_embeddings(TRAIN_CSV, "train.npz")
    X_val,   y_val   = build_or_load_embeddings(VAL_CSV,   "val.npz")

    log.info(f"\n  Train embeddings: {X_train.shape}   Val embeddings: {X_val.shape}")

    # ── Step 2: train classifier ───────────────────────────────────────────
    log.info("\nStep 2/2: Training classifier head...")
    model = build_classifier()
    model.compile(
        optimizer=tf.keras.optimizers.Adam(LEARNING_RATE),
        loss=tf.keras.losses.BinaryCrossentropy(),
        metrics=[
            tf.keras.metrics.BinaryAccuracy(name="accuracy"),
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
            tf.keras.metrics.AUC(name="auc"),
        ]
    )
    model.summary(print_fn=log.info)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    callbacks = [
        # Save best model by val recall (catching real distress is priority)
        tf.keras.callbacks.ModelCheckpoint(
            filepath=str(CHECKPOINT_DIR / f"best_{timestamp}.weights.h5"),
            monitor="val_recall",
            mode="max",
            save_best_only=True,
            save_weights_only=True,
            verbose=1
        ),
        # Stop early if no improvement for 8 epochs
        tf.keras.callbacks.EarlyStopping(
            monitor="val_recall",
            patience=8,
            mode="max",
            restore_best_weights=True,
            verbose=1
        ),
        # Reduce LR when stuck
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=4,
            min_lr=1e-6,
            verbose=1
        ),
        # TensorBoard logs
        tf.keras.callbacks.TensorBoard(
            log_dir=str(LOG_DIR / f"tb_{timestamp}"),
            histogram_freq=1
        ),
    ]

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        batch_size=BATCH_SIZE,
        epochs=EPOCHS,
        callbacks=callbacks,
        class_weight=CLASS_WEIGHT,
        verbose=1
    )

    # ── Save final model ──────────────────────────────────────────────────
    final_path = FINAL_DIR / f"safeher_classifier_{timestamp}.keras"
    model.save(str(final_path))
    log.info(f"\n✅ Classifier saved: {final_path}")
    log.info("▶  Next: python 03_evaluate_model.py --model " + str(final_path))

    best_recall = max(history.history["val_recall"])
    best_auc    = max(history.history["val_auc"])

    log.info("\n── Best Results ──────────────────────────────────")
    log.info(f"   Val Recall (catch real distress): {best_recall:.3f}")
    log.info(f"   Val AUC:                          {best_auc:.3f}")
    log.info("──────────────────────────────────────────────────")

    if best_recall < 0.80:
        log.warning("⚠️  Recall below 0.80 — collect more distress samples")
    if best_auc < 0.85:
        log.warning("⚠️  AUC below 0.85 — model needs more training data")

    log.info("\nNote: 04_export_tflite.py combines this classifier with the")
    log.info("YAMNet backbone into a single waveform-in/score-out model for")
    log.info("on-device inference — no separate step needed for that.")


if __name__ == "__main__":
    train()