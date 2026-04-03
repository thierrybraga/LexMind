"""
IA Juridica - Launcher para desenvolvimento local
Inicia Backend (FastAPI) + Frontend (Flask) simultaneamente
"""

import os
import sys
import asyncio
import subprocess
import signal
import time

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
APP_DIR = os.path.join(BASE_DIR, "app")
BACKEND_DIR = os.path.join(APP_DIR, "backend")

# Adicionar paths ao sys.path
for p in [APP_DIR, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Configurar DATABASE_URL para SQLite local se nao definido
DB_FILE = os.path.join(APP_DIR, "data", "ia_juridica.db")
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
DB_URL = "sqlite+aiosqlite:///" + DB_FILE.replace("\\", "/")
os.environ.setdefault("DATABASE_URL", DB_URL)
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("PYTHONPATH", BACKEND_DIR)

# Carregar .env se existir
env_file = os.path.join(APP_DIR, ".env")
if os.path.exists(env_file):
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    os.environ.setdefault(key, value)


def init_database():
    """Inicializa o banco de dados criando as tabelas"""
    print("\n[IA Juridica] Inicializando banco de dados...")
    # Tenta importar init_db com diferentes estratégias
    try:
        # Estratégia 1: Se BACKEND_DIR estiver no path (o que fizemos acima)
        from app.core.database import init_db
    except ImportError:
        try:
            # Estratégia 2: Caminho relativo/absoluto se o path estiver diferente
            from backend.app.core.database import init_db
        except ImportError:
            print("[AVISO] Não foi possível importar init_db. Pulando inicialização do banco.")
            return

    try:
        # Criar loop se não existir
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        loop.run_until_complete(init_db())
        print("[IA Juridica] Banco de dados inicializado.\n")
    except Exception as e:
        print(f"[AVISO] Erro ao inicializar banco: {e}")

def start_backend():
    """Inicia o backend FastAPI na porta 8000"""
    env = os.environ.copy()
    # Adiciona paths explicitamente
    env["PYTHONPATH"] = f"{BACKEND_DIR};{APP_DIR};{env.get('PYTHONPATH', '')}"
    
    cmd = [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1", "--port", "8000",
        "--reload", "--log-level", "info"
    ]
    
    print(f"[DEBUG] Backend CMD: {' '.join(cmd)}")
    print(f"[DEBUG] Backend CWD: {BACKEND_DIR}")
    
    return subprocess.Popen(
        cmd,
        cwd=BACKEND_DIR,
        env=env
    )


def start_frontend():
    """Inicia o frontend Flask na porta 5000"""
    env = os.environ.copy()
    frontend_dir = os.path.join(APP_DIR, "frontend")
    
    # Adicionar frontend dir ao path
    env["PYTHONPATH"] = f"{frontend_dir};{APP_DIR};{env.get('PYTHONPATH', '')}"
    env["FLASK_APP"] = "app.py"
    env["FLASK_DEBUG"] = "true"
    env["API_BASE_URL"] = "http://localhost:8000/api"
    
    cmd = [
        sys.executable, "-m", "flask", "run",
        "--host", "127.0.0.1", "--port", "5000", "--reload"
    ]
    
    print(f"[DEBUG] Frontend CMD: {' '.join(cmd)}")
    print(f"[DEBUG] Frontend CWD: {frontend_dir}")
    
    return subprocess.Popen(
        cmd,
        cwd=frontend_dir,
        env=env
    )


def main():
    print("=" * 55)
    print("  IA JURIDICA - Sistema de IA para Advocacia")
    print("  Modo: Desenvolvimento Local")
    print("=" * 55)

    # 1. Inicializar banco
    try:
        init_database()
    except Exception as e:
        print(f"[AVISO] Erro ao inicializar banco: {e}")
        print("[AVISO] Continuando mesmo assim...\n")

    # 2. Iniciar processos
    processes = []

    print("[IA Juridica] Iniciando Backend (FastAPI) na porta 8000...")
    backend = start_backend()
    processes.append(backend)

    time.sleep(2)

    print("[IA Juridica] Iniciando Frontend (Flask) na porta 5000...")
    frontend = start_frontend()
    processes.append(frontend)

    print("\n" + "=" * 55)
    print("  Sistema iniciado com sucesso!")
    print("")
    print("  Frontend:  http://localhost:5000")
    print("  Backend:   http://localhost:8000")
    print("  API Docs:  http://localhost:8000/docs")
    print("")
    print("  Credenciais padrao:")
    print("    Email: advogado@iajuridica.com.br")
    print("    Senha: senha123")
    print("")
    print("  Pressione Ctrl+C para parar")
    print("=" * 55 + "\n")

    # 3. Aguardar e lidar com shutdown
    def shutdown(sig=None, frame=None):
        print("\n[IA Juridica] Encerrando...")
        for proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        print("[IA Juridica] Encerrado.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, shutdown)

    try:
        # No Windows, signal.pause() nao existe
        while True:
            for proc in processes:
                if proc.poll() is not None:
                    print(f"[AVISO] Processo {proc.pid} encerrou inesperadamente.")
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
