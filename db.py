# =============================================================================
# db.py — MongoDB helper for TARA RAG pipeline
# =============================================================================
# Uses MONGO_URI env var (default: mongodb://localhost:27017)
# Database : tara_db
# Collection: reports
# =============================================================================

import os
import copy
from datetime import datetime, timezone

# pymongo is optional — pipeline still works without it (just skips mongo save)
try:
    from pymongo import MongoClient, DESCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    _PYMONGO_AVAILABLE = True
except ImportError:
    _PYMONGO_AVAILABLE = False


MONGO_URI  = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME    = "tara_db"
COLLECTION = "reports"

_client = None  # lazy singleton


def _get_collection():
    global _client
    if not _PYMONGO_AVAILABLE:
        raise RuntimeError("pymongo not installed. Run: pip install pymongo")
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Ping to catch connection errors early
        _client.admin.command("ping")
    return _client[DB_NAME][COLLECTION]


def save_report(tara_json: dict, query_name: str, ecu_name: str = "", full_prompt: str = "", eval_score: int = 0) -> str | None:
    """
    Upsert a TARA report into MongoDB.
    Adds metadata fields: _query, _ecu_name, _saved_at, _full_prompt, _eval_score.
    Uses the assets._id as the upsert key (so re-running the same query
    overwrites the existing document instead of duplicating).

    Returns the MongoDB document _id as a string, or None on failure.
    """
    try:
        col = _get_collection()

        doc = copy.deepcopy(tara_json)

        # Metadata envelope
        doc["_query"]       = query_name
        doc["_ecu_name"]    = ecu_name or query_name
        doc["_saved_at"]    = datetime.now(timezone.utc).isoformat()
        doc["_full_prompt"] = full_prompt
        doc["_eval_score"]  = eval_score

        # Derive a stable upsert key from the TARA assets._id  
        report_id = (
            doc.get("assets", {}).get("_id")
            or doc.get("_id")
            or None
        )

        if report_id:
            col.replace_one({"assets._id": report_id}, doc, upsert=True)
            print(f"  🍃 MongoDB: upserted report  (assets._id={report_id})")
        else:
            result = col.insert_one(doc)
            report_id = str(result.inserted_id)
            print(f"  🍃 MongoDB: inserted report  (_id={report_id})")

        return str(report_id)

    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"  ⚠️  MongoDB not reachable — skipping DB save: {e}")
        return None
    except Exception as e:
        print(f"  ⚠️  MongoDB save failed: {e}")
        return None


def list_reports(limit: int = 100) -> list[dict]:
    """Return summary metadata for all reports (no full template/edges)."""
    try:
        col = _get_collection()
        cursor = col.find(
            {},
            {
                "_id": 1,
                "_query": 1,
                "_ecu_name": 1,
                "_saved_at": 1,
                "assets._id": 1,
                "assets.template.nodes": 1,
                "assets.template.edges": 1,
                "damage_scenarios.Derivations": 1,
                "damage_scenarios.Details": 1,
            }
        ).sort("_saved_at", DESCENDING).limit(limit)

        results = []
        for doc in cursor:
            nodes    = doc.get("assets", {}).get("template", {}).get("nodes", [])
            edges    = doc.get("assets", {}).get("template", {}).get("edges", [])
            derivs   = doc.get("damage_scenarios", {}).get("Derivations", [])
            details  = doc.get("damage_scenarios", {}).get("Details", [])
            results.append({
                "_id":        str(doc["_id"]),
                "assets_id":  doc.get("assets", {}).get("_id", ""),
                "query":      doc.get("_query", ""),
                "ecu_name":   doc.get("_ecu_name", ""),
                "saved_at":   doc.get("_saved_at", ""),
                "node_count": len(nodes),
                "edge_count": len(edges),
                "deriv_count":  len(derivs),
                "detail_count": len(details),
            })
        return results
    except Exception as e:
        print(f"  ⚠️  MongoDB list failed: {e}")
        return []


def get_report(report_id: str) -> dict | None:
    """Fetch a full TARA report document by its MongoDB _id."""
    try:
        from bson import ObjectId
        from bson.errors import InvalidId
        col = _get_collection()
        
        # Try as ObjectId first
        try:
            doc = col.find_one({"_id": ObjectId(report_id)})
        except InvalidId:
            # Fallback to direct string lookup (for seeded custom IDs)
            doc = col.find_one({"_id": report_id})
            
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
    except Exception as e:
        print(f"  ⚠️  MongoDB get failed for ID {report_id}: {e}")
        return None


def delete_report(report_id: str) -> bool:
    """Delete a TARA report by its MongoDB _id."""
    try:
        from bson import ObjectId
        from bson.errors import InvalidId
        col = _get_collection()
        try:
            result = col.delete_one({"_id": ObjectId(report_id)})
        except InvalidId:
            result = col.delete_one({"_id": report_id})
        return result.deleted_count > 0
    except Exception as e:
        print(f"  ⚠️  MongoDB delete failed for ID {report_id}: {e}")
        return False


def is_connected() -> bool:
    """Quick connectivity check — returns True/False."""
    try:
        _get_collection()
        return True
    except Exception:
        return False
