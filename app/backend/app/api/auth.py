"""
API de Autenticação
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    get_current_active_user
)
from app.core.config import settings
from app.models.usuario import Usuario
from app.models.audit_log import AuditLog, AcaoAudit, ModuloAudit
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UsuarioCreate,
    UsuarioUpdate,
    UsuarioResponse,
    PasswordChange
)

router = APIRouter()


async def log_audit(
    db: AsyncSession,
    acao: str,
    usuario_id: int = None,
    usuario_email: str = None,
    descricao: str = None,
    request: Request = None
):
    """Helper para criar log de auditoria"""
    log = AuditLog(
        acao=acao,
        modulo=ModuloAudit.AUTH,
        usuario_id=usuario_id,
        usuario_email=usuario_email,
        descricao=descricao,
        usuario_ip=request.client.host if request else None
    )
    db.add(log)


@router.post("/login")
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Autenticação de usuário

    Aceita JSON {email, senha} ou form data {username, password}
    """
    email = None
    password = None

    # Tentar ler JSON body primeiro
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
            email = body.get("email")
            password = body.get("senha") or body.get("password")
        except Exception:
            pass
    else:
        # Form data (OAuth2 compatibility)
        form = await request.form()
        email = form.get("username") or form.get("email")
        password = form.get("password") or form.get("senha")

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email e senha são obrigatórios"
        )

    # Buscar usuário
    result = await db.execute(
        select(Usuario).where(Usuario.email == email)
    )
    user = result.scalar_one_or_none()

    # Verificar credenciais
    if not user or not verify_password(password, user.hashed_password):
        await log_audit(
            db, AcaoAudit.LOGIN_FALHA,
            usuario_email=email,
            descricao="Credenciais inválidas",
            request=request
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verificar se está ativo
    if not user.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário desativado. Entre em contato com o administrador."
        )

    # Criar token
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "role": user.role
        }
    )

    # Atualizar último acesso
    user.ultimo_acesso = datetime.utcnow()

    # Log de auditoria
    await log_audit(
        db, AcaoAudit.LOGIN,
        usuario_id=user.id,
        usuario_email=user.email,
        descricao="Login realizado com sucesso",
        request=request
    )

    await db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "usuario": {
            "id": user.id,
            "email": user.email,
            "nome": user.nome,
            "role": user.role,
            "oab": user.oab,
            "ativo": user.ativo
        }
    }


@router.post("/register", response_model=UsuarioResponse)
async def register(
    user_data: UsuarioCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Registro de novo usuário
    """
    # Verificar se email já existe
    result = await db.execute(
        select(Usuario).where(Usuario.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado"
        )
    
    # Criar usuário
    user = Usuario(
        email=user_data.email,
        nome=user_data.nome,
        hashed_password=get_password_hash(user_data.password),
        oab=user_data.oab,
        oab_estado=user_data.oab_estado,
        cpf=user_data.cpf,
        telefone=user_data.telefone,
        role=user_data.role
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return UsuarioResponse.model_validate(user)


@router.get("/me", response_model=UsuarioResponse)
async def get_me(
    current_user: Usuario = Depends(get_current_active_user)
):
    """
    Retorna dados do usuário autenticado
    """
    return UsuarioResponse.model_validate(current_user)


@router.put("/me", response_model=UsuarioResponse)
async def update_me(
    user_data: UsuarioUpdate,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Atualiza dados do usuário autenticado
    """
    update_data = user_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    await db.commit()
    await db.refresh(current_user)
    
    return UsuarioResponse.model_validate(current_user)


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Altera senha do usuário
    """
    # Verificar senha atual
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta"
        )
    
    # Atualizar senha
    current_user.hashed_password = get_password_hash(password_data.new_password)
    await db.commit()
    
    return {"message": "Senha alterada com sucesso"}


@router.post("/logout")
async def logout(
    request: Request,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Logout (registro para auditoria)
    """
    await log_audit(
        db, AcaoAudit.LOGOUT,
        usuario_id=current_user.id,
        usuario_email=current_user.email,
        descricao="Logout realizado",
        request=request
    )
    await db.commit()
    
    return {"message": "Logout realizado com sucesso"}
