"""
API de Auditoria - Logs e Compliance
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, delete
from typing import Optional, List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.security import get_current_active_user, require_role, Roles
from app.models.usuario import Usuario
from app.models.processo import Processo
from app.models.peticao import Peticao
from app.models.audit_log import AuditLog, AcaoAudit, ModuloAudit
from app.schemas.schemas import AuditLogResponse, AuditLogFilter

router = APIRouter()


# ─── Dashboard Stats (todos os usuários autenticados) ──────────────

@router.get("/dashboard-stats")
async def dashboard_stats(
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Estatísticas para o dashboard.
    Retorna contadores que o frontend espera:
    total_processos, total_peticoes, consultas_ia, consultas_cnj,
    atividades_recentes, ultimas_peticoes
    """
    # Processos do usuário
    total_processos = (await db.execute(
        select(func.count(Processo.id)).where(Processo.responsavel_id == current_user.id)
    )).scalar_one()

    # Petições do usuário
    total_peticoes = (await db.execute(
        select(func.count(Peticao.id)).where(Peticao.autor_id == current_user.id)
    )).scalar_one()

    # Consultas IA do usuário (últimos 30 dias)
    data_inicio = datetime.utcnow() - timedelta(days=30)
    consultas_ia = (await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.usuario_id == current_user.id,
            AuditLog.timestamp >= data_inicio,
            AuditLog.acao.in_([
                AcaoAudit.IA_CONSULTA,
                AcaoAudit.IA_GERACAO,
                AcaoAudit.PETICAO_GERAR_IA,
                AcaoAudit.RAG_PESQUISA
            ])
        )
    )).scalar_one()

    # Consultas CNJ do usuário (últimos 30 dias)
    consultas_cnj = (await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.usuario_id == current_user.id,
            AuditLog.timestamp >= data_inicio,
            AuditLog.modulo == ModuloAudit.CNJ
        )
    )).scalar_one()

    # ─── Atividades Recentes ───
    logs_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.usuario_id == current_user.id)
        .order_by(AuditLog.timestamp.desc())
        .limit(5)
    )
    logs = logs_result.scalars().all()
    
    atividades_recentes = []
    for log in logs:
        tipo = "outro"
        if "peticao" in log.acao:
            tipo = "peticao"
        elif "pesquisa" in log.acao or "rag" in log.acao:
            tipo = "pesquisa"
        elif "cnj" in log.modulo or "processo" in log.acao:
            tipo = "cnj"
            
        # Calcular tempo decorrido simples
        diff = datetime.utcnow() - log.timestamp.replace(tzinfo=None) if log.timestamp else timedelta(0)
        if diff.days > 0:
            tempo = f"há {diff.days} dias"
        elif diff.seconds > 3600:
            tempo = f"há {diff.seconds // 3600} horas"
        elif diff.seconds > 60:
            tempo = f"há {diff.seconds // 60} minutos"
        else:
            tempo = "agora mesmo"
            
        atividades_recentes.append({
            "tipo": tipo,
            "descricao": log.descricao or log.acao,
            "tempo": tempo
        })

    # ─── Últimas Petições ───
    peticoes_result = await db.execute(
        select(Peticao)
        .where(Peticao.autor_id == current_user.id)
        .order_by(Peticao.created_at.desc())
        .limit(5)
    )
    peticoes = peticoes_result.scalars().all()
    
    ultimas_peticoes = []
    for p in peticoes:
        status_color = "secondary"
        if p.status == "finalizada":
            status_color = "success"
        elif p.status == "em_revisao":
            status_color = "warning"
        elif p.status == "protocolada":
            status_color = "info"
            
        ultimas_peticoes.append({
            "id": p.id,
            "titulo": p.titulo,
            "tipo": p.tipo,
            "status_color": status_color,
            "criado_em": p.created_at.strftime("%d/%m/%Y") if p.created_at else ""
        })

    return {
        "total_processos": total_processos,
        "total_peticoes": total_peticoes,
        "consultas_ia": consultas_ia,
        "consultas_cnj": consultas_cnj,
        "atividades_recentes": atividades_recentes,
        "ultimas_peticoes": ultimas_peticoes
    }


