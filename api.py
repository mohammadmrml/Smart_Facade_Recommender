"""
api.py
------
"""

from flask import Flask, request, jsonify
from predict import predict_facade, predict_batch
from flask_cors import CORS

app = Flask(__name__)

# ✅ FIX 1 — allow all requests (no 403)
CORS(app, resources={r"/*": {"origins": "*"}})


# ── Health check ─────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# ── Single prediction ────────────────────────────────────
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json(force=True)   # ✅ FIX 2

        if not data:
            return jsonify({"error": "No JSON body received"}), 400

        required = ["WWR", "Orientation", "Geometry", "Panel_Size", "Porosity", "Rotation"]
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({"error": f"Missing required fields: {missing}"}), 400

        result = predict_facade(
            WWR=float(data["WWR"]),
            Orientation=str(data["Orientation"]),
            Geometry=str(data["Geometry"]),
            Panel_Size=int(data["Panel_Size"]),
            Porosity=float(data["Porosity"]),
            Rotation=int(data["Rotation"]),
            Glass_VLT=data.get("Glass_VLT"),
            Glass_SHGC=data.get("Glass_SHGC"),
            Glass_U=data.get("Glass_U"),
        )

        return jsonify(result), 200   # ✅ FIX 3

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Batch prediction ─────────────────────────────────────
@app.route("/predict_batch", methods=["POST"])
def predict_batch_route():
    try:
        data = request.get_json(force=True)   # ✅ FIX 4

        if not data or "floors" not in data:
            return jsonify({"error": "Expected JSON with 'floors' list"}), 400

        results = predict_batch(data["floors"])
        return jsonify({"results": results}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Run ──────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)  