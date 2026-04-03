import sys
import os
import traceback

print("--- Checking Environment ---")
print(f"CWD: {os.getcwd()}")
print(f"PYTHONPATH: {os.environ.get('PYTHONPATH')}")
print(f"sys.path: {sys.path}")

print("\n--- Checking Imports ---")
try:
    print("Attempting to import app.core.config...")
    import app.core.config
    from app.core.config import settings
    print("SUCCESS: app.core.config imported.")
except Exception:
    print("FAIL: Could not import app.core.config")
    traceback.print_exc()

try:
    print("Attempting to import app.models.cliente...")
    import app.models.cliente
    print("SUCCESS: app.models.cliente imported.")
except Exception:
    print("FAIL: Could not import app.models.cliente")
    traceback.print_exc()

try:
    print("Attempting to import app.models...")
    import app.models
    print("SUCCESS: app.models imported.")
except Exception:
    print("FAIL: Could not import app.models")
    traceback.print_exc()

print("\n--- Checking API Routers ---")
routers = [
    "app.api.auth",
    "app.api.rag",
    "app.api.cnj",
    "app.api.peticoes",
    "app.api.mcp",
    "app.api.audit",
    "app.api.documentos",
    "app.api.clientes",
    "app.api.airflow",
    "app.api.admin"
]

for router in routers:
    try:
        print(f"Attempting to import {router}...")
        __import__(router)
        print(f"SUCCESS: {router} imported.")
    except Exception:
        print(f"FAIL: Could not import {router}")
        traceback.print_exc()

print("\n--- Checking Permissions ---")
try:
    test_dir = os.path.join(os.path.dirname(settings.UPLOAD_DIR), "test_perm")
    print(f"Attempting to create {test_dir}...")
    os.makedirs(test_dir, exist_ok=True)
    print(f"SUCCESS: Created {test_dir}")
    os.rmdir(test_dir)
except Exception:
    print(f"FAIL: Could not create {test_dir}")
    traceback.print_exc()
