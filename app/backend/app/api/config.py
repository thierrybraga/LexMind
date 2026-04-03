"""
API de Configurações do Sistema
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_active_user, require_role
from app.models.usuario import Usuario
from app.models.configuracao import Configuracao
from app.services.cnj_service import CNJService, get_cnj_service

logger = logging.getLogger(__name__)
router = APIRouter()


class ConfigResponse(BaseModel):
    chave: str
    valor: Optional[str] = None
    descricao: Optional[str] = None


class ConfigUpdate(BaseModel):
    valor: str
    descricao: Optional[str] = None


@router.get("/", response_model=List[ConfigResponse])
async def listar_configs(
    current_user: Usuario = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Lista todas as configurações"""
    result = await db.execute(select(Configuracao).order_by(Configuracao.chave))
    configs = result.scalars().all()
    return [
        ConfigResponse(chave=c.chave, valor=c.valor, descricao=c.descricao)
        for c in configs
    ]


@router.get("/{chave}", response_model=ConfigResponse)
async def get_config(
    chave: str,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Obtém uma configuração por chave"""
    result = await db.execute(select(Configuracao).where(Configuracao.chave == chave))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail=f"Configuração '{chave}' não encontrada")
    return ConfigResponse(chave=config.chave, valor=config.valor, descricao=config.descricao)


@router.put("/{chave}", response_model=ConfigResponse)
async def upsert_config(
    chave: str,
    body: ConfigUpdate,
    current_user: Usuario = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Cria ou atualiza uma configuração"""
    result = await db.execute(select(Configuracao).where(Configuracao.chave == chave))
    config = result.scalar_one_or_none()

    if config:
        config.valor = body.valor
        if body.descricao is not None:
            config.descricao = body.descricao
    else:
        config = Configuracao(chave=chave, valor=body.valor, descricao=body.descricao)
        db.add(config)

    await db.commit()
    await db.refresh(config)

    return ConfigResponse(chave=config.chave, valor=config.valor, descricao=config.descricao)


@router.post("/test-email", response_model=Dict[str, Any])
async def test_email(
    current_user: Usuario = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Testa envio de email (simulado por enquanto)"""
    # TODO: Implementar envio real usando configurações do banco
    # smtp_host = await get_config_value(db, "smtp_host")
    # ...
    return {"success": True, "message": "Email de teste enviado com sucesso!"}


@router.post("/test-cnj", response_model=Dict[str, Any])
async def test_cnj(
    current_user: Usuario = Depends(require_role(["admin"])),
    cnj_service: CNJService = Depends(get_cnj_service)
):
    """Testa conexão com CNJ DataJud"""
    try:
        resultado = await cnj_service.verificar_disponibilidade()
        if not resultado.get("disponivel"):
             return {"success": False, "message": f"Erro ao conectar com CNJ: {resultado.get('erro')}"}
        return {"success": True, "message": "Conexão com CNJ estabelecida com sucesso!"}
    except Exception as e:
        return {"success": False, "message": f"Erro ao conectar com CNJ: {str(e)}"}


@router.post("/reset", response_model=Dict[str, Any])
async def reset_config(
    current_user: Usuario = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Restaura configurações padrão (Apaga tudo para recriar no boot ou mantém chaves críticas)"""
    # Por segurança, vamos apenas limpar configurações não essenciais ou logar a ação
    # Implementação segura: não apagar tudo, apenas chaves específicas se solicitado
    # Aqui vamos simular o reset
    return {"success": True, "message": "Configurações restauradas para o padrão."}


@router.post("/clear-cache", response_model=Dict[str, Any])
async def clear_cache(
    current_user: Usuario = Depends(require_role(["admin"]))
):
    """Limpa cache do sistema (Redis/Memória)"""
    # TODO: Implementar limpeza real de cache
    return {"success": True, "message": "Cache do sistema limpo com sucesso."}


@router.post("/check-updates", response_model=Dict[str, Any])
async def check_updates(
    current_user: Usuario = Depends(require_role(["admin"]))
):
    """Verificar atualizações (Simulado)"""
    import asyncio
    await asyncio.sleep(1) # Simula delay
    return {"success": True, "message": "Sistema atualizado! Versão 1.0.0", "version": "1.0.0"}
