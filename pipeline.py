from langgraph.graph import StateGraph
from typing import TypedDict
from collections import Counter
import jinja2

import json
import re

from components import build_store, build_retriever, build_generator
from config import RETRIEVER_TOP_K, OLLAMA_MODEL

# ---------------- STATE ----------------
class RAGState(TypedDict):
    user_query: str
    enriched_query: str
    documents: list
    sdd_report: str          # The new Mentor-grade SDD report
    architecture: dict       # High-quality system design
    threats: list            # Detailed threat analysis
    damage_details: list     # Impact ratings and scenarios
    answer: str              # Final Combined JSON
    retry_count: int
    full_prompt: str
    eval_score: int
    eval_details: dict

# ---------------- SETUP ----------------
def setup(all_docs):
    store, text_embedder = build_store(all_docs)
    retriever = build_retriever(store)
    generator = build_generator()
    return retriever, generator, text_embedder


def safe_generate(prompt: str, role_name: str = "Agent"):
    """Call Ollama via Haystack OllamaGenerator. No rate limits — runs locally."""
    try:
        result = generator.run(prompt=prompt)
        return result
    except Exception as e:
        print(f"  ❌ {role_name} error: {e}")
        return {"replies": [""]}

# ---------------- NODES ----------------

def retrieve(state: RAGState):
    """Retrieves relevant documents using the Haystack retriever."""
    query = state.get("enriched_query") or state.get("user_query")
    embedding = text_embedder.run(text=query)["embedding"]
    result = retriever.run(query_embedding=embedding)
    # Safety: ensure we don't pass massive content if context is bloated
    docs = result["documents"][:RETRIEVER_TOP_K]
    return {"documents": docs}

def sdd_analyst_node(state: RAGState):
    """AGENT 0: Writes a human-readable System Design Document (SSD)."""
    from prompt import SDD_ANALYST_PROMPT
    print("  📑 Writing System Design Document (SDD)...")
    
    tmpl = jinja2.Template(SDD_ANALYST_PROMPT)
    prompt = tmpl.render(question=state["user_query"], documents=state["documents"])
    
    result = safe_generate(prompt, "Analyst")
    report = result["replies"][0] if result["replies"] else "Failed to generate SDD."
    
    return {"sdd_report": report}

def architect_node(state: RAGState):
    """AGENT 1: Turns the SDD report into a structured JSON architecture."""
    from prompt import ARCHITECT_PROMPT
    print("  🏗️  Architecting system from SDD...")
    
    tmpl = jinja2.Template(ARCHITECT_PROMPT)
    prompt = tmpl.render(sdd_report=state["sdd_report"]) # ONLY uses the SDD as source of truth!
    
    result = safe_generate(prompt, "Architect")
    raw_json = result["replies"][0] if result["replies"] else "{}"
    

    try:
        cleaned = re.sub(r"^```[a-z]*\n?", "", raw_json.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"```$", "", cleaned.strip())
        arch_data = json.loads(cleaned)
        return {"architecture": arch_data.get("assets", {})}
    except Exception as e:
        print(f"  ⚠️  Architect parsing failed: {e}")
        return {"architecture": {}}

def threat_analysis_node(state: RAGState):
    """AGENT 2: Focuses on identifying Threats based on the Architecture."""
    from prompt import THREAT_PROMPT
    if not state.get("architecture"): return {"threats": []}
    
    print("  🛡️  Analyzing threats...")
    tmpl = jinja2.Template(THREAT_PROMPT)
    prompt = tmpl.render(
        question=state["user_query"],
        architecture=json.dumps(state["architecture"], indent=2),
        sdd_report=state.get("sdd_report", ""),
        documents=state["documents"]
    )
    
    result = safe_generate(prompt, "ThreatAnalyst")
    raw_json = result["replies"][0] if result["replies"] else "{}"
    

    try:
        cleaned = re.sub(r"^```[a-z]*\n?", "", raw_json.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"```$", "", cleaned.strip())
        threat_data = json.loads(cleaned)
        return {"threats": threat_data.get("Derivations", [])}
    except Exception as e:
        print(f"  ⚠️  Threat parsing failed: {e}")
        return {"threats": []}

