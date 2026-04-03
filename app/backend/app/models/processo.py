"""
Modelo de Processo Judicial
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base, TimestampMixin


class Processo(Base, TimestampMixin):
    """Modelo de processo judicial"""
    
    __tablename__ = "processos"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Identificação do processo
    numero_cnj = Column(String(25), unique=True, index=True, nullable=False)
    numero_antigo = Column(String(50), nullable=True)  # Numeração anterior
    
    # Informações processuais
    classe = Column(String(255), nullable=True)  # Ex: Ação Civil Pública
    assunto = Column(String(255), nullable=True)
    comarca = Column(String(100), nullable=True)
    vara = Column(String(100), nullable=True)
    tribunal = Column(String(50), nullable=True)  # Ex: TJSP, STJ
    
    # Partes
    polo_ativo = Column(Text, nullable=True)  # JSON com partes autoras
    polo_passivo = Column(Text, nullable=True)  # JSON com partes rés
    
    # Status
    status = Column(String(50), default="ativo")  # ativo, arquivado, suspenso
    fase = Column(String(100), nullable=True)  # Fase processual atual
    ultima_movimentacao = Column(DateTime(timezone=True), nullable=True)
    
    # Valores
    valor_causa = Column(String(50), nullable=True)
    
    # Dados extras do CNJ
    dados_cnj = Column(JSON, nullable=True)  # Dados completos do DataJud
    
    # Controle interno
    responsavel_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    favorito = Column(Boolean, default=False)
    notas = Column(Text, nullable=True)
    
    # Relacionamentos
    responsavel = relationship("Usuario", back_populates="processos")
    peticoes = relationship("Peticao", back_populates="processo")
    movimentacoes = relationship("Movimentacao", back_populates="processo", order_by="desc(Movimentacao.data)")
    
    def __repr__(self):
        return f"<Processo(id={self.id}, numero='{self.numero_cnj}')>"


class Movimentacao(Base):
    """Movimentações do processo"""
    
    __tablename__ = "movimentacoes"
    
    id = Column(Integer, primary_key=True, index=True)
    processo_id = Column(Integer, ForeignKey("processos.id"), nullable=False)
    
    data = Column(DateTime(timezone=True), nullable=False)
    descricao = Column(Text, nullable=False)
    tipo = Column(String(100), nullable=True)
    
    # Dados extras
    dados_extras = Column(JSON, nullable=True)
    
    # Relacionamento
    processo = relationship("Processo", back_populates="movimentacoes")
    
    def __repr__(self):
        return f"<Movimentacao(id={self.id}, data='{self.data}')>"