# ─── Histórico IA ──────────────────────────────────────────────────

@router.get("/ia-historico")
async def ia_historico(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna histórico de consultas IA do usuário.
    Inclui RAG, geração de petições e consultas IA.
    """
    base_query = select(AuditLog).where(
        AuditLog.usuario_id == current_user.id,
        AuditLog.acao.in_([
            AcaoAudit.IA_CONSULTA,
            AcaoAudit.IA_GERACAO,
            AcaoAudit.IA_ANALISE,
            AcaoAudit.PETICAO_GERAR_IA,
            AcaoAudit.RAG_PESQUISA
        ])
    )

    # Total
    count_q = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Paginação
    offset = (page - 1) * limit
    base_query = base_query.offset(offset).limit(limit).order_by(AuditLog.timestamp.desc())

    result = await db.execute(base_query)
    logs = result.scalars().all()

    return {
        "logs": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "acao": log.acao,
                "descricao": log.descricao,
                "prompt": log.prompt,
                "fontes_usadas": log.fontes_usadas,
                "modelo_ia": log.modelo_ia,
                "confianca": log.confianca
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "limit": limit
    }


# ─── Logs de Auditoria ─────────────────────────────────────────────

@router.get("/logs")
async def listar_logs(
    usuario_id: Optional[int] = None,
    acao: Optional[str] = None,
    modulo: Optional[str] = None,
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    current_user: Usuario = Depends(require_role([Roles.ADMIN, Roles.ADVOGADO])),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista logs de auditoria.
    Admin: vê todos. Advogado: vê apenas os próprios.
    Retorna {logs: [...], total: int, page: int}
    """
    base_query = select(AuditLog)

    if current_user.role != Roles.ADMIN:
        base_query = base_query.where(AuditLog.usuario_id == current_user.id)
    elif usuario_id:
        base_query = base_query.where(AuditLog.usuario_id == usuario_id)

    if acao:
        base_query = base_query.where(AuditLog.acao == acao)
    if modulo:
        base_query = base_query.where(AuditLog.modulo == modulo)
    if data_inicio:
        base_query = base_query.where(AuditLog.timestamp >= data_inicio)
    if data_fim:
        base_query = base_query.where(AuditLog.timestamp <= data_fim)

    count_q = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    offset = (page - 1) * per_page
    base_query = base_query.offset(offset).limit(per_page).order_by(AuditLog.timestamp.desc())

    result = await db.execute(base_query)
    logs = result.scalars().all()

    return {
        "logs": [AuditLogResponse.model_validate(log).model_dump(mode="json") for log in logs],
        "total": total,
        "page": page
    }


@router.get("/logs/{id}", response_model=AuditLogResponse)
async def get_log(
    id: int,
    current_user: Usuario = Depends(require_role([Roles.ADMIN, Roles.ADVOGADO])),
    db: AsyncSession = Depends(get_db)
):
    """Retorna detalhes de um log específico"""
    query = select(AuditLog).where(AuditLog.id == id)

    if current_user.role != Roles.ADMIN:
        query = query.where(AuditLog.usuario_id == current_user.id)

    result = await db.execute(query)
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Log não encontrado"
        )

    return AuditLogResponse.model_validate(log)


# ─── Estatísticas Admin ────────────────────────────────────────────

