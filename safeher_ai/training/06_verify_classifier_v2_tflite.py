import numpy as np
import tensorflow as tf
from pathlib import Path

KERAS_PATH = Path(
    "safeher_ai/models/v2/safeher_classifier_v2_best.keras"
)

TFLITE_PATH = Path(
    "safeher_ai/models/v2/safeher_classifier_v2.tflite"
)

TEST_PATH = Path(
    "safeher_ai/data/embeddings_v2/test.npz"
)

THRESHOLD = 0.40

print("=" * 70)
print("SAFEHER — KERAS vs TFLITE EQUIVALENCE TEST")
print("=" * 70)

# ------------------------------------------------------------
# Load untouched test embeddings
# ------------------------------------------------------------

print("\nLoading test embeddings...")

data = np.load(TEST_PATH)
X = data["X"].astype(np.float32)
y = data["y"].astype(np.int32)

print("X shape:", X.shape)
print("y shape:", y.shape)

# ------------------------------------------------------------
# Keras predictions
# ------------------------------------------------------------

print("\nLoading Keras model...")

keras_model = tf.keras.models.load_model(KERAS_PATH)

print("Generating Keras probabilities...")

keras_probs = keras_model.predict(
    X,
    batch_size=512,
    verbose=0
).reshape(-1)

# ------------------------------------------------------------
# TFLite predictions
# ------------------------------------------------------------

print("\nLoading TFLite model...")

interpreter = tf.lite.Interpreter(
    model_path=str(TFLITE_PATH)
)

interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

print("TFLite input shape :", input_details[0]["shape"])
print("TFLite input dtype :", input_details[0]["dtype"])
print("TFLite output shape:", output_details[0]["shape"])
print("TFLite output dtype:", output_details[0]["dtype"])

input_index = input_details[0]["index"]
output_index = output_details[0]["index"]

tflite_probs = np.empty(len(X), dtype=np.float32)

print("\nGenerating TFLite probabilities...")

for i in range(len(X)):
    sample = X[i:i+1]

    interpreter.set_tensor(
        input_index,
        sample
    )

    interpreter.invoke()

    output = interpreter.get_tensor(
        output_index
    )

    tflite_probs[i] = output.reshape(-1)[0]

# ------------------------------------------------------------
# Probability comparison
# ------------------------------------------------------------

abs_diff = np.abs(
    keras_probs - tflite_probs
)

max_diff = float(np.max(abs_diff))
mean_diff = float(np.mean(abs_diff))
median_diff = float(np.median(abs_diff))

print("\n" + "=" * 70)
print("PROBABILITY DIFFERENCE")
print("=" * 70)

print(f"Maximum absolute difference : {max_diff:.10f}")
print(f"Mean absolute difference    : {mean_diff:.10f}")
print(f"Median absolute difference  : {median_diff:.10f}")

# ------------------------------------------------------------
# Threshold decision comparison
# ------------------------------------------------------------

keras_pred = (
    keras_probs >= THRESHOLD
).astype(np.int32)

tflite_pred = (
    tflite_probs >= THRESHOLD
).astype(np.int32)

decision_mismatches = int(
    np.sum(keras_pred != tflite_pred)
)

agreement = float(
    np.mean(keras_pred == tflite_pred)
)

print("\n" + "=" * 70)
print(f"DECISION COMPARISON @ THRESHOLD {THRESHOLD:.2f}")
print("=" * 70)

print("Samples              :", len(X))
print("Decision mismatches  :", decision_mismatches)
print(f"Decision agreement   : {agreement * 100:.6f}%")

# ------------------------------------------------------------
# Show largest differences
# ------------------------------------------------------------

largest = np.argsort(abs_diff)[-10:][::-1]

print("\n10 largest probability differences:")
print()

for idx in largest:
    print(
        f"Index {idx:5d} | "
        f"Keras={keras_probs[idx]:.8f} | "
        f"TFLite={tflite_probs[idx]:.8f} | "
        f"Diff={abs_diff[idx]:.10f}"
    )

# ------------------------------------------------------------
# Final verdict
# ------------------------------------------------------------

print("\n" + "=" * 70)
print("FINAL VERDICT")
print("=" * 70)

if max_diff < 1e-4 and decision_mismatches == 0:
    print("✅ PASS — TFLite classifier matches Keras classifier.")
elif max_diff < 1e-3 and agreement >= 0.999:
    print("✅ PASS — Tiny numerical differences only.")
    print("TFLite behavior is effectively equivalent to Keras.")
else:
    print("⚠️ REVIEW REQUIRED")
    print("Differences are larger than expected.")

print("=" * 70)
