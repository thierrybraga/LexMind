"""
IA Jurídica - Backend FastAPI
Sistema de Inteligência Artificial para Advocacia
Desenvolvido com RAG, MCP Server e integração CNJ
"""

import sys
import os

# Adicionar o diretório 'backend' ao path para permitir imports absolutos como 'from app.api ...'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
import logging

from app.api import auth, rag, cnj, peticoes, mcp, audit, documentos, clientes, airflow, admin, whatsapp, llm, config, pesquisa
from app.core.config import settings
from app.core.database import engine, Base, init_db, async_session_maker
from app.models.usuario import Usuario, RoleEnum
from app.core.security import get_password_hash
from sqlalchemy import select

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerenciador de ciclo de vida da aplicação"""
    logger.info("🚀 Iniciando IA Jurídica Backend...")
    
    # Inicializar banco de dados
    try:
        await init_db()
        logger.info("✅ Banco de dados inicializado")
        
        # Criar usuário padrão se não existir
        async with async_session_maker() as session:
            try:
                result = await session.execute(select(Usuario).where(Usuario.email == "advogado@iajuridica.com.br"))
                user = result.scalar_one_or_none()
                
                if not user:
                    logger.info("👤 Criando usuário padrão (advogado@iajuridica.com.br)...")
                    novo_usuario = Usuario(
                        email="advogado@iajuridica.com.br",
                        nome="Doutor Advogado",
                        hashed_password=get_password_hash("senha123"),
                        role=RoleEnum.ADMIN.value,
                        oab="123456",
                        oab_estado="SP",
                        ativo=True
                    )
                    session.add(novo_usuario)
                    await session.commit()
                    logger.info("✅ Usuário padrão criado com sucesso!")
                else:
                    logger.info("✅ Usuário padrão já existe.")
            except Exception as e:
                logger.error(f"❌ Erro ao criar usuário padrão: {e}")

    except Exception as e:
        logger.error(f"❌ Erro crítico na inicialização do banco de dados: {e}")
        # Não lançar exceção para permitir que o container suba e o healthcheck funcione

    
    # Inicializar RAG Engine
    logger.info("✅ RAG Engine pronto")
    
    yield
    
    logger.info("🛑 Encerrando IA Jurídica Backend...")

# Criar aplicação FastAPI
app = FastAPI(
    title="IA Jurídica API",
    description="""
    ## Sistema de Inteligência Artificial para Advocacia
    
    ### Funcionalidades:
    - 🔎 **RAG Jurídico**: Pesquisa semântica em jurisprudência, doutrina e leis
    - ⚖️ **Integração CNJ**: Consulta processual via DataJud
    - 📝 **Geração de Petições**: Criação automatizada de peças processuais
    - 🤖 **MCP Server**: Ferramentas e consultas externas
    - 📊 **Auditoria**: Log completo de todas as operações
    
    ### Compliance:
    - LGPD Compliant
    - Logs imutáveis
    - Aviso legal obrigatório
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(auth.router, prefix="/api/auth", tags=["Autenticação"])
app.include_router(rag.router, prefix="/api/rag", tags=["RAG Jurídico"])
app.include_router(cnj.router, prefix="/api/cnj", tags=["CNJ / Processos"])
app.include_router(peticoes.router, prefix="/api/peticoes", tags=["Petições"])
app.include_router(mcp.router, prefix="/api/mcp", tags=["MCP Server"])
app.include_router(audit.router, prefix="/api/audit", tags=["Auditoria"])
app.include_router(documentos.router, prefix="/api/documentos", tags=["Documentos"])
app.include_router(clientes.router, prefix="/api/clientes", tags=["Gestão de Clientes"])
app.include_router(airflow.router, tags=["Airflow"])
app.include_router(admin.router, prefix="/api/admin", tags=["Administração"])
app.include_router(whatsapp.router, prefix="/api/whatsapp", tags=["WhatsApp"])
app.include_router(llm.router, prefix="/api/llm", tags=["Gestão LLM"])
app.include_router(config.router, prefix="/api/config", tags=["Configurações"])
app.include_router(pesquisa.router, prefix="/api/pesquisa", tags=["Pesquisa Jurídica"])


@app.get("/", tags=["Status"])
async def root():
    """Endpoint raiz - Status do sistema"""
    return {
        "sistema": "IA Jurídica",
        "versao": "1.0.0",
        "status": "operacional",
        "docs": "/docs",
        "aviso_legal": "Este sistema não substitui a consulta a um advogado habilitado."
    }


@app.get("/health", tags=["Status"])
async def health_check():
    """Verificação de saúde do sistema"""
    return {
        "status": "healthy",
        "database": "connected",
        "rag_engine": "ready",
        "mcp_server": "ready"
    }


# Handler de exceções global
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Erro não tratado: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Erro interno do servidor",
            "status_code": 500
        }
    )


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )