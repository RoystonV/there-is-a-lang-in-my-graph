# =============================================================================
# config.py — Central configuration for TARA RAG pipeline
# =============================================================================

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Base dataset directory (relative to this file's location)
# ---------------------------------------------------------------------------
BASE_PATH    = Path(__file__).parent / "datasets"

MITRE_MOBILE = BASE_PATH / "mobileattack.json"
MITRE_ICS    = BASE_PATH / "icsattack.json"
ATM_PATH     = BASE_PATH / "atm.json"
CAPEC_PATH   = BASE_PATH / "capec.xml"
CWE_PATH     = BASE_PATH / "cwec.xml"
ECU_PATH     = BASE_PATH / "dataecu.json"
ANNEX_PATH   = BASE_PATH / "annex.json"
CLAUSE_PATH  = BASE_PATH / "clauses"
REPORTS_PATH = BASE_PATH / "reports_db"

# ---------------------------------------------------------------------------
# Embedding model
# BGE-small beats MiniLM on BEIR benchmarks at same size
# ---------------------------------------------------------------------------
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
# Fallback: "sentence-transformers/all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
MAX_CHARS = 1500   # max chars per chunk for threat-framework entries

# ---------------------------------------------------------------------------
# LLM (Ollama — local, no API limits)
# ---------------------------------------------------------------------------
OLLAMA_MODEL   = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
OLLAMA_URL     = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "600"))

# Legacy Gemini (kept for reference)
# GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
RETRIEVER_TOP_K = 20

# ---------------------------------------------------------------------------
# Vector DB (Weaviate)
# ---------------------------------------------------------------------------
WEAVIATE_URL        = os.environ.get("WEAVIATE_URL", "https://pcvgx3uqnuzgf35jbpbg.c0.asia-southeast1.gcp.weaviate.cloud")
WEAVIATE_API_KEY    = os.environ.get("WEAVIATE_API_KEY", "dVJZb1g4YTYwTjZhWDV5QV82YXgzNHFOWnp2V1IrcDh3NlRKSmgxZERZYkxZSzV0dFcxd2lwRlVrVlJRPV92MjAw")
WEAVIATE_COLLECTION = os.environ.get("WEAVIATE_COLLECTION", "HaystackDocument")