@router.get("/estatisticas")
async def estatisticas_auditoria(
    dias: int = Query(30, ge=1, le=365),
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Estatísticas de auditoria.
    Admin: vê tudo. Outros: vê dashboard stats pessoais.
    """
    # Para não-admin, retornar apenas dashboard stats
    if current_user.role != Roles.ADMIN:
        return await dashboard_stats(current_user, db)

    data_inicio = datetime.utcnow() - timedelta(days=dias)

    # Total de logs por módulo
    result = await db.execute(
        select(AuditLog.modulo, func.count(AuditLog.id))
        .where(AuditLog.timestamp >= data_inicio)
        .group_by(AuditLog.modulo)
    )
    logs_por_modulo = dict(result.fetchall())

    # Total de logs por ação
    result = await db.execute(
        select(AuditLog.acao, func.count(AuditLog.id))
        .where(AuditLog.timestamp >= data_inicio)
        .group_by(AuditLog.acao)
    )
    logs_por_acao = dict(result.fetchall())

    # Usuários mais ativos
    result = await db.execute(
        select(AuditLog.usuario_email, func.count(AuditLog.id))
        .where(AuditLog.timestamp >= data_inicio)
        .group_by(AuditLog.usuario_email)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
    )
    usuarios_ativos = [
        {"email": row[0], "count": row[1]}
        for row in result.fetchall()
    ]

    # Consultas IA
    total_consultas_ia = (await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.timestamp >= data_inicio,
            AuditLog.acao.in_([
                AcaoAudit.IA_CONSULTA,
                AcaoAudit.IA_GERACAO,
                AcaoAudit.PETICAO_GERAR_IA
            ])
        )
    )).scalar() or 0

    # Média de confiança IA
    media_confianca = (await db.execute(
        select(func.avg(AuditLog.confianca)).where(
            AuditLog.timestamp >= data_inicio,
            AuditLog.confianca.isnot(None)
        )
    )).scalar() or 0

    # Totais globais para dashboard admin
    total_processos = (await db.execute(select(func.count(Processo.id)))).scalar_one()
    total_peticoes = (await db.execute(select(func.count(Peticao.id)))).scalar_one()

    return {
        "periodo_dias": dias,
        "total_processos": total_processos,
        "total_peticoes": total_peticoes,
        "consultas_ia": total_consultas_ia,
        "consultas_cnj": logs_por_modulo.get(ModuloAudit.CNJ, 0) if hasattr(ModuloAudit, 'CNJ') else 0,
        "logs_por_modulo": logs_por_modulo,
        "logs_por_acao": logs_por_acao,
        "usuarios_mais_ativos": usuarios_ativos,
        "total_consultas_ia": total_consultas_ia,
        "media_confianca_ia": round(media_confianca, 2)
    }


# ─── Filtros ────────────────────────────────────────────────────────

@router.get("/acoes")
async def listar_acoes():
    """Lista todas as ações possíveis para filtro"""
    return {
        "acoes": [
            {"valor": v, "descricao": v.replace("_", " ").title()}
            for v in dir(AcaoAudit)
            if not v.startswith("_")
        ]
    }


@router.get("/modulos")
async def listar_modulos():
    """Lista todos os módulos para filtro"""
    return {
        "modulos": [
            {"valor": v, "descricao": v.replace("_", " ").title()}
            for v in dir(ModuloAudit)
            if not v.startswith("_")
        ]
    }


@router.delete("/limpar", status_code=status.HTTP_204_NO_CONTENT)
async def limpar_logs(
    dias: int = Query(..., ge=30, description="Remover logs anteriores a X dias (min 30)"),
    current_user: Usuario = Depends(require_role([Roles.ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove logs de auditoria antigos.
    Apenas ADMIN. Mínimo 30 dias de retenção.
    """
    data_corte = datetime.utcnow() - timedelta(days=dias)
    
    # Executar deleção
    await db.execute(
        delete(AuditLog).where(AuditLog.timestamp < data_corte)
    )
    await db.commit()
    
    # Logar a própria ação de limpeza
    log = AuditLog(
        acao=AcaoAudit.SISTEMA_LIMPEZA,
        modulo=ModuloAudit.SISTEMA,
        usuario_id=current_user.id,
        usuario_email=current_user.email,
        descricao=f"Limpeza de logs anteriores a {dias} dias",
        usuario_ip=None
    )
    db.add(log)
    await db.commit()
    
    return None
