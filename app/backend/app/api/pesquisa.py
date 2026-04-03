"""
API de Pesquisa Jurídica Avançada

Endpoints para pesquisa unificada em múltiplas fontes:
- STF, STJ, TST
- CNJ DataJud (Tribunais Estaduais)
- LexML (Legislação)
- Planalto (Legislação Federal)
- OpenAI (Deep Research)
- RAG Local (Base vetorial)
"""

import logging
import time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.usuario import Usuario
from app.models.audit_log import AuditLog, AcaoAudit, ModuloAudit
from app.services.pesquisa_juridica import (
    PesquisaJuridicaService,
    get_pesquisa_service,
    ResultadoPesquisa,
    RespostaPesquisa
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================
# SCHEMAS
# =============================================

class PesquisaRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Termo de busca")
    fontes: Optional[List[str]] = Field(None, description="Fontes a consultar (stf, stj, tst, lexml, planalto, cnj_datajud, openai, rag_local)")
    tribunal: Optional[str] = Field(None, description="Filtrar por tribunal")
    tipo: Optional[str] = Field(None, description="Tipo: jurisprudencia, legislacao, processo")
    limit: int = Field(20, ge=1, le=50, description="Máximo de resultados")
    deep_research: bool = Field(False, description="Ativar análise profunda com OpenAI")


class ResultadoResponse(BaseModel):
    fonte: str
    tipo: str
    titulo: str
    conteudo: str
    url: Optional[str] = None
    tribunal: Optional[str] = None
    data: Optional[str] = None
    relevancia: float = 0.0
    metadata: dict = {}


class PesquisaResponse(BaseModel):
    query: str
    resultados: List[ResultadoResponse]
    total: int
    fontes_consultadas: List[str]
    tempo_total: float
    analise_ia: Optional[str] = None
    sugestoes: List[str] = []


# =============================================
# PESQUISA UNIFICADA
# =============================================

@router.post("/", response_model=PesquisaResponse)
async def pesquisa_unificada(
    request: Request,
    body: PesquisaRequest,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    pesquisa: PesquisaJuridicaService = Depends(get_pesquisa_service)
):
    """
    Pesquisa jurídica unificada em múltiplas fontes.

    Consulta simultaneamente:
    - **STF**: Supremo Tribunal Federal
    - **STJ**: Superior Tribunal de Justiça
    - **TST**: Tribunal Superior do Trabalho
    - **CNJ DataJud**: Tribunais Estaduais (TJSP, TJRJ, etc)
    - **LexML**: Legislação brasileira
    - **Planalto**: Legislação federal
    - **OpenAI**: Pesquisa web + análise IA (requer OPENAI_API_KEY)
    - **RAG Local**: Base vetorial interna
    """
    resultado = await pesquisa.pesquisar(
        query=body.query,
        fontes=body.fontes,
        tribunal=body.tribunal,
        tipo=body.tipo,
        limit=body.limit,
        deep_research=body.deep_research
    )

    # Audit log
    log = AuditLog(
        acao=AcaoAudit.RAG_PESQUISA,
        modulo=ModuloAudit.RAG,
        usuario_id=current_user.id,
        usuario_email=current_user.email,
        descricao=f"Pesquisa unificada: {body.query[:100]}",
        prompt=body.query,
        fontes_usadas=resultado.fontes_consultadas,
        usuario_ip=request.client.host,
        extras={"deep_research": body.deep_research, "fontes_solicitadas": body.fontes}
    )
    db.add(log)
    await db.commit()

    return PesquisaResponse(
        query=resultado.query,
        resultados=[
            ResultadoResponse(
                fonte=r.fonte,
                tipo=r.tipo,
                titulo=r.titulo,
                conteudo=r.conteudo,
                url=r.url,
                tribunal=r.tribunal,
                data=r.data,
                relevancia=r.relevancia,
                metadata=r.metadata
            )
            for r in resultado.resultados
        ],
        total=resultado.total,
        fontes_consultadas=resultado.fontes_consultadas,
        tempo_total=resultado.tempo_total,
        analise_ia=resultado.analise_ia,
        sugestoes=resultado.sugestoes
    )


# =============================================
# ENDPOINTS POR TRIBUNAL
# =============================================

@router.get("/stf")
async def pesquisar_stf(
    q: str = Query(..., min_length=3, description="Termo de busca"),
    limit: int = Query(10, ge=1, le=25),
    current_user: Usuario = Depends(get_current_active_user),
    pesquisa: PesquisaJuridicaService = Depends(get_pesquisa_service)
):
    """Pesquisa jurisprudência no STF (Supremo Tribunal Federal)"""
    resultados = await pesquisa._pesquisar_stf(q, limit=limit)
    return {
        "tribunal": "STF",
        "query": q,
        "total": len(resultados),
        "resultados": [_to_dict(r) for r in resultados]
    }


@router.get("/stj")
async def pesquisar_stj(
    q: str = Query(..., min_length=3, description="Termo de busca"),
    limit: int = Query(10, ge=1, le=25),
    current_user: Usuario = Depends(get_current_active_user),
    pesquisa: PesquisaJuridicaService = Depends(get_pesquisa_service)
):
    """Pesquisa jurisprudência no STJ (Superior Tribunal de Justiça)"""
    resultados = await pesquisa._pesquisar_stj(q, limit=limit)
    return {
        "tribunal": "STJ",
        "query": q,
        "total": len(resultados),
        "resultados": [_to_dict(r) for r in resultados]
    }


@router.get("/tst")
async def pesquisar_tst(
    q: str = Query(..., min_length=3, description="Termo de busca"),
    limit: int = Query(10, ge=1, le=25),
    current_user: Usuario = Depends(get_current_active_user),
    pesquisa: PesquisaJuridicaService = Depends(get_pesquisa_service)
):
    """Pesquisa jurisprudência no TST (Tribunal Superior do Trabalho)"""
    resultados = await pesquisa._pesquisar_tst(q, limit=limit)
    return {
        "tribunal": "TST",
        "query": q,
        "total": len(resultados),
        "resultados": [_to_dict(r) for r in resultados]
    }


@router.get("/tribunal/{sigla}")
async def pesquisar_tribunal(
    sigla: str,
    q: str = Query(..., min_length=3, description="Termo de busca"),
    limit: int = Query(10, ge=1, le=25),
    current_user: Usuario = Depends(get_current_active_user),
    pesquisa: PesquisaJuridicaService = Depends(get_pesquisa_service)
):
    """
    Pesquisa jurisprudência em tribunal estadual via CNJ DataJud.

    Siglas suportadas: TJSP, TJRJ, TJMG, TJRS, TJPR, TJBA, TJPE, TJCE, TJSC, TJGO
    """
    sigla_upper = sigla.upper()
    tribunais_validos = ["TJSP", "TJRJ", "TJMG", "TJRS", "TJPR", "TJBA", "TJPE", "TJCE", "TJSC", "TJGO",
                         "TRF1", "TRF2", "TRF3", "TRF4", "TRF5"]
    if sigla_upper not in tribunais_validos:
        raise HTTPException(
            status_code=400,
            detail=f"Tribunal '{sigla_upper}' não suportado. Válidos: {', '.join(tribunais_validos)}"
        )

    resultados = await pesquisa._pesquisar_tribunal_estadual(q, sigla_upper, limit)
    return {
        "tribunal": sigla_upper,
        "query": q,
        "total": len(resultados),
        "resultados": [_to_dict(r) for r in resultados]
    }


# =============================================
# LEGISLAÇÃO
# =============================================

@router.get("/legislacao")
async def pesquisar_legislacao(
    q: str = Query(..., min_length=3, description="Termo de busca"),
    limit: int = Query(10, ge=1, le=25),
    current_user: Usuario = Depends(get_current_active_user),
    pesquisa: PesquisaJuridicaService = Depends(get_pesquisa_service)
):
    """
    Pesquisa legislação brasileira (LexML + Planalto).
    """
    import asyncio
    lexml_task = pesquisa._pesquisar_lexml(q, limit=limit)
    planalto_task = pesquisa._pesquisar_planalto(q, limit=limit)

    lexml_res, planalto_res = await asyncio.gather(lexml_task, planalto_task, return_exceptions=True)

    resultados = []
    fontes = []
    if not isinstance(lexml_res, Exception):
        resultados.extend(lexml_res)
        if lexml_res:
            fontes.append("LexML")
    if not isinstance(planalto_res, Exception):
        resultados.extend(planalto_res)
        if planalto_res:
            fontes.append("Planalto")

    # Deduplicar por título
    seen = set()
    unique = []
    for r in resultados:
        if r.titulo not in seen:
            seen.add(r.titulo)
            unique.append(r)
    unique.sort(key=lambda r: r.relevancia, reverse=True)

    return {
        "query": q,
        "fontes": fontes,
        "total": len(unique[:limit]),
        "resultados": [_to_dict(r) for r in unique[:limit]]
    }


# =============================================
# DEEP RESEARCH (OpenAI)
# =============================================

@router.post("/deep-research")
async def deep_research(
    request: Request,
    body: PesquisaRequest,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    pesquisa: PesquisaJuridicaService = Depends(get_pesquisa_service)
):
    """
    Pesquisa jurídica profunda com análise IA (OpenAI).

    Combina resultados de todas as fontes com análise inteligente:
    - Síntese do entendimento dominante
    - Divergências entre tribunais
    - Legislação aplicável
    - Recomendações práticas

    ⚠️ Requer OPENAI_API_KEY configurado no ambiente.
    """
    if not pesquisa.openai_client:
        raise HTTPException(
            status_code=503,
            detail="OpenAI não configurado. Defina OPENAI_API_KEY no ambiente."
        )

    body.deep_research = True

    resultado = await pesquisa.pesquisar(
        query=body.query,
        fontes=body.fontes or ["openai", "stf", "stj", "lexml", "rag_local"],
        tribunal=body.tribunal,
        tipo=body.tipo,
        limit=body.limit,
        deep_research=True
    )

    # Audit log
    log = AuditLog(
        acao=AcaoAudit.IA_CONSULTA,
        modulo=ModuloAudit.IA,
        usuario_id=current_user.id,
        usuario_email=current_user.email,
        descricao=f"Deep Research: {body.query[:100]}",
        prompt=body.query,
        resposta_ia=resultado.analise_ia[:2000] if resultado.analise_ia else None,
        fontes_usadas=resultado.fontes_consultadas,
        usuario_ip=request.client.host
    )
    db.add(log)
    await db.commit()

    return PesquisaResponse(
        query=resultado.query,
        resultados=[
            ResultadoResponse(
                fonte=r.fonte,
                tipo=r.tipo,
                titulo=r.titulo,
                conteudo=r.conteudo,
                url=r.url,
                tribunal=r.tribunal,
                data=r.data,
                relevancia=r.relevancia,
                metadata=r.metadata
            )
            for r in resultado.resultados
        ],
        total=resultado.total,
        fontes_consultadas=resultado.fontes_consultadas,
        tempo_total=resultado.tempo_total,
        analise_ia=resultado.analise_ia,
        sugestoes=resultado.sugestoes
    )


# =============================================
# SÚMULAS E TESES
# =============================================

@router.get("/sumulas/{tribunal}")
async def listar_sumulas(
    tribunal: str,
    current_user: Usuario = Depends(get_current_active_user),
    pesquisa: PesquisaJuridicaService = Depends(get_pesquisa_service)
):
    """Lista súmulas do tribunal (STF ou STJ)"""
    tribunal_upper = tribunal.upper()
    if tribunal_upper not in ["STF", "STJ"]:
        raise HTTPException(status_code=400, detail="Tribunal deve ser STF ou STJ")

    resultados = await pesquisa.consultar_sumulas(tribunal_upper)
    return {
        "tribunal": tribunal_upper,
        "total": len(resultados),
        "resultados": [_to_dict(r) for r in resultados]
    }


@router.get("/teses-repetitivos")
async def teses_repetitivos(
    q: str = Query("", description="Filtro opcional"),
    current_user: Usuario = Depends(get_current_active_user),
    pesquisa: PesquisaJuridicaService = Depends(get_pesquisa_service)
):
    """Pesquisa teses firmadas em recursos repetitivos (STJ)"""
    resultados = await pesquisa.consultar_teses_repetitivos(q)
    return {
        "query": q,
        "total": len(resultados),
        "resultados": [_to_dict(r) for r in resultados]
    }


# =============================================
# FONTES DISPONÍVEIS
# =============================================

@router.get("/fontes")
async def listar_fontes(
    current_user: Usuario = Depends(get_current_active_user),
    pesquisa: PesquisaJuridicaService = Depends(get_pesquisa_service)
):
    """Lista todas as fontes de pesquisa disponíveis e seu status"""
    return {
        "fontes": [
            {"id": "stf", "nome": "Supremo Tribunal Federal", "tipo": "jurisprudencia", "status": "ativo"},
            {"id": "stj", "nome": "Superior Tribunal de Justiça", "tipo": "jurisprudencia", "status": "ativo"},
            {"id": "tst", "nome": "Tribunal Superior do Trabalho", "tipo": "jurisprudencia", "status": "ativo"},
            {"id": "cnj_datajud", "nome": "CNJ DataJud", "tipo": "processo", "status": "ativo"},
            {"id": "tjsp", "nome": "Tribunal de Justiça de São Paulo", "tipo": "processo", "status": "ativo"},
            {"id": "tjrj", "nome": "Tribunal de Justiça do Rio de Janeiro", "tipo": "processo", "status": "ativo"},
            {"id": "tjmg", "nome": "Tribunal de Justiça de Minas Gerais", "tipo": "processo", "status": "ativo"},
            {"id": "lexml", "nome": "LexML - Rede de Informação Legislativa", "tipo": "legislacao", "status": "ativo"},
            {"id": "planalto", "nome": "Portal da Legislação - Planalto", "tipo": "legislacao", "status": "ativo"},
            {"id": "openai", "nome": "OpenAI Deep Research", "tipo": "ia", "status": "ativo" if pesquisa.openai_client else "não configurado"},
            {"id": "rag_local", "nome": "Base Vetorial Local (RAG)", "tipo": "todos", "status": "ativo"},
        ]
    }


# =============================================
# HELPERS
# =============================================

def _to_dict(r: ResultadoPesquisa) -> dict:
    """Converte ResultadoPesquisa para dict"""
    return {
        "fonte": r.fonte,
        "tipo": r.tipo,
        "titulo": r.titulo,
        "conteudo": r.conteudo,
        "url": r.url,
        "tribunal": r.tribunal,
        "data": r.data,
        "relevancia": r.relevancia,
        "metadata": r.metadata
    }
