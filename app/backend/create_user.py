import asyncio
import sys
import os

# Adiciona o diretório atual ao path para importar os módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import async_session_maker, init_db
from app.models.usuario import Usuario, RoleEnum
from app.core.security import get_password_hash
from sqlalchemy import select

async def create_user():
    print("Inicializando banco de dados...")
    await init_db()
    
    print("Conectando ao banco de dados...")
    async with async_session_maker() as session:
        # Verifica se já existe
        result = await session.execute(select(Usuario).where(Usuario.email == "advogado@iajuridica.com.br"))
        user = result.scalar_one_or_none()
        
        if user:
            print("Usuário advogado@iajuridica.com.br já existe.")
            # Atualizar senha para garantir
            user.hashed_password = get_password_hash("senha123")
            await session.commit()
            print("Senha redefinida para: senha123")
            return

        print("Criando usuário advogado@iajuridica.com.br...")
        novo_usuario = Usuario(
            email="advogado@iajuridica.com.br",
            nome="Doutor Advogado",
            hashed_password=get_password_hash("senha123"),
            role=RoleEnum.ADVOGADO.value,
            oab="123456",
            oab_estado="SP",
            ativo=True
        )
        
        session.add(novo_usuario)
        await session.commit()
        print("Usuário criado com sucesso!")
        print("Email: advogado@iajuridica.com.br")
        print("Senha: senha123")

if __name__ == "__main__":
    # Fix para Windows SelectorEventLoop
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(create_user())