# =============================================================================
# seed_mongo.py  —  Load existing TARA JSON outputs into MongoDB
# =============================================================================
# Run this once (from rag_front_test/frontend/) to populate the DB with
# the 5 pre-generated reports that already exist in outputs/tara/
# =============================================================================

import sys
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    import db as mongo_db
except ImportError as e:
    print(f"❌ Could not import db.py: {e}")
    sys.exit(1)

TARA_DIR = ROOT / "results"

def infer_ecu_name(filename: str) -> str:
    """Turn tara_output_Battery_Management_System_ECU.json → Battery Management System ECU"""
    name = filename.replace("tara_output_", "").replace(".json", "")
    return name.replace("_", " ")

def main():
    files = list(TARA_DIR.glob("tara_output_*.json"))
    if not files:
        print(f"❌ No tara_output_*.json files found in {TARA_DIR}")
        sys.exit(1)

    print(f"\n🌱 Seeding MongoDB with {len(files)} reports...\n")

    if not mongo_db.is_connected():
        print("❌ Cannot connect to MongoDB. Is mongod running?")
        print(f"   URI: {mongo_db.MONGO_URI}")
        sys.exit(1)

    for fpath in files:
        try:
            with open(fpath, encoding="utf-8") as f:
                tara_json = json.load(f)

            ecu_name  = infer_ecu_name(fpath.name)
            query     = ecu_name

            mongo_id = mongo_db.save_report(tara_json, query_name=query, ecu_name=ecu_name)
            status = "✅" if mongo_id else "⚠️ "
            print(f"  {status} {fpath.name}  →  {ecu_name}")

        except Exception as e:
            print(f"  ❌ {fpath.name}: {e}")

    reports = mongo_db.list_reports()
    print(f"\n🍃 MongoDB now has {len(reports)} reports in tara_db.reports")
    print("\nYou can now run the frontend:\n  cd frontend\n  python server.py\n")

if __name__ == "__main__":
    main()
