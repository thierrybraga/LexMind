"""
Modelos do Sistema IA Jurídica
"""

from app.models.usuario import Usuario, RoleEnum
from app.models.processo import Processo, Movimentacao
from app.models.peticao import Peticao, TemplatePeticao, TipoPeticaoEnum, StatusPeticaoEnum
from app.models.jurisprudencia import Jurisprudencia, Doutrina, Legislacao
from app.models.audit_log import AuditLog, AcaoAudit, ModuloAudit
from app.models.configuracao import Configuracao
from app.models.cliente import Cliente, Atendimento, Agendamento, StatusAtendimentoEnum
from app.models.mensagem import Mensagem, RemetenteEnum, TipoMensagemEnum

__all__ = [
    "Usuario",
    "RoleEnum",
    "Processo",
    "Movimentacao",
    "Peticao",
    "TemplatePeticao",
    "TipoPeticaoEnum",
    "StatusPeticaoEnum",
    "Jurisprudencia",
    "Doutrina",
    "Legislacao",
    "AuditLog",
    "AcaoAudit",
    "ModuloAudit",
    "Cliente",
    "Atendimento",
    "Agendamento",
    "StatusAtendimentoEnum",
    "Configuracao",
    "Mensagem",
    "RemetenteEnum",
    "TipoMensagemEnum"
]