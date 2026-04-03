from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import func
from datetime import datetime
from typing import List

from app.core.database import get_db
from app.models.cliente import Cliente, Atendimento, Agendamento, StatusAtendimentoEnum
from app.schemas.cliente_schemas import (
    ClienteIntakeRequest,
    AdvogadoOutput,
    AgendamentoRequest,
    AgendamentoResponse
)
from app.services.ia_juridica import IAJuridicaService
from app.services.google_calendar import GoogleIntegrationService

router = APIRouter()
ia_service = IAJuridicaService()
google_service = GoogleIntegrationService()

@router.post("/intake", response_model=AdvogadoOutput)
async def intake_cliente(
    request: ClienteIntakeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Recebe dados do cliente, salva com compliance LGPD e processa via IA.
    """
    if not request.dados_pessoais.consentimento_lgpd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consentimento LGPD é obrigatório."
        )

    # 1. Salvar/Atualizar Cliente
    result = await db.execute(select(Cliente).where(Cliente.cpf == request.dados_pessoais.cpf))
    cliente = result.scalar_one_or_none()

    if not cliente:
        dt_nascimento = None
        if request.dados_pessoais.data_nascimento:
            try:
                dt_nascimento = datetime.fromisoformat(request.dados_pessoais.data_nascimento.replace('Z', '+00:00'))
            except ValueError:
                pass

        cliente = Cliente(
            nome=request.dados_pessoais.nome_completo,
            cpf=request.dados_pessoais.cpf,
            rg=request.dados_pessoais.rg,
            data_nascimento=dt_nascimento,
            endereco=request.dados_pessoais.endereco.rua,
            cidade=request.dados_pessoais.endereco.cidade,
            estado=request.dados_pessoais.endereco.estado,
            cep=request.dados_pessoais.endereco.cep,
            email=request.dados_pessoais.email,
            telefone=request.dados_pessoais.telefone,
            aceite_lgpd=True,
            data_aceite_lgpd=func.now()
        )
        db.add(cliente)
        await db.commit()
        await db.refresh(cliente)

    # 2. Processar via IA
    ia_output = await ia_service.processar_caso(request)

    # 3. Salvar Atendimento
    docs_str = ", ".join(request.dados_juridicos.documentos_anexos) if request.dados_juridicos.documentos_anexos else "Nenhum"
    descricao_completa = f"{request.dados_juridicos.relato_da_causa}\n\nDocumentos: {docs_str}"

    atendimento = Atendimento(
        cliente_id=cliente.id,
        assunto="Triagem Inicial - " + (request.dados_juridicos.relato_da_causa[:50] if request.dados_juridicos.relato_da_causa else "Novo Caso"),
        descricao=descricao_completa,
        resultado=f"Ação Sugerida: {ia_output.analise_juridica.acao_cabivel}. Status: Processado via IA.",
        status=StatusAtendimentoEnum.CONCLUIDO.value
    )
    db.add(atendimento)
    await db.commit()

    return ia_output


@router.post("/agendar", response_model=AgendamentoResponse)
async def agendar_reuniao(
    request: AgendamentoRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Agenda reunião no Google Calendar e envia convite.
    """
    result = await db.execute(select(Cliente).where(Cliente.id == request.cliente_id))
    cliente = result.scalar_one_or_none()

    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    # 1. Criar Evento Google Calendar
    evento = await google_service.criar_evento_agenda(
        titulo=f"Reunião Jurídica - {cliente.nome}",
        data_inicio=request.data_horario,
        emails_convidados=[cliente.email, request.advogado_email]
    )

    # 2. Salvar Agendamento
    dt_hora = None
    try:
        dt_hora = datetime.fromisoformat(request.data_horario.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        dt_hora = datetime.now()

    agendamento = Agendamento(
        cliente_id=cliente.id,
        titulo=f"Reunião Jurídica - {cliente.nome}",
        data_hora=dt_hora,
        link_reuniao=evento.get("link", ""),
        status="agendado"
    )
    db.add(agendamento)
    await db.commit()

    # 3. Enviar Email (Simulado)
    await google_service.enviar_email_confirmacao(
        para=cliente.email,
        assunto="Confirmação de Agendamento - IA Jurídica",
        corpo=f"Sua reunião foi agendada. Link: {evento.get('link', '')}"
    )

    return AgendamentoResponse(
        sucesso=True,
        mensagem="Agendamento realizado com sucesso",
        link_reuniao=evento.get("link", ""),
        evento_id=evento.get("id", "")
    )
