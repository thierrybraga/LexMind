"""
API de RAG Jurídico - Pesquisa Semântica
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from typing import List, Optional
import time

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.core.llm import get_llm_engine, LLMEngine
from app.models.usuario import Usuario
from app.models.jurisprudencia import Jurisprudencia, Doutrina, Legislacao
from app.models.audit_log import AuditLog, AcaoAudit, ModuloAudit
from app.schemas.schemas import (
    RAGSearchRequest,
    RAGSearchResponse,
    RAGResultItem,
    ConsultaIARequest,
    ConsultaIAResponse
)
from app.services.rag_engine import RAGEngine, get_rag_engine

router = APIRouter()


async def log_rag_audit(
    db: AsyncSession,
    usuario: Usuario,
    query: str,
    resultados: int,
    fontes: List[str],
    request: Request = None
):
    """Log de auditoria para pesquisas RAG"""
    log = AuditLog(
        acao=AcaoAudit.RAG_PESQUISA,
        modulo=ModuloAudit.RAG,
        usuario_id=usuario.id,
        usuario_email=usuario.email,
        descricao=f"Pesquisa RAG: {query[:100]}",
        prompt=query,
        fontes_usadas=fontes,
        usuario_ip=request.client.host if request else None
    )
    db.add(log)


@router.post("/search", response_model=RAGSearchResponse)
async def search_rag(
    request: Request,
    search_request: RAGSearchRequest,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    rag_engine: RAGEngine = Depends(get_rag_engine)
):
    """
    Pesquisa semântica em base jurídica (RAG)
    
    Busca em:
    - Jurisprudência (STF, STJ, TJs, TRFs)
    - Doutrina
    - Legislação
    """
    start_time = time.time()
    
    # Realizar busca vetorial
    results = await rag_engine.search(
        query=search_request.query,
        tribunal=search_request.tribunal,
        area_direito=search_request.area_direito,
        tipo_fonte=search_request.tipo_fonte,
        top_k=search_request.top_k
    )
    
    # Formatar resultados
    formatted_results = []
    fontes_consultadas = set()
    
    for result in results:
        formatted_results.append(RAGResultItem(
            id=result.get("id", 0),
            tipo=result.get("tipo", "desconhecido"),
            titulo=result.get("titulo") or result.get("ementa", ""),
            conteudo=result.get("conteudo", "")[:500],
            fonte=result.get("fonte", ""),
            tribunal=result.get("tribunal"),
            data=result.get("data_julgamento") or result.get("data"),
            relevancia=result.get("score", 0.0),
            metadata=result.get("metadata", {})
        ))
        fontes_consultadas.add(result.get("tipo", "desconhecido"))
    
    tempo_busca = time.time() - start_time
    
    # Log de auditoria
    await log_rag_audit(
        db, current_user,
        search_request.query,
        len(formatted_results),
        list(fontes_consultadas),
        request
    )
    await db.commit()
    
    return RAGSearchResponse(
        query=search_request.query,
        total_results=len(formatted_results),
        results=formatted_results,
        tempo_busca=tempo_busca,
        fontes_consultadas=list(fontes_consultadas)
    )


@router.post("/jurisprudencia/indexar")
async def index_jurisprudencia(
    request: Request,
    dados: dict = Body(...),
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    rag_engine: RAGEngine = Depends(get_rag_engine)
):
    """
    Indexa uma nova jurisprudência no banco e no vector store
    """
    # Validar campos obrigatórios
    required_fields = ["tribunal", "ementa"]
    for field in required_fields:
        if field not in dados:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Campo obrigatório ausente: {field}"
            )
            
    # Verificar se já existe
    if "numero" in dados:
        existing = await db.execute(
            select(Jurisprudencia).where(
                and_(
                    Jurisprudencia.numero == dados["numero"],
                    Jurisprudencia.tribunal == dados["tribunal"]
                )
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Jurisprudência já cadastrada"
            )
    
    # Criar objeto
    nova_juris = Jurisprudencia(
        numero=dados.get("numero"),
        tribunal=dados.get("tribunal"),
        ementa=dados.get("ementa"),
        orgao_julgador=dados.get("orgao_julgador"),
        relator=dados.get("relator"),
        data_julgamento=dados.get("data_julgamento"),
        inteiro_teor=dados.get("inteiro_teor"),
        area_direito=dados.get("area_direito"),
        tese_principal=dados.get("tese_principal"),
        url_original=dados.get("url_original")
    )
    
    db.add(nova_juris)
    await db.commit()
    await db.refresh(nova_juris)
    
    # Indexar no RAG (Vector DB)
    try:
        embedding_id = await rag_engine.index_document(
            id=nova_juris.id,
            text=f"{nova_juris.tribunal} - {nova_juris.ementa}",
            metadata={
                "tipo": "jurisprudencia",
                "tribunal": nova_juris.tribunal,
                "numero": nova_juris.numero,
                "area": nova_juris.area_direito
            }
        )
        nova_juris.embedding_id = embedding_id
        await db.commit()
    except Exception as e:
        print(f"Erro ao indexar no Vector DB: {e}")
        
    return {
        "id": nova_juris.id,
        "mensagem": "Jurisprudência indexada com sucesso",
        "embedding_id": nova_juris.embedding_id
    }


@router.get("/jurisprudencia/{id}")
async def get_jurisprudencia(
    id: int,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna detalhes de uma jurisprudência específica
    """
    result = await db.execute(
        select(Jurisprudencia).where(Jurisprudencia.id == id)
    )
    juris = result.scalar_one_or_none()
    
    if not juris:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jurisprudência não encontrada"
        )
        
    return juris


