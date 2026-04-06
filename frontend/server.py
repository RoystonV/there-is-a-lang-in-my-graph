# =============================================================================
# server.py — Flask API + static file server for TARA visualizer
# =============================================================================
# Run: python server.py
# Then open: http://localhost:5000
# =============================================================================

import os
import sys
import json
from pathlib import Path

# Make sure db.py (in parent Langraph_rag_fucytech) is importable
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from flask import Flask, jsonify, send_from_directory, abort, request
    from flask_cors import CORS
except ImportError:
    print("❌ Flask not installed. Run: pip install flask flask-cors pymongo")
    sys.exit(1)

import db as mongo_db

app = Flask(__name__, static_folder=str(Path(__file__).parent), static_url_path="")
CORS(app)

ECU_PATH = ROOT / "datasets" / "dataecu.json"


# ── Static files ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(Path(__file__).parent), "index.html")


# ── Health / status ───────────────────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    connected = mongo_db.is_connected()
    return jsonify({
        "mongo_connected": connected,
        "mongo_uri": mongo_db.MONGO_URI,
        "db_name": mongo_db.DB_NAME,
        "collection": mongo_db.COLLECTION,
    })


# ── Reports list ──────────────────────────────────────────────────────────────

@app.route("/api/reports")
def api_reports():
    reports = mongo_db.list_reports(limit=200)
    return jsonify(reports)


# ── Single report ─────────────────────────────────────────────────────────────

@app.route("/api/report/<report_id>")
def api_report(report_id):
    doc = mongo_db.get_report(report_id)
    if doc is None:
        abort(404, description=f"Report {report_id} not found")
    return jsonify(doc)


# ── Delete report ─────────────────────────────────────────────────────────────

@app.route("/api/report/<report_id>", methods=["DELETE"])
def api_delete_report(report_id):
    success = mongo_db.delete_report(report_id)
    return jsonify({"deleted": success})


# ── ECU list ──────────────────────────────────────────────────────────────────

@app.route("/api/ecus")
def api_ecus():
    try:
        with open(ECU_PATH, encoding="utf-8") as f:
            data = json.load(f)
        ecus = [
            {"key": k, "name": v.get("name", k), "type": v.get("type", "")}
            for k, v in data.items()
        ]
        return jsonify(ecus)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "=" * 55)
    print("  TARA RAG Visualizer  |  Flask API Server")
    print("=" * 55)
    print(f"  URL    : http://localhost:{port}")
    print(f"  Mongo  : {mongo_db.MONGO_URI}")
    print(f"  DB     : {mongo_db.DB_NAME}.{mongo_db.COLLECTION}")
    print("=" * 55 + "\n")

    connected = mongo_db.is_connected()
    if connected:
        print("  🍃 MongoDB connection: ✅ OK")
        reports = mongo_db.list_reports(limit=1)
        if not reports:
            print("  ⚠️  No reports in MongoDB yet.")
            print(f"     Run seed: python seed_mongo.py  (from {Path(__file__).parent})")
    else:
        print("  ⚠️  MongoDB not reachable. Start MongoDB first.")
        print("      Reports list will be empty until connection is established.")

    print("\n  Press Ctrl+C to stop.\n")
    app.run(host="0.0.0.0", port=port, debug=False)
