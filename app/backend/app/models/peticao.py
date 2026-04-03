"""
Modelo de Petição
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base, TimestampMixin


class TipoPeticaoEnum(str, enum.Enum):
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


class StatusPeticaoEnum(str, enum.Enum):
    RASCUNHO = "rascunho"
    EM_REVISAO = "em_revisao"
    FINALIZADA = "finalizada"
    PROTOCOLADA = "protocolada"


class Peticao(Base, TimestampMixin):
    """Modelo de petição jurídica"""
    
    __tablename__ = "peticoes"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Identificação
    titulo = Column(String(255), nullable=False)
    tipo = Column(String(50), default=TipoPeticaoEnum.OUTRO.value)
    
    # Vinculação
    processo_id = Column(Integer, ForeignKey("processos.id"), nullable=True)
    autor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    
    # Conteúdo
    conteudo = Column(Text, nullable=True)  # HTML/Markdown
    objetivo = Column(Text, nullable=True)
    
    # Status
    status = Column(String(20), default=StatusPeticaoEnum.RASCUNHO.value)
    
    # IA - Metadados da geração
    gerada_por_ia = Column(Boolean, default=False)
    prompt_usado = Column(Text, nullable=True)
    jurisprudencias_usadas = Column(JSON, nullable=True)  # IDs das jurisprudências
    fontes_usadas = Column(JSON, nullable=True)  # Lista de fontes citadas
    confianca_ia = Column(Integer, nullable=True)  # 0-100
    
    # Versionamento
    versao = Column(Integer, default=1)
    versao_anterior_id = Column(Integer, ForeignKey("peticoes.id"), nullable=True)
    
    # Arquivos
    arquivo_docx = Column(String(500), nullable=True)
    arquivo_pdf = Column(String(500), nullable=True)
    
    # Relacionamentos
    processo = relationship("Processo", back_populates="peticoes")
    autor = relationship("Usuario", back_populates="peticoes")
    versao_anterior = relationship("Peticao", remote_side=[id])
    
    def __repr__(self):
        return f"<Peticao(id={self.id}, titulo='{self.titulo}', tipo='{self.tipo}')>"


class TemplatePeticao(Base, TimestampMixin):
    """Templates de petições reutilizáveis"""
    
    __tablename__ = "templates_peticao"
    
    id = Column(Integer, primary_key=True, index=True)
    
    nome = Column(String(255), nullable=False)
    tipo = Column(String(50), nullable=False)
    descricao = Column(Text, nullable=True)
    
    conteudo = Column(Text, nullable=False)  # Template com placeholders
    
    # Metadados
    tribunal = Column(String(50), nullable=True)  # Se específico para tribunal
    area_direito = Column(String(100), nullable=True)
    
    # Controle
    ativo = Column(Boolean, default=True)
    uso_count = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<TemplatePeticao(id={self.id}, nome='{self.nome}')>"
