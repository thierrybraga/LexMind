"""
Modelo de Jurisprudência
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float, Boolean
from sqlalchemy.sql import func

from app.core.database import Base, TimestampMixin


class Jurisprudencia(Base, TimestampMixin):
    """Modelo de jurisprudência para RAG"""
    
    __tablename__ = "jurisprudencias"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Identificação
    numero = Column(String(100), index=True, nullable=True)  # Ex: REsp 123456
    tipo_recurso = Column(String(100), nullable=True)  # REsp, HC, AgRg, etc.
    
    # Tribunal e julgamento
    tribunal = Column(String(50), index=True, nullable=False)  # STF, STJ, TJSP
    orgao_julgador = Column(String(100), nullable=True)  # 1ª Turma, Plenário
    relator = Column(String(255), nullable=True)
    data_julgamento = Column(DateTime, nullable=True)
    data_publicacao = Column(DateTime, nullable=True)
    
    # Conteúdo
    ementa = Column(Text, nullable=False)
    ementa_resumida = Column(Text, nullable=True)
    inteiro_teor = Column(Text, nullable=True)
    
    # Classificação
    assuntos = Column(JSON, nullable=True)  # Lista de assuntos
    area_direito = Column(String(100), nullable=True)  # Penal, Civil, Trabalhista
    
    # Teses
    tese_principal = Column(Text, nullable=True)
    teses_secundarias = Column(JSON, nullable=True)
    
    # RAG - Embeddings
    embedding_id = Column(String(100), nullable=True)  # ID no vector store
    chunk_ids = Column(JSON, nullable=True)  # IDs dos chunks
    
    # Metadados de indexação
    fonte = Column(String(100), nullable=True)  # DataJud, site tribunal
    url_original = Column(String(500), nullable=True)
    hash_conteudo = Column(String(64), nullable=True)  # Para detectar duplicatas
    
    # Relevância
    citacoes_count = Column(Integer, default=0)  # Quantas vezes foi citada
    score_relevancia = Column(Float, default=0.0)
    
    def __repr__(self):
        return f"<Jurisprudencia(id={self.id}, numero='{self.numero}', tribunal='{self.tribunal}')>"


class Doutrina(Base, TimestampMixin):
    """Modelo de doutrina jurídica"""
    
    __tablename__ = "doutrinas"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Identificação
    titulo = Column(String(500), nullable=False)
    autor = Column(String(255), nullable=False)
    
    # Publicação
    editora = Column(String(255), nullable=True)
    ano_publicacao = Column(Integer, nullable=True)
    edicao = Column(String(50), nullable=True)
    isbn = Column(String(20), nullable=True)
    
    # Conteúdo
    resumo = Column(Text, nullable=True)
    capitulos = Column(JSON, nullable=True)
    
    # Classificação
    area_direito = Column(String(100), nullable=True)
    palavras_chave = Column(JSON, nullable=True)
    
    # RAG
    embedding_id = Column(String(100), nullable=True)
    chunk_ids = Column(JSON, nullable=True)
    
    # Arquivo
    arquivo_path = Column(String(500), nullable=True)
    
    def __repr__(self):
        return f"<Doutrina(id={self.id}, titulo='{self.titulo[:50]}')>"


class Legislacao(Base, TimestampMixin):
    """Modelo de legislação"""
    
    __tablename__ = "legislacoes"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Identificação
    tipo = Column(String(100), nullable=False)  # Lei, Decreto, MP, etc.
    numero = Column(String(50), nullable=False)
    ano = Column(Integer, nullable=False)
    
    # Descrição
    ementa = Column(Text, nullable=True)
    apelido = Column(String(255), nullable=True)  # Ex: "Código Civil"
    
    # Conteúdo
    texto_integral = Column(Text, nullable=True)
    
    # Status
    vigente = Column(Boolean, default=True)
    data_publicacao = Column(DateTime, nullable=True)
    data_revogacao = Column(DateTime, nullable=True)
    
    # RAG
    embedding_id = Column(String(100), nullable=True)
    chunk_ids = Column(JSON, nullable=True)
    
    # Fonte
    url_planalto = Column(String(500), nullable=True)
    
    @property
    def citacao_completa(self):
        return f"{self.tipo} nº {self.numero}/{self.ano}"
    
    def __repr__(self):
        return f"<Legislacao(id={self.id}, tipo='{self.tipo}', numero='{self.numero}')>"
