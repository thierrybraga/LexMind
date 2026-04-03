"""
Modelo de Cliente e Atendimento
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Enum as SqlEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base, TimestampMixin


class StatusAtendimentoEnum(str, enum.Enum):
    PENDENTE = "pendente"
    EM_ANDAMENTO = "em_andamento"
    AGUARDANDO_CLIENTE = "aguardando_cliente"
    CONCLUIDO = "concluido"
    CANCELADO = "cancelado"


class Cliente(Base, TimestampMixin):
    """Modelo de cliente do escritório"""
    
    __tablename__ = "clientes"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Identificação
    nome = Column(String(255), nullable=False, index=True)
    cpf = Column(String(14), unique=True, index=True, nullable=True)
    rg = Column(String(20), nullable=True)
    data_nascimento = Column(DateTime, nullable=True)
    
    # Contato
    email = Column(String(255), nullable=True)
    telefone = Column(String(20), nullable=True)
    celular = Column(String(20), nullable=True)
    
    # Endereço
    endereco = Column(Text, nullable=True)
    cidade = Column(String(100), nullable=True)
    estado = Column(String(2), nullable=True)
    cep = Column(String(10), nullable=True)
    
    # Dados Profissionais
    profissao = Column(String(100), nullable=True)
    estado_civil = Column(String(20), nullable=True)
    nacionalidade = Column(String(50), default="Brasileira")
    
    # Status
    ativo = Column(Boolean, default=True)
    observacoes = Column(Text, nullable=True)
    
    # LGPD
    aceite_lgpd = Column(Boolean, default=False)
    data_aceite_lgpd = Column(DateTime, nullable=True)
    
    # Relacionamentos
    atendimentos = relationship("Atendimento", back_populates="cliente")
    agendamentos = relationship("Agendamento", back_populates="cliente")
    mensagens = relationship("Mensagem", back_populates="cliente")
    # processos = relationship("Processo", back_populates="cliente") # Future linkage
    
    def __repr__(self):
        return f"<Cliente(id={self.id}, nome='{self.nome}', cpf='{self.cpf}')>"


class Atendimento(Base, TimestampMixin):
    """Registro de atendimento ao cliente"""
    
    __tablename__ = "atendimentos"
    
    id = Column(Integer, primary_key=True, index=True)
    
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    advogado_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    
    # Detalhes
    assunto = Column(String(255), nullable=False)
    descricao = Column(Text, nullable=True)
    tipo = Column(String(50), default="consulta") # consulta, retorno, etc.
    
    # Status
    status = Column(String(50), default=StatusAtendimentoEnum.PENDENTE.value)
    
    # Tempo
    data_inicio = Column(DateTime(timezone=True), default=func.now())
    data_fim = Column(DateTime(timezone=True), nullable=True)
    duracao_minutos = Column(Integer, nullable=True)
    
    # Resultado
    resultado = Column(Text, nullable=True)
    proximos_passos = Column(Text, nullable=True)
    
    # Relacionamentos
    cliente = relationship("Cliente", back_populates="atendimentos")
    advogado = relationship("Usuario")
    mensagens = relationship("Mensagem", back_populates="atendimento")
    
    def __repr__(self):
        return f"<Atendimento(id={self.id}, cliente='{self.cliente_id}', status='{self.status}')>"


class Agendamento(Base, TimestampMixin):
    """Agendamento de reuniões ou prazos com cliente"""
    
    __tablename__ = "agendamentos"
    
    id = Column(Integer, primary_key=True, index=True)
    
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    responsavel_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    
    titulo = Column(String(255), nullable=False)
    descricao = Column(Text, nullable=True)
    
    data_hora = Column(DateTime(timezone=True), nullable=False)
    local = Column(String(255), nullable=True) # Online, Escritório, Tribunal
    link_reuniao = Column(String(500), nullable=True)
    
    status = Column(String(50), default="agendado") # agendado, realizado, cancelado, reagendado
    
    # Lembretes
    enviar_lembrete = Column(Boolean, default=True)
    lembrete_enviado = Column(Boolean, default=False)
    
    # Relacionamentos
    cliente = relationship("Cliente", back_populates="agendamentos")
    responsavel = relationship("Usuario")

    def __repr__(self):
        return f"<Agendamento(id={self.id}, data='{self.data_hora}', status='{self.status}')>"