"""
API de Petições - Geração e Gestão
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io
from sqlalchemy import select
from typing import Optional, List
import os

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.core.config import settings
from app.core.llm import get_llm_engine, LLMEngine, TipoPeca
from app.models.usuario import Usuario
from app.models.processo import Processo
from app.models.peticao import Peticao, StatusPeticaoEnum
from app.models.jurisprudencia import Jurisprudencia
from app.models.audit_log import AuditLog, AcaoAudit, ModuloAudit
from app.schemas.schemas import (
    PeticaoGerarRequest,
    PeticaoGerarResponse,
    PeticaoCreate,
    PeticaoUpdate,
    PeticaoResponse,
    PeticaoExportarRequest
)
from app.services.rag_engine import get_rag_engine, RAGEngine
from app.services.documento_service import DocumentoService, get_documento_service

router = APIRouter()


@router.post("/gerar", response_model=PeticaoGerarResponse)
async def gerar_peticao(
    request: Request,
    peticao_request: PeticaoGerarRequest,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    llm_engine: LLMEngine = Depends(get_llm_engine),
    rag_engine: RAGEngine = Depends(get_rag_engine)
):
    """
    Gera petição jurídica usando IA
    
    A IA utiliza:
    - Dados do processo (se informado)
    - Jurisprudências relevantes (via RAG)
    - Templates específicos por tipo de peça
    """
    avisos = []
    dados_processo = {}
    jurisprudencias = []
    
    # Buscar dados do processo se informado
    if peticao_request.processo_numero:
        result = await db.execute(
            select(Processo).where(Processo.numero_cnj == peticao_request.processo_numero)
        )
        processo = result.scalar_one_or_none()
        if processo:
            dados_processo = {
                "numero": processo.numero_cnj,
                "classe": processo.classe,
                "assunto": processo.assunto,
                "comarca": processo.comarca,
                "vara": processo.vara,
                "tribunal": processo.tribunal,
                "polo_ativo": processo.polo_ativo,
                "polo_passivo": processo.polo_passivo
            }
        else:
            avisos.append("Processo não encontrado na base local. Dados podem estar incompletos.")
    
    # Buscar jurisprudências via RAG ou IDs específicos
    if peticao_request.jurisprudencia_ids:
        result = await db.execute(
            select(Jurisprudencia).where(
                Jurisprudencia.id.in_(peticao_request.jurisprudencia_ids)
            )
        )
        juris_list = result.scalars().all()
        jurisprudencias = [
            {
                "id": j.id,
                "numero": j.numero,
                "tribunal": j.tribunal,
                "ementa": j.ementa,
                "tese_principal": j.tese_principal
            }
            for j in juris_list
        ]
    else:
        # Buscar via RAG baseado no objetivo
        rag_results = await rag_engine.search(
            query=peticao_request.objetivo,
            tipo_fonte="jurisprudencia",
            top_k=5
        )
        jurisprudencias = [
            {
                "id": r.get("id"),
                "numero": r.get("fonte"),
                "tribunal": r.get("tribunal"),
                "ementa": r.get("conteudo")
            }
            for r in rag_results
        ]
    
    if not jurisprudencias:
        avisos.append("Nenhuma jurisprudência encontrada. Recomenda-se revisão manual.")
    
    # Mapear tipo de peça
    tipo_peca_map = {
        "inicial": TipoPeca.INICIAL,
        "contestacao": TipoPeca.CONTESTACAO,
        "recurso": TipoPeca.RECURSO,
        "habeas_corpus": TipoPeca.HABEAS_CORPUS,
        "embargos": TipoPeca.EMBARGOS,
        "agravo": TipoPeca.AGRAVO,
        "apelacao": TipoPeca.APELACAO,
        "parecer": TipoPeca.PARECER,
        "memoriais": TipoPeca.MEMORIAIS,
    }
    tipo_peca = tipo_peca_map.get(peticao_request.tipo.value, TipoPeca.INICIAL)
    
    # Gerar petição via LLM
    try:
        response = await llm_engine.gerar_peticao(
            tipo_peca=tipo_peca,
            dados_processo=dados_processo,
            jurisprudencias=jurisprudencias,
            objetivo=peticao_request.objetivo,
            estilo_tribunal=peticao_request.estilo_tribunal or "formal"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar petição: {str(e)}"
        )
    
    # Criar registro da petição
    peticao = Peticao(
        titulo=f"{peticao_request.tipo.value.upper()} - {peticao_request.objetivo[:50]}",
        tipo=peticao_request.tipo.value,
        autor_id=current_user.id,
        conteudo=response.content,
        objetivo=peticao_request.objetivo,
        status=StatusPeticaoEnum.RASCUNHO.value,
        gerada_por_ia=True,
        prompt_usado=peticao_request.objetivo,
        jurisprudencias_usadas=[j.get("id") for j in jurisprudencias if j.get("id")],
        fontes_usadas=response.sources_used,
        confianca_ia=int(response.confidence * 100)
    )
    
    # Vincular processo se existir
    if peticao_request.processo_numero:
        result = await db.execute(
            select(Processo).where(Processo.numero_cnj == peticao_request.processo_numero)
        )
        processo = result.scalar_one_or_none()
        if processo:
            peticao.processo_id = processo.id
    
    db.add(peticao)
    await db.commit()
    await db.refresh(peticao)
    
    # Log de auditoria
    log = AuditLog(
        acao=AcaoAudit.PETICAO_GERAR_IA,
        modulo=ModuloAudit.PETICAO,
        usuario_id=current_user.id,
        usuario_email=current_user.email,
        descricao=f"Petição gerada: {peticao.titulo}",
        prompt=peticao_request.objetivo,
        resposta_ia=response.content[:2000],
        fontes_usadas=response.sources_used,
        modelo_ia=response.model,
        tokens_usados=response.tokens_used,
        confianca=int(response.confidence * 100),
        entidade_tipo="peticao",
        entidade_id=peticao.id,
        usuario_ip=request.client.host
    )
    db.add(log)
    await db.commit()
    
    # Aviso legal obrigatório
    avisos.append("AVISO: Este documento foi gerado por IA e não substitui a revisão por advogado habilitado.")
    
    return PeticaoGerarResponse(
        peticao=PeticaoResponse.model_validate(peticao),
        fontes_utilizadas=jurisprudencias,
        confianca=response.confidence,
        avisos=avisos
    )


@router.post("/", response_model=PeticaoResponse)
async def criar_peticao(
    request: Request,
    peticao_data: PeticaoCreate,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Cria petição manualmente (sem IA)
    """
    peticao = Peticao(
        titulo=peticao_data.titulo,
        tipo=peticao_data.tipo.value,
        processo_id=peticao_data.processo_id,
        autor_id=current_user.id,
        conteudo=peticao_data.conteudo,
        objetivo=peticao_data.objetivo,
        status=StatusPeticaoEnum.RASCUNHO.value,
        gerada_por_ia=False
    )
    
    db.add(peticao)
    await db.commit()
    await db.refresh(peticao)
    
    # Log
    log = AuditLog(
        acao=AcaoAudit.PETICAO_CRIAR,
        modulo=ModuloAudit.PETICAO,
        usuario_id=current_user.id,
        usuario_email=current_user.email,
        descricao=f"Petição criada: {peticao.titulo}",
        entidade_tipo="peticao",
        entidade_id=peticao.id,
        usuario_ip=request.client.host
    )
    db.add(log)
    await db.commit()
    
    return PeticaoResponse.model_validate(peticao)


