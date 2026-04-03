"""
IA Juridica - Heroku Entry Point
Serve o Flask frontend como app WSGI principal.
O backend FastAPI roda embutido via thread.
"""

import os
import sys
import asyncio
import threading
import logging

# Setup paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_DIR = os.path.abspath(os.path.dirname(__file__))
BACKEND_DIR = os.path.join(APP_DIR, "backend")

for p in [BASE_DIR, APP_DIR, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Heroku provides DATABASE_URL with postgres:// - convert to postgresql+asyncpg://
db_url = os.environ.get("DATABASE_URL", "")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    os.environ["DATABASE_URL"] = db_url
elif not db_url:
    db_file = os.path.join(APP_DIR, "data", "ia_juridica.db")
    os.makedirs(os.path.dirname(db_file), exist_ok=True)
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + db_file.replace("\\", "/")

os.environ.setdefault("ENVIRONMENT", "production")

logger = logging.getLogger(__name__)


def start_backend_thread():
    """Start FastAPI backend in a background thread"""
    import uvicorn
    port = int(os.environ.get("BACKEND_PORT", "8001"))

    def run_backend():
        try:
            from backend.app.core.database import init_db
            asyncio.run(init_db())
        except Exception as e:
            logger.warning(f"Backend DB init warning: {e}")

        uvicorn.run(
            "backend.app.main:app",
            host="127.0.0.1",
            port=port,
            log_level="warning"
        )

    thread = threading.Thread(target=run_backend, daemon=True)
    thread.start()


# Start the backend in background
start_backend_thread()

# Set Flask API URL to local backend
os.environ["API_BASE_URL"] = f"http://127.0.0.1:{os.environ.get('BACKEND_PORT', '8001')}/api"

# Import Flask app
from frontend.app import app  # noqa: E402
