"""
Modelo de Usuário
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base, TimestampMixin


class RoleEnum(str, enum.Enum):
    ADMIN = "admin"
    ADVOGADO = "advogado"
    ESTAGIARIO = "estagiario"
    CLIENTE = "cliente"


class Usuario(Base, TimestampMixin):
    """Modelo de usuário do sistema"""
    
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    nome = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # Dados profissionais
    oab = Column(String(20), nullable=True)  # Número OAB
    oab_estado = Column(String(2), nullable=True)  # UF da OAB
    cpf = Column(String(14), nullable=True)
    telefone = Column(String(20), nullable=True)
    
    # Controle de acesso
    role = Column(String(20), default=RoleEnum.ADVOGADO.value, nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
    
    # Configurações
    limite_consultas_dia = Column(Integer, default=100)
    
    # Timestamps
    ultimo_acesso = Column(DateTime(timezone=True), nullable=True)
    
    # Relacionamentos
    peticoes = relationship("Peticao", back_populates="autor")
    processos = relationship("Processo", back_populates="responsavel")
    audit_logs = relationship("AuditLog", back_populates="usuario")
    
    def __repr__(self):
        return f"<Usuario(id={self.id}, email='{self.email}', role='{self.role}')>"
    
    @property
    def nome_completo(self):
        return self.nome
    
    @property
    def oab_completa(self):
        if self.oab and self.oab_estado:
            return f"OAB/{self.oab_estado} {self.oab}"
        return None