def damage_scenario_node(state: RAGState):
    """AGENT 3: Focuses on Impact Ratings and Damage Scenarios."""
    from prompt import DAMAGE_PROMPT
    if not state.get("threats"): return {"damage_details": []}
    
    print("  💥 Assessing damage scenarios...")
    tmpl = jinja2.Template(DAMAGE_PROMPT)
    prompt = tmpl.render(
        threats=json.dumps(state["threats"], indent=2),
        architecture=json.dumps(state["architecture"], indent=2)
    )
    
    result = safe_generate(prompt, "DamageAnalyst")
    raw_json = result["replies"][0] if result["replies"] else "{}"
    
    try:
        cleaned = re.sub(r"^```[a-z]*\n?", "", raw_json.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"```$", "", cleaned.strip())
        damage_data = json.loads(cleaned)
        return {"damage_details": damage_data.get("Details", [])}
    except Exception as e:
        print(f"  ⚠️  Damage parsing failed: {e}")
        return {"damage_details": []}

def evaluate(state: RAGState):
    """Combine all agent outputs into the final TARA JSON and evaluate."""
    print("  📝 Combining and evaluating...")
    
    # Assemble final JSON
    final_output = {
        "assets": state.get("architecture", {}),
        "damage_scenarios": {
            "Derivations": state.get("threats", []),
            "Details": state.get("damage_details", [])
        }
    }
    
    state["answer"] = json.dumps(final_output)
    
    points = 0
    eval_metrics = {
        "json_valid": True,
        "schema_valid": False,
        "node_count": 0,
        "damage_scenarios_count": 0,
        "retry_attempt": state.get("retry_count", 0)
    }

    if "assets" in final_output and "damage_scenarios" in final_output:
        points += 1
        eval_metrics["schema_valid"] = True

    nodes = final_output.get("assets", {}).get("template", {}).get("nodes", [])
    eval_metrics["node_count"] = len(nodes)
    if len(nodes) >= 5: points += 1
    elif len(nodes) >= 3: points += 0.5

    derivations = final_output.get("damage_scenarios", {}).get("Derivations", [])
    eval_metrics["damage_scenarios_count"] = len(derivations)
    if derivations: points += 1
    
    state["eval_score"] = int(points * 20 + 20)
    eval_metrics["final_score"] = state["eval_score"]
    state["eval_details"] = eval_metrics

    print(f"  EVALUATION: Multi-agent score {state['eval_score']}%")
    return {"eval_score": state['eval_score'], "eval_details": state['eval_details'], "answer": state["answer"]}

# ---------------- ROUTER ----------------
def evaluate_router(state):
    score = state.get("eval_score", 0)
    retry_count = state.get("retry_count", 0)
    
    if score < 50 or state.get("eval_details", {}).get("node_count") < 3:
        return "retry" if retry_count < 1 else "end"
    return "end"

# ---------------- RETRY ----------------
def retry(state):
    return {"retry_count": state["retry_count"] + 1}

# ---------------- BUILD GRAPH ----------------
def build_graph(all_docs):
    global retriever, generator, text_embedder
    retriever, generator, text_embedder = setup(all_docs)

    builder = StateGraph(RAGState)

    builder.add_node("retrieve", retrieve)
    builder.add_node("analyst", sdd_analyst_node) # STEP 0
    builder.add_node("architect", architect_node)
    builder.add_node("threats", threat_analysis_node)
    builder.add_node("damage", damage_scenario_node)
    builder.add_node("evaluate", evaluate)
    builder.add_node("retry", retry)

    builder.set_entry_point("retrieve")

    builder.add_edge("retrieve", "analyst") # Connect Retrieve -> Analyst
    builder.add_edge("analyst", "architect") # Connect Analyst -> Architect
    builder.add_edge("architect", "threats")
    builder.add_edge("threats", "damage")
    builder.add_edge("damage", "evaluate")

    builder.add_conditional_edges(
        "evaluate",
        evaluate_router,
        {
            "retry": "retry",
            "end": "__end__"
        }
    )

    builder.add_edge("retry", "retrieve")

    return builder.compile()