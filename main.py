# =============================================================================
# main.py — CLI entry point for TARA LangGraph RAG Pipeline
# =============================================================================

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from components import (
    resolve_ecu, list_ecus, build_enriched_query,
    parse_and_fix, print_summary,
    EMBED_MODEL, OLLAMA_MODEL, RETRIEVER_TOP_K,
)
from ingest import load_all_documents
from pipeline import build_graph
import db as mongo_db
from fpdf import FPDF

def save_as_pdf(text_content, output_path):
    """Generates a professional PDF from the SDD markdown content."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="System Design Document (SDD)", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=11)
    
    # Simple line-by-line rendering for the PDF
    for line in text_content.split('\n'):
        # Clean up some basic markdown bold/bullets for the PDF
        clean_line = line.replace('**', '').replace('###', '').replace('##', '').strip()
        if not clean_line:
            pdf.ln(5)
            continue
        pdf.multi_cell(0, 8, txt=clean_line.encode('latin-1', 'replace').decode('latin-1'))
    
    pdf.output(str(output_path))


def main():
    parser = argparse.ArgumentParser(
        description="TARA Agentic RAG Pipeline",
    )

    parser.add_argument("--query", "-q", type=str, default=None)
    parser.add_argument("--output", "-o", type=str, default=None)
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--list-ecus", action="store_true")

    args = parser.parse_args()

    # ── List ECUs ─────────────────────────────────────────────
    if args.list_ecus:
        list_ecus()
        return

    if not args.query:
        parser.print_help()
        sys.exit(1)

    user_query = args.query.strip()

    print("\n" + "=" * 60)
    print("  TARA Agentic RAG (LangGraph)")
    print("=" * 60)
    print(f"  Query : {user_query}")
    print("=" * 60 + "\n")



    # ── STEP 1: ECU RESOLUTION ───────────────────────────────
    print("[1/4] Resolving ECU...")
    ecu_entry = resolve_ecu(user_query)

    if ecu_entry:
        print(f"  ✅ Matched : {ecu_entry['name']}")
    else:
        print("  ⚠️ No match found")

    enriched_query = build_enriched_query(user_query, ecu_entry)

    # ── STEP 2: INGEST ───────────────────────────────────────
    print("\n[2/4] Loading documents...")
    all_docs = load_all_documents()

    # ── STEP 3: LANGGRAPH BUILD ──────────────────────────────
    print("\n[3/4] Building LangGraph pipeline...")
    graph = build_graph(all_docs)

    # ── STEP 4: GENERATE ─────────────────────────────────────
    print("\n[4/4] Generating report...")
    print(f"  Embedding model : {EMBED_MODEL}")
    print(f"  LLM model       : {OLLAMA_MODEL} (Ollama)")
    print(f"  Retriever top_k : {RETRIEVER_TOP_K}")

    result = graph.invoke({
        "user_query": user_query,
        "enriched_query": enriched_query,
        "retry_count": 0
    })

    raw_output = result["answer"]

    # ── POST PROCESS ─────────────────────────────────────────
    print("\nPost-processing...")
    tara_json = parse_and_fix(raw_output)

    if tara_json is None:
        print("❌ Failed to parse output")
        print(raw_output[:1000])
        sys.exit(1)

    print("✅ JSON parsed successfully")
    print_summary(tara_json)

    # ── PRINT OUTPUT ─────────────────────────────────────────
    print("\n" + "-" * 60)
    print(json.dumps(tara_json, indent=2, ensure_ascii=False))
    print("-" * 60)

    # ── SAVE FILE ────────────────────────────────────────────
    if not args.no_save:
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", user_query.strip())
        
        # Directories matching user request
        outputs_dir = Path(__file__).parent / "outputs"
        prompts_dir = outputs_dir / "prompts"
        tara_dir    = outputs_dir / "Results"
        eval_dir    = outputs_dir / "langgraph_evaluation_results"
        
        prompts_dir.mkdir(parents=True, exist_ok=True)
        tara_dir.mkdir(parents=True, exist_ok=True)
        eval_dir.mkdir(parents=True, exist_ok=True)

        # Build full_prompt from the SDD report (multi-agent graph
        # doesn't populate full_prompt directly)
        full_prompt = result.get("full_prompt", "") or result.get("sdd_report", "")

        # 1. Save TARA JSON output
        out_file = args.output or f"tara_output_{safe_name}.json"
        out_path = tara_dir / out_file
        
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(tara_json, f, indent=2, ensure_ascii=False)
        print(f"✅ TARA Saved → {out_path}")
            
        # 2. Save SDD Report (Markdown + PDF)
        sdd_dir = outputs_dir / "sdd_reports"
        sdd_dir.mkdir(parents=True, exist_ok=True)
        sdd_name = f"sdd_report_{safe_name}"
        
        if "sdd_report" in result:
            sdd_md_path = sdd_dir / f"{sdd_name}.md"
            sdd_pdf_path = sdd_dir / f"{sdd_name}.pdf"
            
            # Save Markdown
            with open(sdd_md_path, "w", encoding="utf-8") as f:
                f.write(result["sdd_report"])
            
            # Save PDF
            try:
                save_as_pdf(result["sdd_report"], sdd_pdf_path)
                print(f"  ✅ SDD Reports saved: \n     - MD: {sdd_md_path}\n     - PDF: {sdd_pdf_path}")
            except Exception as e:
                print(f"  ⚠️  PDF generation failed: {e}")
        
        # 3. Save Full Prompt for Debugging
        if full_prompt:
            prompt_path = prompts_dir / f"tara_prompt_{safe_name}.txt"
            with open(prompt_path, "w", encoding="utf-8") as f:
                f.write(full_prompt)
            print(f"  📄 Prompt saved → {prompt_path}")

        # 4. Save Evaluation Results
        eval_details = result.get("eval_details", {})
        if eval_details:
            eval_path = eval_dir / f"eval_report_{safe_name}.json"
            with open(eval_path, "w", encoding="utf-8") as f:
                json.dump(eval_details, f, indent=2, ensure_ascii=False)
            print(f"  📊 Evaluation saved → {eval_path}")

        # 5. MongoDB Sync
        if "MONGO_URI" in os.environ:
             mongo_db.save_report(
                 tara_json, 
                 query_name=user_query, 
                 ecu_name=ecu_entry["name"] if ecu_entry else user_query,
                 full_prompt=full_prompt,
                 eval_score=result.get("eval_score", 0)
             )


if __name__ == "__main__":
    main()