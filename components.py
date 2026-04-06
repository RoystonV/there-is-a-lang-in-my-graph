# =============================================================================
# components.py — Config, ECU resolution, UUID post-processing, component setup
# =============================================================================

import json
import os
import re
import uuid as _uuid
from pathlib import Path

from haystack.components.embedders import (
    SentenceTransformersDocumentEmbedder,
    SentenceTransformersTextEmbedder,
)
from haystack.utils import Secret
from haystack_integrations.document_stores.weaviate import WeaviateDocumentStore
from haystack_integrations.document_stores.weaviate.auth import AuthApiKey
from haystack_integrations.components.retrievers.weaviate import WeaviateEmbeddingRetriever
from haystack_integrations.components.generators.ollama import OllamaGenerator

from config import (
    EMBED_MODEL, MAX_CHARS, OLLAMA_MODEL, OLLAMA_URL, OLLAMA_TIMEOUT,
    RETRIEVER_TOP_K,
    WEAVIATE_URL, WEAVIATE_API_KEY, WEAVIATE_COLLECTION,
    MITRE_MOBILE, MITRE_ICS, ATM_PATH, CAPEC_PATH, CWE_PATH,
    ECU_PATH, ANNEX_PATH, CLAUSE_PATH, REPORTS_PATH
)


# ─────────────────────────────────────────────────────────────────────────────
# ECU RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────

_SUFFIX_WORDS = {
    "ecu", "system", "module", "interface", "controller", "unit",
    "network", "port", "server", "bus", "head", "vehicle", "automotive"
}

_ALIASES = {
    "obd":               "obd",
    "obd-ii":            "obd",
    "obd2":              "obd",
    "tcu":               "tcu",
    "telematics control":"tcu",
    "bcm":               "bcm",
    "ecm":               "ecm",
    "ivi":               "ivi",
    "eps":               "eps",
    "abs":               "abs",
    "bms":               "bms",
    "adas":              "adas",
}


def _acronym(text: str) -> str:
    skip      = {"the", "and", "for", "of", "a", "an", "or", "in", "on", "to", "/"}
    words     = [w.strip("()/-").lower() for w in text.replace("/", " ").split()]
    sig_words = [w for w in words if w and w not in skip]
    core      = [w for w in sig_words if w not in _SUFFIX_WORDS]
    chosen    = core if core else sig_words
    return "".join(w[0] for w in chosen if w)


def resolve_ecu(query: str, ecu_path=None) -> dict | None:
    """5-pass fuzzy-match query to a dataecu.json entry. Returns entry dict or None."""
    ecu_path = ecu_path or ECU_PATH
    with open(ecu_path, "r", encoding="utf-8") as f:
        ecu_db = json.load(f)
    q = query.lower().strip()

    # Pass 0: alias table
    for phrase, key in _ALIASES.items():
        if phrase in q and key in ecu_db:
            return ecu_db[key]
    # Pass 1: exact key or standalone word
    for key, entry in ecu_db.items():
        if key == q or f" {key} " in f" {q} ":
            return entry
    # Pass 2: full name substring
    for key, entry in ecu_db.items():
        if entry["name"].lower() in q:
            return entry
    # Pass 3a: exact acronym
    qa = _acronym(q)
    for key, entry in ecu_db.items():
        if qa and qa == key:
            return entry
    # Pass 3b: acronym prefix
    if len(qa) >= 2:
        for key, entry in ecu_db.items():
            if key.startswith(qa) and len(key) - len(qa) <= 1:
                return entry
    # Pass 4: word overlap
    for key, entry in ecu_db.items():
        name_words = [w.strip("()/-").lower() for w in entry["name"].replace("/", " ").split()]
        core       = [w for w in name_words if len(w) > 2 and w not in _SUFFIX_WORDS]
        if sum(1 for w in core if w in q) >= 2:
            return entry
    # Pass 5: key word in query
    for key, entry in ecu_db.items():
        if any(w in q for w in key.replace("_", " ").split() if len(w) > 3):
            return entry
    return None


def list_ecus(ecu_path=None) -> None:
    """Print all ECU keys and names from dataecu.json."""
    ecu_path = ecu_path or ECU_PATH
    with open(ecu_path, "r", encoding="utf-8") as f:
        ecu_db = json.load(f)
    print(f"\n{'Key':<20} {'Name'}")
    print("-" * 60)
    for key, entry in ecu_db.items():
        print(f"  {key:<18} {entry.get('name', '')}")
    print(f"\nTotal: {len(ecu_db)} ECU entries")


def build_enriched_query(user_query: str, ecu_entry: dict | None) -> str:
    if ecu_entry:
        return (
            f"{ecu_entry['name']}\n\n"
            f"AUTHORITATIVE ASSET LIST (from system dataecu specification) — "
            f"generate ONLY these assets, no others:\n"
            f"{ecu_entry['hint']}\n\n"
            f"All threat analysis, damage scenarios, and edges must reference "
            f"ONLY the assets listed above. Do NOT add any other components."
        )
    return user_query


# ─────────────────────────────────────────────────────────────────────────────
# POST-PROCESSING
# ─────────────────────────────────────────────────────────────────────────────

def stamp_uuids(obj: dict) -> dict:
    """Replace empty/placeholder id/_id/model_id fields with fresh uuid4 values."""
    ID_KEYS = {"id", "_id", "model_id"}

    def _bad(val):
        if not val:
            return True
        if isinstance(val, str) and (
            "PLACEHOLDER" in val or val.strip() == "" or val.startswith("<")
        ):
            return True
        return False

    def _walk(o):
        if isinstance(o, dict):
            for k, v in list(o.items()):
                if k in ID_KEYS and _bad(v):
                    o[k] = str(_uuid.uuid4())
                else:
                    _walk(v)
        elif isinstance(o, list):
            for item in o:
                _walk(item)

    _walk(obj)
    return obj


