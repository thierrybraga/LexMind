"""
API de Gestão de Modelos LLM - OpenAI
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_active_user, require_role
from app.models.usuario import Usuario
from app.models.configuracao import Configuracao
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status")
async def llm_status(
    current_user: Usuario = Depends(get_current_active_user)
):
    """Status da OpenAI e modelo ativo"""
    if not settings.OPENAI_API_KEY:
        return {
            "openai_online": False,
            "error": "OPENAI_API_KEY não configurado",
            "active_model": settings.OPENAI_MODEL
        }
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        models = await client.models.list()
    except Exception as e:
        return {
            "openai_online": False,
            "error": str(e),
            "active_model": settings.OPENAI_MODEL
        }

    return {
        "openai_online": True,
        "active_model": settings.OPENAI_MODEL,
        "models_count": len(models.data),
        "provider": "OpenAI"
    }


@router.get("/models")
async def list_models(
    current_user: Usuario = Depends(get_current_active_user)
):
    """Lista modelos disponíveis na OpenAI"""
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI não configurado. Defina OPENAI_API_KEY no ambiente."
        )
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        data = await client.models.list()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OpenAI indisponível: {str(e)}"
        )

    models = []
    for m in data.data:
        models.append({
            "name": m.id,
            "created_at": m.created,
            "owned_by": m.owned_by,
            "is_active": m.id == settings.OPENAI_MODEL
        })

    return {
        "models": models,
        "active_model": settings.OPENAI_MODEL,
        "total": len(models)
    }


@router.get("/models/{name:path}/info")
async def model_info(
    name: str,
    current_user: Usuario = Depends(get_current_active_user)
):
    """Informações detalhadas de um modelo"""
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI não configurado. Defina OPENAI_API_KEY no ambiente."
        )
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        return await client.models.retrieve(name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Modelo '{name}' não encontrado: {str(e)}")


@router.post("/models/pull")
async def pull_model(
    request: dict,
    current_user: Usuario = Depends(require_role(["admin"]))
):
    raise HTTPException(status_code=400, detail="Operação não suportada para OpenAI")


@router.delete("/models/{name:path}")
async def delete_model(
    name: str,
    current_user: Usuario = Depends(require_role(["admin"]))
):
    raise HTTPException(status_code=400, detail="Operação não suportada para OpenAI")


@router.put("/active-model")
async def set_active_model(
    request: dict,
    current_user: Usuario = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Define o modelo LLM ativo"""
    model_name = request.get("name")
    if not model_name:
        raise HTTPException(status_code=400, detail="Campo 'name' obrigatório")

    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI não configurado. Defina OPENAI_API_KEY no ambiente."
        )

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        await client.models.retrieve(model_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Modelo '{model_name}' não encontrado: {str(e)}")

    # Salvar na configuração
    result = await db.execute(
        select(Configuracao).where(Configuracao.chave == "llm_model")
    )
    config = result.scalar_one_or_none()

    if config:
        config.valor = model_name
    else:
        config = Configuracao(chave="llm_model", valor=model_name, descricao="Modelo LLM ativo")
        db.add(config)

    await db.commit()

    # Atualizar settings em runtime
    settings.OPENAI_MODEL = model_name

    # Atualizar LLMEngine
    from app.core.llm import llm_engine
    llm_engine.model = model_name

    return {
        "message": f"Modelo ativo alterado para '{model_name}'",
        "active_model": model_name
    }