@router.get("/")
async def listar_peticoes(
    tipo: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista petições do usuário.
    Retorna {peticoes: [...], total: int}
    """
    from sqlalchemy import func as sa_func

    base_query = select(Peticao).where(Peticao.autor_id == current_user.id)

    if tipo:
        base_query = base_query.where(Peticao.tipo == tipo)
    if status:
        base_query = base_query.where(Peticao.status == status)

    count_q = select(sa_func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    base_query = base_query.offset(skip).limit(limit).order_by(Peticao.updated_at.desc())
    result = await db.execute(base_query)
    peticoes = result.scalars().all()

    return {
        "peticoes": [PeticaoResponse.model_validate(p).model_dump(mode="json") for p in peticoes],
        "total": total
    }


@router.get("/{id}", response_model=PeticaoResponse)
async def get_peticao(
    id: int,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna detalhes de uma petição
    """
    result = await db.execute(
        select(Peticao).where(
            Peticao.id == id,
            Peticao.autor_id == current_user.id
        )
    )
    peticao = result.scalar_one_or_none()
    
    if not peticao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Petição não encontrada"
        )
    
    return PeticaoResponse.model_validate(peticao)


@router.put("/{id}", response_model=PeticaoResponse)
async def atualizar_peticao(
    id: int,
    request: Request,
    peticao_data: PeticaoUpdate,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Atualiza petição
    """
    result = await db.execute(
        select(Peticao).where(
            Peticao.id == id,
            Peticao.autor_id == current_user.id
        )
    )
    peticao = result.scalar_one_or_none()
    
    if not peticao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Petição não encontrada"
        )
    
    # Incrementar versão
    peticao.versao += 1
    
    update_data = peticao_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(peticao, field, value)
    
    await db.commit()
    await db.refresh(peticao)
    
    # Log
    log = AuditLog(
        acao=AcaoAudit.PETICAO_EDITAR,
        modulo=ModuloAudit.PETICAO,
        usuario_id=current_user.id,
        usuario_email=current_user.email,
        descricao=f"Petição atualizada: {peticao.titulo} (v{peticao.versao})",
        entidade_tipo="peticao",
        entidade_id=peticao.id,
        usuario_ip=request.client.host
    )
    db.add(log)
    await db.commit()
    
    return PeticaoResponse.model_validate(peticao)


@router.post("/exportar/{formato}")
async def exportar_conteudo(
    formato: str,
    export_request: PeticaoExportarRequest,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    doc_service: DocumentoService = Depends(get_documento_service)
):
    """
    Exporta conteúdo arbitrário para DOCX ou PDF
    """
    if formato not in ["docx", "pdf"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato inválido. Use 'docx' ou 'pdf'."
        )
        
    if formato == "docx":
        docx_bytes = await doc_service.gerar_docx(
            conteudo=export_request.conteudo,
            titulo=export_request.titulo
        )
        
        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={export_request.titulo}.docx"}
        )
        
    elif formato == "pdf":
        pdf_bytes = await doc_service.gerar_pdf(
            conteudo=export_request.conteudo,
            titulo=export_request.titulo
        )

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={export_request.titulo}.pdf"}
        )


@router.post("/{id}/exportar/{formato}")
async def exportar_peticao(
    id: int,
    formato: str,
    request: Request,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    doc_service: DocumentoService = Depends(get_documento_service)
):
    """
    Exporta petição para DOCX ou PDF
    """
    if formato not in ["docx", "pdf"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato inválido. Use 'docx' ou 'pdf'."
        )
        
    result = await db.execute(
        select(Peticao).where(
            Peticao.id == id,
            Peticao.autor_id == current_user.id
        )
    )
    peticao = result.scalar_one_or_none()
    
    if not peticao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Petição não encontrada"
        )
        
    if formato == "docx":
        docx_bytes = await doc_service.gerar_docx(
            conteudo=peticao.conteudo,
            titulo=peticao.titulo
        )
        
        # Log
        log = AuditLog(
            acao=AcaoAudit.PETICAO_EXPORTAR,
            modulo=ModuloAudit.PETICAO,
            usuario_id=current_user.id,
            usuario_email=current_user.email,
            descricao=f"Petição exportada: {peticao.titulo} ({formato})",
            entidade_tipo="peticao",
            entidade_id=peticao.id
        )
        db.add(log)
        await db.commit()
        
        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={peticao.titulo}.docx"}
        )
        
    elif formato == "pdf":
        pdf_bytes = await doc_service.gerar_pdf(
            conteudo=peticao.conteudo,
            titulo=peticao.titulo
        )

        # Log
        log = AuditLog(
            acao=AcaoAudit.PETICAO_EXPORTAR,
            modulo=ModuloAudit.PETICAO,
            usuario_id=current_user.id,
            usuario_email=current_user.email,
            descricao=f"Petição exportada: {peticao.titulo} ({formato})",
            entidade_tipo="peticao",
            entidade_id=peticao.id
        )
        db.add(log)
        await db.commit()

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={peticao.titulo}.pdf"}
        )


@router.delete("/{id}")
async def deletar_peticao(
    id: int,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Deleta petição (soft delete)
    """
    result = await db.execute(
        select(Peticao).where(
            Peticao.id == id,
            Peticao.autor_id == current_user.id
        )
    )
    peticao = result.scalar_one_or_none()
    
    if not peticao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Petição não encontrada"
        )
    
    peticao.status = "deletado"
    await db.commit()
    
    return {"message": "Petição deletada com sucesso"}