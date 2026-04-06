import os
import google.generativeai as genai

def list_models():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY environment variable not set.")
        return

    genai.configure(api_key=api_key)
    
    print("Available Gemini Models:")
    print("-" * 30)
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"Model: {m.name}")
                print(f"  Short name  : {m.name.split('/')[-1]}")
                print(f"  Description: {m.description}")
                print("-" * 30)
    except Exception as e:
        print(f"❌ Error listing models: {e}")

if __name__ == "__main__":
    list_models()
