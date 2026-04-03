"""
Configurações do Sistema IA Jurídica
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")


class Settings(BaseSettings):
    """Configurações globais da aplicação"""
    
    # Informações do App
    APP_NAME: str = "IA Jurídica"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # Segurança
    SECRET_KEY: str = "sua-chave-secreta-muito-segura-mude-em-producao"
    ALGORITHM: str = "HS256"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 horas
    JWT_EXPIRE_MINUTES: int = 1440
    
    # Database
    # Priorizar variável de ambiente; fallback para SQLite local
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{os.path.join(DATA_DIR, 'ia_juridica.db')}"
    )
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5000",
        "http://localhost:8000",
        "http://127.0.0.1:5000",
        "http://127.0.0.1:8000",
    ]
    
    # RAG Configuration
    VECTOR_DB_PATH: str = os.path.join(DATA_DIR, "vector_db")
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    TOP_K_RESULTS: int = 5
    
    # LLM Configuration
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.3
    LLM_TIMEOUT: int = 120

    # OpenAI Configuration (pesquisa jurídica avançada / deep research)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_SEARCH_MODEL: str = "gpt-4o-mini"
    
    # CNJ Configuration
    CNJ_API_URL: str = "https://api-publica.datajud.cnj.jus.br"
    CNJ_API_KEY: Optional[str] = None
    CNJ_TIMEOUT: int = 30
    
    # MCP Server
    MCP_ENABLED: bool = True
    MCP_ALLOWED_TOOLS: List[str] = [
        "buscar_jurisprudencia",
        "consultar_processo",
        "criar_documento",
        "converter_pdf",
        "buscar_lei"
    ]
    
    # Diretórios
    UPLOAD_DIR: str = os.path.join(DATA_DIR, "uploads")
    UPLOAD_PATH: str = os.path.join(DATA_DIR, "uploads")
    OUTPUT_DIR: str = os.path.join(DATA_DIR, "outputs")
    TEMPLATES_DIR: str = os.path.join(DATA_DIR, "templates")
    
    # Limites
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: str = "pdf,docx,doc,txt,odt,rtf"
    MAX_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_PERIOD: int = 60
    
    # Auditoria
    AUDIT_ENABLED: bool = True
    AUDIT_RETENTION_DAYS: int = 365
    AUDIT_LOG_FILE: str = os.path.join(LOGS_DIR, "audit.log")
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5000,http://127.0.0.1:3000"

    # Apache Airflow
    AIRFLOW_URL: str = "http://airflow-webserver:8080"
    AIRFLOW_USERNAME: str = "admin"
    AIRFLOW_PASSWORD: str = "admin"
    AIRFLOW_ENABLED: bool = True

    # WhatsApp (Evolution API)
    WHATSAPP_API_URL: str = "http://host.docker.internal:8083"
    WHATSAPP_API_KEY: str = "429683C4C977415CAAFCCE10F7D57E11"
    WHATSAPP_INSTANCE_NAME: str = "ia-juridica"
    WHATSAPP_WEBHOOK_SECRET: Optional[str] = None

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: str = os.path.join(LOGS_DIR, "app.log")
    
    class Config:
        env_file = os.path.join(BASE_DIR, ".env") if not os.getenv("DYNO") else None
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações"""
    return Settings()


settings = get_settings()


# Criar diretórios necessários
def setup_directories():
    """Cria diretórios necessários para o sistema"""
    dirs = [
        settings.UPLOAD_DIR,
        settings.OUTPUT_DIR,
        settings.TEMPLATES_DIR,
        settings.VECTOR_DB_PATH,
    ]
    for dir_path in dirs:
        try:
            os.makedirs(dir_path, exist_ok=True)
        except OSError as e:
            # Log error but don't crash the app during import
            print(f"WARNING: Could not create directory {dir_path}: {e}")

setup_directories()
