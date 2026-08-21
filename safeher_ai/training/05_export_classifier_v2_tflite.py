import tensorflow as tf
from pathlib import Path

MODEL_PATH = Path("safeher_ai/models/v2/safeher_classifier_v2_best.keras")
OUTPUT_DIR = Path("safeher_ai/models/v2")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("SafeHer — V2 CLASSIFIER-ONLY TFLite EXPORT")
print("=" * 60)

print("\nLoading Keras classifier...")
model = tf.keras.models.load_model(MODEL_PATH)

print("✅ Keras classifier loaded")
print()
model.summary()

print("\nConverting classifier to TFLite...")

converter = tf.lite.TFLiteConverter.from_keras_model(model)

tflite_model = converter.convert()

output_path = OUTPUT_DIR / "safeher_classifier_v2.tflite"
output_path.write_bytes(tflite_model)

size_kb = len(tflite_model) / 1024

print(f"\n✅ Saved: {output_path}")
print(f"Size   : {size_kb:.1f} KB")

print("\nVerifying TFLite model...")

interpreter = tf.lite.Interpreter(model_path=str(output_path))
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

print("Input shape :", input_details[0]["shape"])
print("Input dtype :", input_details[0]["dtype"])
print("Output shape:", output_details[0]["shape"])
print("Output dtype:", output_details[0]["dtype"])

# One deterministic dummy embedding.
dummy = tf.zeros((1, 1024), dtype=tf.float32).numpy()

interpreter.set_tensor(
    input_details[0]["index"],
    dummy
)

interpreter.invoke()

output = interpreter.get_tensor(
    output_details[0]["index"]
)

print("Dummy output:", output)

print("\n" + "=" * 60)
print("✅ CLASSIFIER-ONLY TFLITE EXPORT COMPLETE")
print("=" * 60)