def crosslink_node_ids(obj: dict) -> dict:
    """Propagate stamped nodeIds into Edges, Derivations, and cyberLosses by label-matching."""
    template = obj.get("assets", {}).get("template", {})
    nodes = template.get("nodes", [])
    edges = template.get("edges", [])
    
    label_to_id = {
        n.get("data", {}).get("label", "").lower(): n.get("id")
        for n in nodes if n.get("id")
    }

    # Fix Edges
    for edge in edges:
        src_label = edge.get("source", "").lower()
        tgt_label = edge.get("target", "").lower()
        if src_label in label_to_id:
            edge["source"] = label_to_id[src_label]
        if tgt_label in label_to_id:
            edge["target"] = label_to_id[tgt_label]

    for d in obj.get("damage_scenarios", {}).get("Derivations", []):
        nid = d.get("nodeId", "")
        if not nid or str(nid).startswith("<") or "PLACEHOLDER" in str(nid):
            d["nodeId"] = label_to_id.get(d.get("asset", "").lower()) or str(_uuid.uuid4())
    
    for det in obj.get("damage_scenarios", {}).get("Details", []):
        for cl in det.get("cyberLosses", []):
            nid = cl.get("nodeId", "")
            if not nid or str(nid).startswith("<") or "PLACEHOLDER" in str(nid):
                cl["nodeId"] = label_to_id.get(cl.get("node", "").lower()) or str(_uuid.uuid4())
            if not cl.get("id") or str(cl.get("id", "")).startswith("<"):
                cl["id"] = str(_uuid.uuid4())
    return obj


def parse_and_fix(raw_text: str) -> dict | None:
    """Strip markdown fences, parse JSON, stamp UUIDs, crosslink nodeIds."""
    cleaned = re.sub(r"^```[a-z]*\n?", "", raw_text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned.strip())
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON parse error: {e}")
        print(f"Raw output (first 500 chars):\n{cleaned[:500]}")
        return None
    return crosslink_node_ids(stamp_uuids(obj))


def print_summary(tara_json: dict) -> None:
    node_count  = len(tara_json.get("assets", {}).get("template", {}).get("nodes", []))
    edge_count  = len(tara_json.get("assets", {}).get("template", {}).get("edges", []))
    deriv_count = len(tara_json.get("damage_scenarios", {}).get("Derivations", []))
    ds_count    = len(tara_json.get("damage_scenarios", {}).get("Details", []))
    print(f"   Nodes          : {node_count}")
    print(f"   Edges          : {edge_count}")
    print(f"   Derivations    : {deriv_count}")
    print(f"   Damage details : {ds_count}")
    print("   IDs            : all stamped as uuid4")


# ─────────────────────────────────────────────────────────────────────────────
# HAYSTACK COMPONENT BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def build_store(all_docs=None):
    """Embed all_docs, load into WeaviateDocumentStore. Skip if already populated."""
    store = WeaviateDocumentStore(
        url=WEAVIATE_URL,
        auth_client_secret=AuthApiKey(api_key=Secret.from_token(WEAVIATE_API_KEY)),
        collection_settings={
            "class": WEAVIATE_COLLECTION,
            "properties": [
                {"name": "_original_id", "dataType": ["text"]},
                {"name": "content",       "dataType": ["text"]},
                {"name": "blob_data",     "dataType": ["blob"]},
                {"name": "blob_mime_type","dataType": ["text"]},
                {"name": "score",         "dataType": ["number"]},
                # Meta fields that would be misdetected as UUID
                {"name": "node_id",  "dataType": ["text"]},
                {"name": "stix_id",  "dataType": ["text"]},
                {"name": "capec_id", "dataType": ["text"]},
                {"name": "cwe_id",   "dataType": ["text"]},
            ],
        },
    )
    
    text_embedder = SentenceTransformersTextEmbedder(model=EMBED_MODEL)
    text_embedder.warm_up()

    # 🚀 OPTIMIZATION: Check if data already exists in Weaviate Cloud
    try:
        count = store.count_documents()
        if count > 0:
            print(f"✅ Weaviate Cloud is already populated with {count} documents.")
            print(f"⚡ Skipping re-ingestion to save time and API quota.")
            return store, text_embedder
    except Exception as e:
        print(f"⚠️  Could not check document count: {e}")

    if not all_docs:
        print("⚠️ No documents provided and Weaviate is empty. Processing stopped.")
        return store, text_embedder

    print(f"✅ Embedders ready  [{EMBED_MODEL}]")
    doc_embedder = SentenceTransformersDocumentEmbedder(model=EMBED_MODEL)
    doc_embedder.warm_up()

    print(f"🔄 Embedding {len(all_docs)} documents and storing in Weaviate...")
    embedded_docs = doc_embedder.run(documents=all_docs)["documents"]
    store.write_documents(embedded_docs)
    print(f"✅ {store.count_documents()} documents embedded and stored in Weaviate.")
    return store, text_embedder


def build_retriever(store):
    return WeaviateEmbeddingRetriever(document_store=store, top_k=RETRIEVER_TOP_K)


def build_generator():
    return OllamaGenerator(
        model=OLLAMA_MODEL,
        url=OLLAMA_URL,
        timeout=OLLAMA_TIMEOUT,
    )
