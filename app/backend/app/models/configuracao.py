"""
Modelo de Configuração - Chave/Valor
"""

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from app.core.database import Base, TimestampMixin


class Configuracao(Base, TimestampMixin):
    """Configurações do sistema em formato chave-valor"""

    __tablename__ = "configuracoes"

    id = Column(Integer, primary_key=True, index=True)
    chave = Column(String(255), unique=True, nullable=False, index=True)
    valor = Column(Text, nullable=True)
    descricao = Column(String(500), nullable=True)
