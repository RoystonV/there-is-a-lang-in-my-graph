# 🛡️ TARA Agentic RAG Pipeline

A **multi-agent RAG (Retrieval-Augmented Generation) pipeline** for generating ISO 21434-compliant **Threat Analysis and Risk Assessment (TARA)** reports for automotive ECUs. Built with **LangGraph** for agentic orchestration, **Haystack** for retrieval, and **Ollama** for local LLM inference.

---

## 🏗️ Architecture

The pipeline uses a 4-agent LangGraph state machine that processes a user query (e.g., "BMS") through a structured chain of AI agents:

```
┌─────────┐    ┌─────────┐    ┌───────────┐    ┌─────────┐    ┌────────┐
│ Retrieve │───▶│   SDD   │───▶│ Architect │───▶│ Threat  │───▶│ Damage │
│ (RAG)   │    │ Analyst │    │           │    │ Analyst │    │Analyst │
└─────────┘    └─────────┘    └───────────┘    └─────────┘    └────────┘
     │                                                              │
     │              ┌──────────┐    ┌───────┐                       │
     └──────────────│  Retry   │◀───│ Eval  │◀──────────────────────┘
                    └──────────┘    └───────┘
```

| Agent | Role |
|:------|:-----|
| **Retrieve** | Embeds the query and retrieves top-K relevant documents from Weaviate |
| **SDD Analyst** | Writes a human-readable System Design Document from retrieved context |
| **Architect** | Converts the SDD into structured JSON architecture (nodes, edges, details) |
| **Threat Analyst** | Identifies threats based on architecture + threat frameworks (CAPEC, CWE, MITRE) |
| **Damage Analyst** | Assesses impact ratings and damage scenarios per ISO 21434 |
| **Evaluator** | Scores the output and triggers a retry if quality is below threshold |

## 📁 Project Structure

```
├── main.py              # CLI entry point — orchestrates the full pipeline
├── pipeline.py          # LangGraph state machine definition and agent nodes
├── components.py        # Haystack component builders (store, retriever, generator)
├── config.py            # Central configuration (models, paths, API keys)
├── prompt.py            # Jinja2 prompt templates for each agent
├── ingest.py            # Document ingestion (MITRE, CAPEC, CWE, ISO 21434, ECU data)
├── db.py                # MongoDB integration for report persistence
├── requirements.txt     # Python dependencies
├── docker-compose.yml   # Local Weaviate + MongoDB services
├── datasets/            # Threat frameworks, ECU specs, ISO clauses
│   ├── dataecu.json     # ECU specifications and reference architectures
│   ├── reports_db/      # Pre-built reference TARA reports (BMS, Infotainment)
│   ├── clauses/         # ISO 21434 clause text files
│   ├── annex.json       # ISO 21434 Annex F damage scenario templates
│   ├── capec.xml        # CAPEC attack patterns
│   ├── cwec.xml         # CWE weakness enumeration
│   ├── mobileattack.json # MITRE ATT&CK Mobile
│   ├── icsattack.json   # MITRE ATT&CK ICS
│   └── atm.json         # Automotive threat model entries
└── outputs/             # Generated reports
    ├── Results/         # Final TARA JSON outputs
    ├── sdd_reports/     # SDD as Markdown + PDF
    ├── prompts/         # Saved prompts for debugging
    └── langgraph_evaluation_results/  # Evaluation scores
```

## 🔧 Knowledge Sources

The RAG pipeline ingests **2100+ documents** across these categories:

| Source | Count | Description |
|:-------|------:|:------------|
| CWE | 969 | Common Weakness Enumeration |
| CAPEC | 613 | Common Attack Pattern Enumeration |
| MITRE Mobile | 176 | Mobile ATT&CK techniques |
| MITRE ICS | 95 | Industrial Control System techniques |
| ATM | 77 | Automotive threat model entries |
| REPORTS_DB | ~90 | Pre-built reference architectures (BMS, Infotainment) |
| ECU | 50 | ECU specifications from `dataecu.json` |
| ISO 21434 | 39 | Clause text + risk assessment methodology |
| Annex F | 5 | Damage scenario impact categories |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Ollama** — for local LLM inference (no API keys needed)
- **Weaviate Cloud** account (or local instance via Docker)

### 1. Install Ollama

```bash
# Windows (winget)
winget install Ollama.Ollama

# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Pull a model

```bash
# Recommended: gemma3:4b (fast, ~3GB)
ollama pull gemma3:4b

# Better quality: gemma3:12b or llama3.1:8b (~7-8GB)
ollama pull gemma3:12b
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the pipeline

```bash
# Generate a TARA report for a Battery Management System
python main.py --query "BMS"

# Generate for Infotainment Head Unit
python main.py --query "Infotainment"

# List all supported ECUs
python main.py --list-ecus

# Custom output file
python main.py --query "BMS" --output my_report.json
```

### 5. (Optional) Use a different model

Set the `OLLAMA_MODEL` environment variable:

```bash
# PowerShell
$env:OLLAMA_MODEL="gemma3:12b"
python main.py --query "BMS"

# Bash
OLLAMA_MODEL=gemma3:12b python main.py --query "BMS"
```

---

## ⚙️ Configuration

All settings are centralized in `config.py` and can be overridden via environment variables:

| Variable | Default | Description |
|:---------|:--------|:------------|
| `OLLAMA_MODEL` | `gemma3:4b` | Ollama model to use |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_TIMEOUT` | `600` | Request timeout in seconds |
| `WEAVIATE_URL` | *(cloud URL)* | Weaviate instance URL |
| `WEAVIATE_API_KEY` | *(set via env)* | Weaviate authentication key |
| `MONGO_URI` | *(optional)* | MongoDB connection string for report persistence |

---

## 📊 Output Format

The pipeline generates a structured JSON report compatible with the TARA frontend visualizer:

```json
{
  "assets": {
    "template": {
      "nodes": [
        {
          "id": "BMM",
          "type": "default",
          "parentId": "SYS",
          "position": { "x": 124, "y": 257 },
          "data": {
            "label": "Battery Monitoring Manager",
            "description": "Measures cell voltage, current...",
            "details": [
              { "name": "Integrity", "id": "I01" },
              { "name": "Authenticity", "id": "A01" }
            ]
          }
        }
      ],
      "edges": [...],
      "details": [...]
    }
  },
  "damage_scenarios": {
    "Derivations": [...],
    "Details": [...]
  }
}
```

---

## 🐳 Docker (Local Weaviate + MongoDB)

To run Weaviate and MongoDB locally instead of using cloud services:

```bash
docker-compose up -d
```

Then update environment variables:
```bash
export WEAVIATE_URL=http://localhost:8080
export MONGO_URI=mongodb://localhost:27017/tara_db
```

---

## 📝 Notes

- **First run** ingests all documents into Weaviate (~2100 docs). Subsequent runs skip ingestion if the collection already exists.
- **Embedding model**: `BAAI/bge-small-en-v1.5` — downloaded automatically on first run (~130MB).
- **Windows users**: Set `PYTHONIOENCODING=utf-8` if you see Unicode errors in the terminal.
- The pipeline includes an **auto-retry mechanism** — if the evaluation score is below 50%, it automatically re-runs the generation chain once.

---

## 📄 License

This project is part of an academic research project on automotive cybersecurity threat analysis using RAG pipelines and agentic AI.
