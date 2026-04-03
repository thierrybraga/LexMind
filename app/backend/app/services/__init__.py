"""
Services - Camada de lógica de negócio
"""

from app.services.rag_engine import RAGEngine, get_rag_engine
from app.services.cnj_service import CNJService, get_cnj_service
from app.services.documento_service import DocumentoService, get_documento_service
from app.services.mcp_service import MCPService, get_mcp_service
from app.services.peticao_service import PeticaoService, get_peticao_service

__all__ = [
    "RAGEngine",
    "get_rag_engine",
    "CNJService", 
    "get_cnj_service",
    "DocumentoService",
    "get_documento_service",
    "MCPService",
    "get_mcp_service",
    "PeticaoService",
    "get_peticao_service",
]
