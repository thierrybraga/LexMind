"""
Configuração do Banco de Dados - SQLAlchemy Async
Suporta PostgreSQL (produção) e SQLite (desenvolvimento local)
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, DateTime, func, event
from typing import AsyncGenerator
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configurar engine args baseado no driver
engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True,
}

# SQLite precisa de connect_args especial
if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

# Engine assíncrono
engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


class Base(DeclarativeBase):
    """Base para todos os modelos"""
    pass


class TimestampMixin:
    """Mixin para campos de timestamp"""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency para obter sessão do banco"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Inicializa o banco de dados criando todas as tabelas"""
    import asyncio

    retries = 3 if settings.DATABASE_URL.startswith("sqlite") else 10
    for i in range(retries):
        try:
            async with engine.begin() as conn:
                # Importar todos os modelos para que sejam registrados
                from app.models import usuario, processo, peticao, jurisprudencia, audit_log, cliente, configuracao, mensagem

                # Criar tabelas
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Tabelas do banco de dados criadas")
                return
        except Exception as e:
            if i < retries - 1:
                logger.warning(f"Falha ao conectar ao banco (tentativa {i+1}/{retries}). Retentando em 2s... Erro: {e}")
                await asyncio.sleep(2)
            else:
                logger.error("Falha critica ao conectar ao banco apos varias tentativas.")
                raise e


async def drop_db():
    """Remove todas as tabelas (CUIDADO - apenas para desenvolvimento)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        logger.warning("Todas as tabelas foram removidas")
