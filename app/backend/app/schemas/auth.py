"""
Schemas de Autenticação
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    """Request de login"""
    email: EmailStr
    password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    """Response com token JWT"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UsuarioResponse"


class TokenData(BaseModel):
    """Dados extraídos do token"""
    email: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None


class UsuarioCreate(BaseModel):
    """Criação de usuário"""
    email: EmailStr
    nome: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6)
    oab: Optional[str] = None
    oab_estado: Optional[str] = Field(None, max_length=2)
    cpf: Optional[str] = None
    telefone: Optional[str] = None
    role: str = "advogado"


class UsuarioUpdate(BaseModel):
    """Atualização de usuário"""
    nome: Optional[str] = None
    oab: Optional[str] = None
    oab_estado: Optional[str] = None
    telefone: Optional[str] = None


class UsuarioResponse(BaseModel):
    """Response de usuário"""
    id: int
    email: str
    nome: str
    oab: Optional[str]
    oab_estado: Optional[str]
    role: str
    ativo: bool
    created_at: datetime
    ultimo_acesso: Optional[datetime]
    
    class Config:
        from_attributes = True


class PasswordChange(BaseModel):
    """Alteração de senha"""
    current_password: str
    new_password: str = Field(..., min_length=6)


class PasswordReset(BaseModel):
    """Reset de senha"""
    email: EmailStr


# Resolver referência circular
TokenResponse.model_rebuild()
