"""
Modelo de Audit Log - Compliance e Rastreabilidade
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AuditLog(Base):
    """Log de auditoria imutável para compliance jurídico"""
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Timestamp (imutável)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Usuário
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    usuario_email = Column(String(255), nullable=True)  # Redundância para casos de exclusão
    usuario_ip = Column(String(45), nullable=True)
    
    # Ação
    acao = Column(String(100), nullable=False, index=True)
    modulo = Column(String(100), nullable=False, index=True)
    
    # Detalhes
    descricao = Column(Text, nullable=True)
    
    # Request/Response
    endpoint = Column(String(255), nullable=True)
    metodo_http = Column(String(10), nullable=True)
    request_data = Column(JSON, nullable=True)  # Dados da requisição (sanitizados)
    response_status = Column(Integer, nullable=True)
    
    # IA específico
    prompt = Column(Text, nullable=True)
    resposta_ia = Column(Text, nullable=True)
    fontes_usadas = Column(JSON, nullable=True)
    modelo_ia = Column(String(100), nullable=True)
    tokens_usados = Column(Integer, nullable=True)
    confianca = Column(Integer, nullable=True)  # 0-100
    
    # Entidade afetada
    entidade_tipo = Column(String(100), nullable=True)  # processo, peticao, etc.
    entidade_id = Column(Integer, nullable=True)
    
    # Metadados extras
    extras = Column(JSON, nullable=True)
    
    # Relacionamento
    usuario = relationship("Usuario", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, acao='{self.acao}', timestamp='{self.timestamp}')>"


class AcaoAudit:
    """Constantes de ações para auditoria"""
    
    # Autenticação
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FALHA = "login_falha"
    
    # Usuários
    USUARIO_CRIAR = "usuario_criar"
    USUARIO_EDITAR = "usuario_editar"
    USUARIO_DESATIVAR = "usuario_desativar"
    
    # Processos
    PROCESSO_CONSULTAR = "processo_consultar"
    PROCESSO_CRIAR = "processo_criar"
    PROCESSO_CNJ_SYNC = "processo_cnj_sync"
    
    # Petições
    PETICAO_CRIAR = "peticao_criar"
    PETICAO_EDITAR = "peticao_editar"
    PETICAO_GERAR_IA = "peticao_gerar_ia"
    PETICAO_EXPORTAR = "peticao_exportar"
    
    # RAG
    RAG_PESQUISA = "rag_pesquisa"
    RAG_INDEXAR = "rag_indexar"
    
    # IA
    IA_CONSULTA = "ia_consulta"
    IA_ANALISE = "ia_analise"
    IA_GERACAO = "ia_geracao"
    
    # MCP
    MCP_EXECUTAR = "mcp_executar"
    MCP_FERRAMENTA = "mcp_ferramenta"
    
    # Documentos
    DOC_UPLOAD = "doc_upload"
    DOC_DOWNLOAD = "doc_download"
    DOC_CONVERTER = "doc_converter"
    
    # Clientes
    CLIENTE_CRIAR = "cliente_criar"
    CLIENTE_EDITAR = "cliente_editar"
    CLIENTE_LGPD_ACEITE = "cliente_lgpd_aceite"
    
    # Sistema
    SISTEMA_CONFIG = "sistema_config"
    SISTEMA_LIMPEZA = "sistema_limpeza"

class ModuloAudit:
    """Módulos do sistema para auditoria"""
    AUTH = "auth"
    USUARIOS = "usuarios"
    PROCESSOS = "processos"
    PROCESSO = "processos"
    PETICOES = "peticoes"
    PETICAO = "peticoes"
    RAG = "rag"
    IA = "ia"
    MCP = "mcp"
    DOCUMENTO = "documentos"
    DOCUMENTOS = "documentos"
    CLIENTES = "clientes"
    CNJ = "cnj"
    ADMIN = "admin"
    SISTEMA = "sistema"