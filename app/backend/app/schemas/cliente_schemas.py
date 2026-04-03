from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any

# =======================
# INPUT DO CLIENTE
# =======================

class Endereco(BaseModel):
    rua: str
    cidade: str
    estado: str
    cep: str

class DadosPessoais(BaseModel):
    nome_completo: str
    cpf: str
    rg: str
    data_nascimento: str
    local_nascimento: str
    endereco: Endereco
    telefone: str
    email: EmailStr
    consentimento_lgpd: bool = Field(..., description="Obrigatório para processamento")

class DadosJuridicos(BaseModel):
    relato_da_causa: str
    documentos_anexos: List[str] = [] # Lista de nomes/urls temporários

class ClienteIntakeRequest(BaseModel):
    dados_pessoais: DadosPessoais
    dados_juridicos: DadosJuridicos

# =======================
# OUTPUT PARA ADVOGADO
# =======================

class ContatoAdv(BaseModel):
    email: str
    telefone: str

class ClienteResumo(BaseModel):
    nome: str
    cpf: str
    contato: ContatoAdv

class AnaliseJuridica(BaseModel):
    tipo_causa: str
    acao_cabivel: str
    competencia: str
    foro: str
    prazo_critico: str

class PecaSugerida(BaseModel):
    estrutura: List[str]

class AdvogadoOutput(BaseModel):
    cliente: ClienteResumo
    analise_juridica: AnaliseJuridica
    peca_sugerida: PecaSugerida
    alertas: List[str]

# =======================
# AGENDAMENTO
# =======================

class AgendamentoRequest(BaseModel):
    cliente_id: int
    data_horario: str  # ISO Format
    advogado_email: str

class AgendamentoResponse(BaseModel):
    sucesso: bool
    mensagem: str
    link_reuniao: Optional[str]
    evento_id: Optional[str]