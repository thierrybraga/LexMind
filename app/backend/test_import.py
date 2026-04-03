
import sys
import os

# Add backend directory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)
print(f"Added {backend_dir} to sys.path")

try:
    from app.api import auth
    print("Successfully imported app.api.auth")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
