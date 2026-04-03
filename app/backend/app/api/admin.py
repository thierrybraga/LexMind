"""
API de Administração - Gestão de Usuários e Sistema
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_active_user, require_role, Roles
from app.models.usuario import Usuario
from app.schemas.auth import UsuarioResponse

router = APIRouter()


@router.get("/usuarios")
async def listar_usuarios(
    role: Optional[str] = None,
    ativo: Optional[bool] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: Usuario = Depends(require_role([Roles.ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista todos os usuários do sistema (apenas admin).
    Retorna {usuarios: [...], total: int}
    """
    base_query = select(Usuario)

    if role:
        base_query = base_query.where(Usuario.role == role)
    if ativo is not None:
        base_query = base_query.where(Usuario.ativo == ativo)

    count_q = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    offset = (page - 1) * limit
    base_query = base_query.offset(offset).limit(limit).order_by(Usuario.created_at.desc())

    result = await db.execute(base_query)
    usuarios = result.scalars().all()

    return {
        "usuarios": [UsuarioResponse.model_validate(u).model_dump(mode="json") for u in usuarios],
        "total": total
    }


@router.get("/usuarios/{id}")
async def get_usuario(
    id: int,
    current_user: Usuario = Depends(require_role([Roles.ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Retorna detalhes de um usuário"""
    result = await db.execute(select(Usuario).where(Usuario.id == id))
    usuario = result.scalar_one_or_none()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    return UsuarioResponse.model_validate(usuario).model_dump(mode="json")


@router.put("/usuarios/{id}/toggle-ativo")
async def toggle_usuario_ativo(
    id: int,
    current_user: Usuario = Depends(require_role([Roles.ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Ativa/desativa um usuário"""
    result = await db.execute(select(Usuario).where(Usuario.id == id))
    usuario = result.scalar_one_or_none()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if usuario.id == current_user.id:
        raise HTTPException(status_code=400, detail="Não é possível desativar a própria conta")

    usuario.ativo = not usuario.ativo
    await db.commit()

    return {"message": f"Usuário {'ativado' if usuario.ativo else 'desativado'}", "ativo": usuario.ativo}


@router.put("/usuarios/{id}/role")
async def alterar_role(
    id: int,
    role: str,
    current_user: Usuario = Depends(require_role([Roles.ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Altera o role de um usuário"""
    valid_roles = ["admin", "advogado", "estagiario", "cliente"]
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Role inválido. Use: {valid_roles}")

    result = await db.execute(select(Usuario).where(Usuario.id == id))
    usuario = result.scalar_one_or_none()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    usuario.role = role
    await db.commit()

    return {"message": f"Role alterado para {role}"}
