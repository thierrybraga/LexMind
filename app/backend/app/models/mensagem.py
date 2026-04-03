"""
Modelo de Mensagem (WhatsApp/Chat)
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SqlEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base, TimestampMixin


class RemetenteEnum(str, enum.Enum):
    CLIENTE = "cliente"
    IA = "ia"
    ADVOGADO = "advogado"
    SISTEMA = "sistema"


class TipoMensagemEnum(str, enum.Enum):
    TEXTO = "text"
    IMAGEM = "image"
    AUDIO = "audio"
    DOCUMENTO = "document"
    OUTRO = "other"


class Mensagem(Base, TimestampMixin):
    """Registro de mensagem trocada via WhatsApp ou Chat"""

    __tablename__ = "mensagens"

    id = Column(Integer, primary_key=True, index=True)

    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    atendimento_id = Column(Integer, ForeignKey("atendimentos.id"), nullable=True)

    # Identificadores externos
    whatsapp_id = Column(String(255), nullable=True, index=True)
    remote_jid = Column(String(50), nullable=True, index=True)

    # Conteúdo
    remetente = Column(String(20), default=RemetenteEnum.CLIENTE.value)
    tipo = Column(String(20), default=TipoMensagemEnum.TEXTO.value)
    conteudo = Column(Text, nullable=True)
    media_url = Column(String(500), nullable=True)

    # Status
    status = Column(String(20), default="recebida")

    # Relacionamentos
    cliente = relationship("Cliente", back_populates="mensagens")
    atendimento = relationship("Atendimento", back_populates="mensagens")

    def __repr__(self):
        return f"<Mensagem(id={self.id}, remetente='{self.remetente}', data='{self.created_at}')>"
