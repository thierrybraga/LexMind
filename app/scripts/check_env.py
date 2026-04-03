import sys
import importlib.util

def check_import(module_name):
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        print(f"❌ {module_name}: NOT INSTALLED")
        return False
    else:
        print(f"✅ {module_name}: INSTALLED ({spec.origin})")
        return True

print("Checking RAG dependencies...")
rag_deps = ["sentence_transformers", "chromadb", "numpy"]
all_ok = True
for dep in rag_deps:
    if not check_import(dep):
        all_ok = False

if all_ok:
    print("\nAll RAG dependencies are present.")
else:
    print("\nSome RAG dependencies are MISSING. RAG will run in MOCK mode.")