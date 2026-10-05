import os
from pathlib import Path
import numpy as np
import tensorflow as tf
from sklearn.utils.class_weight import compute_class_weight

# ============================================================
# SafeHer — V2 Classifier Training
# Input: 1024-dim YAMNet embeddings
# Output: distress probability
# ============================================================

BASE = Path("safeher_ai")
EMBED_DIR = BASE / "data" / "embeddings_v2"
MODEL_DIR = BASE / "models" / "v2"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_PATH = EMBED_DIR / "train.npz"
VAL_PATH   = EMBED_DIR / "val.npz"

print("=" * 60)
print("SafeHer — V2 Classifier Training")
print("=" * 60)

# ------------------------------------------------------------
# Load data
# ------------------------------------------------------------

train = np.load(TRAIN_PATH)
val = np.load(VAL_PATH)

X_train = train["X"].astype(np.float32)
y_train = train["y"].astype(np.float32)

X_val = val["X"].astype(np.float32)
y_val = val["y"].astype(np.float32)

print("\nDataset:")
print("Train X:", X_train.shape)
print("Train y:", y_train.shape)
print("Val   X:", X_val.shape)
print("Val   y:", y_val.shape)

print("\nTrain labels:")
print("  Distress:", int((y_train == 1).sum()))
print("  Normal  :", int((y_train == 0).sum()))

print("\nVal labels:")
print("  Distress:", int((y_val == 1).sum()))
print("  Normal  :", int((y_val == 0).sum()))

# ------------------------------------------------------------
# Class weights
# ------------------------------------------------------------

classes = np.array([0, 1])
weights = compute_class_weight(
    class_weight="balanced",
    classes=classes,
    y=y_train.astype(int),
)

class_weight = {
    0: float(weights[0]),
    1: float(weights[1]),
}

print("\nClass weights:")
print("  Normal  :", class_weight[0])
print("  Distress:", class_weight[1])

# ------------------------------------------------------------
# Model
# ------------------------------------------------------------

inputs = tf.keras.Input(
    shape=(1024,),
    name="yamnet_embedding"
)

x = tf.keras.layers.Dense(
    256,
    activation="relu",
    name="dense1"
)(inputs)

x = tf.keras.layers.BatchNormalization(name="bn1")(x)
x = tf.keras.layers.Dropout(0.35, name="dropout1")(x)

x = tf.keras.layers.Dense(
    64,
    activation="relu",
    name="dense2"
)(x)

x = tf.keras.layers.BatchNormalization(name="bn2")(x)
x = tf.keras.layers.Dropout(0.25, name="dropout2")(x)

output = tf.keras.layers.Dense(
    1,
    activation="sigmoid",
    name="output"
)(x)

model = tf.keras.Model(
    inputs=inputs,
    outputs=output,
    name="SafeHerV2AudioClassifier"
)

model.compile(
    optimizer=tf.keras.optimizers.Adam(
        learning_rate=1e-3
    ),
    loss=tf.keras.losses.BinaryCrossentropy(),
    metrics=[
        tf.keras.metrics.BinaryAccuracy(name="accuracy"),
        tf.keras.metrics.Precision(name="precision"),
        tf.keras.metrics.Recall(name="recall"),
        tf.keras.metrics.AUC(name="auc"),
    ],
)

print("\nModel:")
model.summary()

# ------------------------------------------------------------
# Callbacks
# ------------------------------------------------------------

best_path = MODEL_DIR / "safeher_classifier_v2_best.keras"

callbacks = [
    tf.keras.callbacks.ModelCheckpoint(
        str(best_path),
        monitor="val_auc",
        mode="max",
        save_best_only=True,
        verbose=1,
    ),

    tf.keras.callbacks.EarlyStopping(
        monitor="val_auc",
        mode="max",
        patience=8,
        restore_best_weights=True,
        verbose=1,
    ),

    tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_auc",
        mode="max",
        factor=0.5,
        patience=3,
        min_lr=1e-6,
        verbose=1,
    ),
]

# ------------------------------------------------------------
# Train
# ------------------------------------------------------------

print("\n" + "=" * 60)
print("STARTING TRAINING")
print("=" * 60)

history = model.fit(
    X_train,
    y_train,
    validation_data=(X_val, y_val),
    epochs=40,
    batch_size=256,
    class_weight=class_weight,
    callbacks=callbacks,
    verbose=1,
)

# ------------------------------------------------------------
# Save final restored model
# ------------------------------------------------------------

final_path = MODEL_DIR / "safeher_classifier_v2_final.keras"
model.save(final_path)

print("\n" + "=" * 60)
print("✅ V2 TRAINING COMPLETE")
print("=" * 60)

print("Best model :", best_path)
print("Final model:", final_path)

print("\nFinal validation metrics:")

results = model.evaluate(
    X_val,
    y_val,
    verbose=0
)

for name, value in zip(model.metrics_names, results):
    print(f"  {name:10s}: {value:.4f}")

print("\n✅ Ready for V2 test evaluation.")
