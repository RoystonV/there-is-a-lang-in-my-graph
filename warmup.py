import os
import sys
from pathlib import Path

# Ensure we are looking at the right folder
try:
    from haystack.components.embedders import SentenceTransformersDocumentEmbedder
    print(" Initializing Model Warmup...")
    
    # 1. Force download of the BGE model (Exactly as used in main.py)
    model_name = "BAAI/bge-small-en-v1.5"
    embedder = SentenceTransformersDocumentEmbedder(model=model_name)
    embedder.warm_up()
    
    print("\n" + "="*50)
    print(" SUCCESS: Embedding Model Cached Locally!")
    print(f" Model Location: {model_name}")
    print("="*50)
    
    # 2. Check Directory Health
    outputs_path = Path(__file__).parent / "outputs"
    folders = ["Results", "prompts", "langgraph_evaluation_results"]
    
    print("\n📂 Ensuring Output Folders Exist...")
    for f in folders:
        f_path = outputs_path / f
        f_path.mkdir(parents=True, exist_ok=True)
        print(f"  - {f} : [READY]")

    # 3. Check for API Key
    if "GOOGLE_API_KEY" in os.environ:
        print("\n🔑 API KEY detected in Environment!")
    else:
        print("\n⚠️  WARNING: GOOGLE_API_KEY is not set.")
        print("   -> Run: $env:GOOGLE_API_KEY='your_key_here'")

except Exception as e:
    print(f"\n❌ ERROR DURING WARMUP: {e}")
    print("\nSuggestion: Ensure you are in the 'Langraph_rag_fucytech' folder and run: pip install sentence-transformers")