@router.get("/sugestoes")
async def get_sugestoes(
    q: str,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna sugestões de busca baseado no input parcial
    """
    if len(q) < 3:
        return {"sugestoes": []}
    
    # Buscar em assuntos de jurisprudências
    result = await db.execute(
        select(Jurisprudencia.tese_principal)
        .where(Jurisprudencia.tese_principal.ilike(f"%{q}%"))
        .distinct()
        .limit(10)
    )
    
    sugestoes = [row[0] for row in result.fetchall() if row[0]]
    
    return {"sugestoes": sugestoes[:10]}


@router.post("/consulta-ia")
async def consulta_ia(
    request: Request,
    dados: ConsultaIARequest,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    llm_engine: LLMEngine = Depends(get_llm_engine),
    rag_engine: RAGEngine = Depends(get_rag_engine)
):
    """
    Consulta jurídica com IA + RAG
    
    A IA responde fundamentada em jurisprudência, doutrina e legislação.
    """
    query = dados.pergunta
    search_query = dados.search_query or query
    usar_rag = dados.usar_rag
    
    contexto_rag = []
    
    # Buscar contexto via RAG
    if usar_rag:
        rag_results = await rag_engine.search(query=search_query, top_k=5)
        contexto_rag = [
            {
                "fonte": r.get("fonte", ""),
                "conteudo": r.get("conteudo", "")
            }
            for r in rag_results
        ]
    
    # Processar com LLM
    response = await llm_engine.processar_consulta_juridica(
        consulta=query,
        contexto_rag=contexto_rag
    )
    
    # Log de auditoria
    log = AuditLog(
        acao=AcaoAudit.IA_CONSULTA,
        modulo=ModuloAudit.IA,
        usuario_id=current_user.id,
        usuario_email=current_user.email,
        prompt=query,
        resposta_ia=response.content[:2000],
        fontes_usadas=response.sources_used,
        modelo_ia=response.model,
        tokens_usados=response.tokens_used,
        confianca=int(response.confidence * 100),
        usuario_ip=request.client.host
    )
    db.add(log)
    await db.commit()
    
    return {
        "resposta": response.content,
        "fontes": response.sources_used,
        "confianca": response.confidence,
        "aviso_legal": "Este conteúdo é gerado por IA e não substitui a consulta a um advogado habilitado."
    }


@router.get("/estatisticas")
async def get_estatisticas(
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna estatísticas da base RAG
    """
    from sqlalchemy import func
    
    # Contar jurisprudências por tribunal
    result = await db.execute(
        select(
            Jurisprudencia.tribunal,
            func.count(Jurisprudencia.id)
        ).group_by(Jurisprudencia.tribunal)
    )
    juris_por_tribunal = dict(result.fetchall())
    
    # Total de cada tipo
    total_juris = await db.execute(select(func.count(Jurisprudencia.id)))
    total_doutrina = await db.execute(select(func.count(Doutrina.id)))
    total_legislacao = await db.execute(select(func.count(Legislacao.id)))
    
    return {
        "total_jurisprudencias": total_juris.scalar() or 0,
        "total_doutrinas": total_doutrina.scalar() or 0,
        "total_legislacoes": total_legislacao.scalar() or 0,
        "jurisprudencias_por_tribunal": juris_por_tribunal
    }