"""
Schemas de RAG e Pesquisa Jurídica
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============== RAG ==============

class TribunalEnum(str, Enum):
    STF = "STF"
    STJ = "STJ"
    TST = "TST"
    TSE = "TSE"
    STM = "STM"
    TRF1 = "TRF1"
    TRF2 = "TRF2"
    TRF3 = "TRF3"
    TRF4 = "TRF4"
    TRF5 = "TRF5"
    TJSP = "TJSP"
    TJRJ = "TJRJ"
    TJMG = "TJMG"
    TJRS = "TJRS"
    TJPR = "TJPR"
    OUTROS = "OUTROS"


class RAGSearchRequest(BaseModel):
    """Request de pesquisa RAG"""
    query: str = Field(..., min_length=3, description="Consulta jurídica")
    tribunal: Optional[str] = None
    area_direito: Optional[str] = None
    ano_inicio: Optional[int] = None
    ano_fim: Optional[int] = None
    tipo_fonte: Optional[str] = None  # jurisprudencia, doutrina, legislacao
    top_k: int = Field(default=5, ge=1, le=20)


class RAGResultItem(BaseModel):
    """Item de resultado RAG"""
    id: Any = 0
    tipo: str = "desconhecido"
    titulo: str = ""
    conteudo: str = ""
    fonte: str = ""
    tribunal: Optional[str] = None
    data: Optional[str] = None
    relevancia: float = 0.0
    metadata: Optional[Dict[str, Any]] = None


class RAGSearchResponse(BaseModel):
    """Response de pesquisa RAG"""
    query: str
    total_results: int
    results: List[RAGResultItem]
    tempo_busca: float
    fontes_consultadas: List[str]


# ============== Consulta IA ==============

class ConsultaIARequest(BaseModel):
    """Request para consulta IA"""
    pergunta: str = Field(..., description="Pergunta jurídica")
    search_query: Optional[str] = Field(None, description="Query específica para busca RAG")
    usar_rag: bool = True


class ConsultaIAResponse(BaseModel):
    """Response de consulta IA"""
    content: str
    tokens_used: int
    model: str
    sources_used: Optional[List[str]] = None
    confidence: float = 0.0


# ============== Processo ==============

class ProcessoCreate(BaseModel):
    """Criação de processo"""
    numero_cnj: str = Field(..., pattern=r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$")
    classe: Optional[str] = None
    assunto: Optional[str] = None
    comarca: Optional[str] = None
    vara: Optional[str] = None
    tribunal: Optional[str] = None
    area_direito: Optional[str] = None
    autor: Optional[str] = None
    reu: Optional[str] = None
    valor_causa: Optional[str] = None
    data_distribuicao: Optional[str] = None
    notas: Optional[str] = None
    observacoes: Optional[str] = None  # Alias for notes from frontend


class ProcessoResponse(BaseModel):
    """Response de processo"""
    id: int
    numero_cnj: str
    classe: Optional[str]
    assunto: Optional[str]
    comarca: Optional[str]
    vara: Optional[str]
    tribunal: Optional[str]
    polo_ativo: Optional[str]
    polo_passivo: Optional[str]
    status: str
    fase: Optional[str]
    ultima_movimentacao: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class MovimentacaoResponse(BaseModel):
    """Response de movimentação"""
    id: int
    data: datetime
    descricao: str
    tipo: Optional[str]
    
    class Config:
        from_attributes = True


# ============== CNJ ==============

class CNJConsultaRequest(BaseModel):
    """Request de consulta CNJ"""
    numero_processo: str = Field(..., description="Número do processo formato CNJ")


class CNJConsultaResponse(BaseModel):
    """Response de consulta CNJ"""
    numero_cnj: str
    classe: Optional[str]
    assunto: Optional[str]
    comarca: Optional[str]
    vara: Optional[str]
    tribunal: Optional[str]
    polo_ativo: List[str]
    polo_passivo: List[str]
    status: str
    valor_causa: Optional[str]
    data_distribuicao: Optional[datetime]
    movimentacoes: List[Dict[str, Any]]
    dados_completos: Dict[str, Any]


# ============== Petição ==============

class TipoPeticaoEnum(str, Enum):
    INICIAL = "inicial"
    CONTESTACAO = "contestacao"
    RECURSO = "recurso"
    HABEAS_CORPUS = "habeas_corpus"
    EMBARGOS = "embargos"
    AGRAVO = "agravo"
    APELACAO = "apelacao"
    PARECER = "parecer"
    MEMORIAIS = "memoriais"
    OUTRO = "outro"


class PeticaoGerarRequest(BaseModel):
    """Request para gerar petição via IA"""
    tipo: TipoPeticaoEnum
    processo_numero: Optional[str] = None
    objetivo: str = Field(..., min_length=10)
    jurisprudencia_ids: Optional[List[int]] = None
    contexto_adicional: Optional[str] = None
    estilo_tribunal: Optional[str] = "formal"


class PeticaoCreate(BaseModel):
    """Criação manual de petição"""
    titulo: str = Field(..., min_length=5)
    tipo: TipoPeticaoEnum
    processo_id: Optional[int] = None
    conteudo: str
    objetivo: Optional[str] = None


class PeticaoUpdate(BaseModel):
    """Atualização de petição"""
    titulo: Optional[str] = None
    conteudo: Optional[str] = None
    status: Optional[str] = None


class PeticaoExportarRequest(BaseModel):
    """Request para exportar conteúdo de petição"""
    conteudo: str = Field(..., min_length=10)
    titulo: str = "Petição Exportada"
    tipo: Optional[str] = "peticao"


class PeticaoResponse(BaseModel):
    """Response de petição"""
    id: int
    titulo: str
    tipo: str
    processo_id: Optional[int]
    conteudo: Optional[str]
    objetivo: Optional[str]
    status: str
    gerada_por_ia: bool
    fontes_usadas: Optional[List[str]]
    confianca_ia: Optional[int]
    versao: int
    arquivo_docx: Optional[str]
    arquivo_pdf: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PeticaoGerarResponse(BaseModel):
    """Response de geração de petição"""
    peticao: PeticaoResponse
    fontes_utilizadas: List[Dict[str, Any]]
    confianca: float
    avisos: List[str]


# ============== MCP ==============

class MCPExecuteRequest(BaseModel):
    """Request para executar ferramenta MCP"""
    tool: str = Field(..., description="Nome da ferramenta")
    params: Dict[str, Any] = Field(default_factory=dict)


class MCPExecuteResponse(BaseModel):
    """Response de execução MCP"""
    tool: str
    success: bool
    result: Any
    error: Optional[str]
    execution_time: float


# ============== Auditoria ==============

class AuditLogResponse(BaseModel):
    """Response de log de auditoria"""
    id: int
    timestamp: datetime
    usuario_email: Optional[str]
    acao: str
    modulo: str
    descricao: Optional[str]
    prompt: Optional[str]
    fontes_usadas: Optional[List[str]]
    modelo_ia: Optional[str]
    
    class Config:
        from_attributes = True


class AuditLogFilter(BaseModel):
    """Filtros para logs de auditoria"""
    usuario_id: Optional[int] = None
    acao: Optional[str] = None
    modulo: Optional[str] = None
    data_inicio: Optional[datetime] = None
    data_fim: Optional[datetime] = None
    page: int = 1
    per_page: int = 50
