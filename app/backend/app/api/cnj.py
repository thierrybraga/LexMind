"""
API de Integração com CNJ - DataJud
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import httpx
import re

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.core.config import settings
from app.models.usuario import Usuario
from app.models.processo import Processo, Movimentacao
from app.models.configuracao import Configuracao
from app.models.audit_log import AuditLog, AcaoAudit, ModuloAudit
from app.schemas.schemas import (
    CNJConsultaRequest,
    CNJConsultaResponse,
    ProcessoResponse,
    ProcessoCreate
)
from app.services.cnj_service import CNJService, get_cnj_service

router = APIRouter()


def validar_numero_cnj(numero: str) -> bool:
    """Valida formato do número CNJ"""
    # Formato: NNNNNNN-DD.AAAA.J.TR.OOOO
    padrao = r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$"
    return bool(re.match(padrao, numero))


@router.post("/processo", response_model=CNJConsultaResponse)
async def consultar_processo_cnj(
    request: Request,
    consulta: CNJConsultaRequest,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    cnj_service: CNJService = Depends(get_cnj_service)
):
    """
    Consulta processo no CNJ DataJud
    
    Retorna dados completos do processo incluindo movimentações.
    """
    # Validar formato
    if not validar_numero_cnj(consulta.numero_processo):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de número de processo inválido. Use: NNNNNNN-DD.AAAA.J.TR.OOOO"
        )
    
    # Consultar CNJ
    try:
        # Buscar chave na configuração
        result = await db.execute(select(Configuracao).where(Configuracao.chave == "CNJ_API_KEY"))
        config = result.scalar_one_or_none()
        api_key = config.valor if config else None

        dados = await cnj_service.consultar_processo(consulta.numero_processo, api_key=api_key)
    except ValueError as e:
        # Processo não encontrado na base do DataJud
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erro ao consultar CNJ: {str(e)}"
        )
    
    # Log de auditoria
    log = AuditLog(
        acao=AcaoAudit.PROCESSO_CNJ_SYNC,
        modulo=ModuloAudit.CNJ,
        usuario_id=current_user.id,
        usuario_email=current_user.email,
        descricao=f"Consulta CNJ: {consulta.numero_processo}",
        usuario_ip=request.client.host
    )
    db.add(log)
    await db.commit()
    
    return CNJConsultaResponse(**dados)


@router.post("/processo/salvar", response_model=ProcessoResponse)
async def salvar_processo(
    request: Request,
    processo_data: ProcessoCreate,
    sync_cnj: bool = True,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    cnj_service: CNJService = Depends(get_cnj_service)
):
    """
    Salva processo no banco de dados local
    
    Opcionalmente sincroniza com CNJ para obter dados atualizados.
    """
    # Verificar se processo já existe
    result = await db.execute(
        select(Processo).where(Processo.numero_cnj == processo_data.numero_cnj)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Processo já cadastrado"
        )
    
    # Dados base
    dados_processo = processo_data.model_dump(exclude={"area_direito", "autor", "reu", "data_distribuicao", "observacoes"})
    dados_processo["responsavel_id"] = current_user.id
    
    # Mapeamento manual de campos do frontend
    if processo_data.autor:
        dados_processo["polo_ativo"] = processo_data.autor
    if processo_data.reu:
        dados_processo["polo_passivo"] = processo_data.reu
    if processo_data.observacoes:
        dados_processo["notas"] = processo_data.observacoes
    if processo_data.area_direito:
        # Se assunto estiver vazio, usa area_direito
        if not dados_processo.get("assunto"):
            dados_processo["assunto"] = processo_data.area_direito
            
    # Sincronizar com CNJ se solicitado
    if sync_cnj:
        try:
            dados_cnj = await cnj_service.consultar_processo(processo_data.numero_cnj)
            dados_processo.update({
                "classe": dados_cnj.get("classe"),
                "assunto": dados_cnj.get("assunto"),
                "comarca": dados_cnj.get("comarca"),
                "vara": dados_cnj.get("vara"),
                "tribunal": dados_cnj.get("tribunal"),
                "polo_ativo": str(dados_cnj.get("polo_ativo", [])),
                "polo_passivo": str(dados_cnj.get("polo_passivo", [])),
                "dados_cnj": dados_cnj.get("dados_completos")
            })
        except Exception as e:
            # Continua mesmo se CNJ falhar
            pass
    
    # Criar processo
    processo = Processo(**dados_processo)
    db.add(processo)
    await db.commit()
    await db.refresh(processo)
    
    # Log de auditoria
    log = AuditLog(
        acao=AcaoAudit.PROCESSO_CRIAR,
        modulo=ModuloAudit.PROCESSO,
        usuario_id=current_user.id,
        usuario_email=current_user.email,
        descricao=f"Processo criado: {processo_data.numero_cnj}",
        entidade_tipo="processo",
        entidade_id=processo.id,
        usuario_ip=request.client.host
    )
    db.add(log)
    await db.commit()
    
    return ProcessoResponse.model_validate(processo)


@router.get("/processos")
async def listar_processos(
    tribunal: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista processos salvos do usuário.
    Retorna {processos: [...], total: int} para consumo pelo frontend.
    """
    from sqlalchemy import func as sa_func

    base_query = select(Processo).where(Processo.responsavel_id == current_user.id)

    if tribunal:
        base_query = base_query.where(Processo.tribunal == tribunal)
    if status:
        base_query = base_query.where(Processo.status == status)

    # Total
    count_q = select(sa_func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Paginar
    base_query = base_query.offset(skip).limit(limit).order_by(Processo.updated_at.desc())
    result = await db.execute(base_query)
    processos = result.scalars().all()

    return {
        "processos": [ProcessoResponse.model_validate(p).model_dump(mode="json") for p in processos],
        "total": total
    }


@router.get("/processo-by-id/{id}", response_model=ProcessoResponse)
async def get_processo_by_id(
    id: int,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna detalhes de um processo por ID numérico
    """
    result = await db.execute(
        select(Processo).where(
            Processo.id == id,
            Processo.responsavel_id == current_user.id
        )
    )
    processo = result.scalar_one_or_none()

    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado"
        )

    return ProcessoResponse.model_validate(processo)


@router.get("/processo/{numero_cnj}", response_model=ProcessoResponse)
async def get_processo(
    numero_cnj: str,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna detalhes de um processo salvo por número CNJ
    """
    result = await db.execute(
        select(Processo).where(Processo.numero_cnj == numero_cnj)
    )
    processo = result.scalar_one_or_none()
    
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado"
        )
    
    return ProcessoResponse.model_validate(processo)


@router.post("/processo/{numero_cnj}/sync")
async def sync_processo(
    numero_cnj: str,
    request: Request,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    cnj_service: CNJService = Depends(get_cnj_service)
):
    """
    Sincroniza processo com CNJ (atualiza movimentações)
    """
    # Buscar processo local
    result = await db.execute(
        select(Processo).where(Processo.numero_cnj == numero_cnj)
    )
    processo = result.scalar_one_or_none()
    
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado localmente"
        )
    
    # Consultar CNJ
    dados_cnj = await cnj_service.consultar_processo(numero_cnj)
    
    # Atualizar dados
    processo.fase = dados_cnj.get("status")
    processo.dados_cnj = dados_cnj.get("dados_completos")
    
    # Adicionar novas movimentações
    for mov in dados_cnj.get("movimentacoes", []):
        # Verificar se já existe
        existing = await db.execute(
            select(Movimentacao).where(
                Movimentacao.processo_id == processo.id,
                Movimentacao.data == mov.get("data"),
                Movimentacao.descricao == mov.get("descricao")
            )
        )
        if not existing.scalar_one_or_none():
            nova_mov = Movimentacao(
                processo_id=processo.id,
                data=mov.get("data"),
                descricao=mov.get("descricao"),
                tipo=mov.get("tipo")
            )
            db.add(nova_mov)
    
    await db.commit()
    
    return {"message": "Processo sincronizado com sucesso"}


@router.get("/processo/{numero_cnj}/movimentacoes")
async def get_movimentacoes(
    numero_cnj: str,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna movimentações de um processo
    """
    result = await db.execute(
        select(Processo).where(Processo.numero_cnj == numero_cnj)
    )
    processo = result.scalar_one_or_none()
    
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado"
        )
    
    result = await db.execute(
        select(Movimentacao)
        .where(Movimentacao.processo_id == processo.id)
        .order_by(Movimentacao.data.desc())
    )
    movimentacoes = result.scalars().all()
    
    return [
        {
            "id": m.id,
            "data": m.data,
            "descricao": m.descricao,
            "tipo": m.tipo
        }
        for m in movimentacoes
    ]
