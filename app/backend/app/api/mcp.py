"""
API MCP Server - Ferramentas e Execução Controlada
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List
import time

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.core.config import settings
from app.models.usuario import Usuario
from app.models.jurisprudencia import Legislacao
from app.models.audit_log import AuditLog, AcaoAudit, ModuloAudit
from app.schemas.schemas import MCPExecuteRequest, MCPExecuteResponse
from app.services.mcp_service import MCPService, get_mcp_service

router = APIRouter()


@router.get("/tools")
async def listar_ferramentas(
    current_user: Usuario = Depends(get_current_active_user)
):
    """
    Lista ferramentas MCP disponíveis
    """
    tools = [
        {
            "name": "buscar_jurisprudencia",
            "description": "Busca jurisprudência nos tribunais",
            "params": ["query", "tribunal", "limit"]
        },
        {
            "name": "consultar_processo",
            "description": "Consulta dados de processo no CNJ",
            "params": ["numero_processo"]
        },
        {
            "name": "criar_documento",
            "description": "Cria documento DOCX ou PDF",
            "params": ["conteudo", "formato", "nome_arquivo"]
        },
        {
            "name": "converter_pdf",
            "description": "Converte PDF para texto",
            "params": ["arquivo_path"]
        },
        {
            "name": "buscar_lei",
            "description": "Busca legislação no Planalto/LexML",
            "params": ["tipo", "numero", "ano"]
        },
        {
            "name": "extrair_texto_pdf",
            "description": "Extrai texto de arquivo PDF",
            "params": ["arquivo_path"]
        },
        {
            "name": "analisar_documento",
            "description": "Analisa documento jurídico com IA",
            "params": ["conteudo", "tipo_analise"]
        }
    ]
    
    return {
        "tools": tools,
        "total": len(tools),
        "allowed": settings.MCP_ALLOWED_TOOLS
    }


@router.post("/execute", response_model=MCPExecuteResponse)
async def executar_ferramenta(
    request: Request,
    mcp_request: MCPExecuteRequest,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    Executa ferramenta MCP
    
    ⚠️ Execução controlada em sandbox
    """
    start_time = time.time()
    
    # Verificar se ferramenta está permitida
    if mcp_request.tool not in settings.MCP_ALLOWED_TOOLS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Ferramenta '{mcp_request.tool}' não está habilitada"
        )
    
    # Executar ferramenta
    try:
        result = await mcp_service.execute(
            tool=mcp_request.tool,
            params=mcp_request.params,
            user_id=current_user.id
        )
        success = True
        error = None
    except Exception as e:
        result = None
        success = False
        error = str(e)
    
    execution_time = time.time() - start_time
    
    # Log de auditoria
    log = AuditLog(
        acao=AcaoAudit.MCP_EXECUTAR,
        modulo=ModuloAudit.MCP,
        usuario_id=current_user.id,
        usuario_email=current_user.email,
        descricao=f"MCP Tool: {mcp_request.tool}",
        request_data=mcp_request.params,
        response_status=200 if success else 500,
        usuario_ip=request.client.host,
        extras={
            "tool": mcp_request.tool,
            "success": success,
            "execution_time": execution_time
        }
    )
    db.add(log)
    await db.commit()
    
    return MCPExecuteResponse(
        tool=mcp_request.tool,
        success=success,
        result=result,
        error=error,
        execution_time=execution_time
    )


@router.post("/buscar-jurisprudencia")
async def buscar_jurisprudencia_mcp(
    request: Request,
    query: str,
    tribunal: str = None,
    limit: int = 10,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    Busca jurisprudência via MCP (wrapper conveniente)
    """
    result = await mcp_service.execute(
        tool="buscar_jurisprudencia",
        params={
            "query": query,
            "tribunal": tribunal,
            "limit": limit
        },
        user_id=current_user.id
    )
    
    return result


@router.post("/converter-documento")
async def converter_documento_mcp(
    request: Request,
    arquivo_path: str,
    formato_saida: str = "txt",
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    Converte documento via MCP
    """
    if formato_saida not in ["txt", "docx", "pdf"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de saída inválido"
        )
    
    result = await mcp_service.execute(
        tool="converter_pdf" if arquivo_path.endswith(".pdf") else "criar_documento",
        params={
            "arquivo_path": arquivo_path,
            "formato_saida": formato_saida
        },
        user_id=current_user.id
    )
    
    return result


@router.post("/buscar-legislacao")
async def buscar_legislacao_mcp(
    request: Request,
    tipo: str,
    numero: str = None,
    ano: int = None,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    Busca legislação via MCP e persiste resultados
    """
    result = await mcp_service.execute(
        tool="buscar_lei",
        params={
            "tipo": tipo,
            "numero": numero,
            "ano": ano
        },
        user_id=current_user.id
    )
    
    # Persistir resultados no banco se encontrados
    if result and isinstance(result, dict) and "resultados" in result:
        for item in result["resultados"]:
            # Tentar extrair número e ano se possível
            num = item.get("numero", "").split("/")[0] if "/" in item.get("numero", "") else item.get("numero", "")
            
            # Verificar existência
            stmt = select(Legislacao).where(
                Legislacao.numero == num,
                Legislacao.tipo == item.get("tipo", "Lei")
            )
            existing = await db.execute(stmt)
            if not existing.scalar_one_or_none():
                nova_lei = Legislacao(
                    tipo=item.get("tipo", "Lei"),
                    numero=num,
                    ano=ano or 0,  # Fallback
                    ementa=item.get("ementa"),
                    apelido=item.get("nome"),
                    url_planalto=item.get("link")
                )
                db.add(nova_lei)
        
        await db.commit()
    
    return result


@router.get("/status")
async def status_mcp(
    current_user: Usuario = Depends(get_current_active_user)
):
    """
    Status do servidor MCP
    """
    return {
        "enabled": settings.MCP_ENABLED,
        "status": "operational" if settings.MCP_ENABLED else "disabled",
        "allowed_tools": settings.MCP_ALLOWED_TOOLS
    }