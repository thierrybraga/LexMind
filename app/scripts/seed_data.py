"""
Seed de dados iniciais para o sistema IA Jurídica
"""

import asyncio
import sys
from pathlib import Path

# Adicionar path do projeto
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from backend.app.core.database import async_session_maker, engine
from backend.app.models import Base
from backend.app.models.usuario import Usuario
from backend.app.models.jurisprudencia import Jurisprudencia, Doutrina, Legislacao
from backend.app.core.security import get_password_hash


async def create_tables():
    """Criar todas as tabelas"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tabelas criadas com sucesso!")


async def seed_usuarios():
    """Criar usuários de exemplo"""
    async with async_session_maker() as session:
        usuarios = [
            Usuario(
                nome="Administrador",
                email="admin@iajuridica.com.br",
                senha_hash=get_password_hash("admin123"),
                role="admin",
                oab=None,
                ativo=True
            ),
            Usuario(
                nome="Dr. João Silva",
                email="joao@advocacia.com.br",
                senha_hash=get_password_hash("advogado123"),
                role="advogado",
                oab="OAB/SP 123.456",
                ativo=True
            ),
            Usuario(
                nome="Maria Santos",
                email="maria@escritorio.com.br",
                senha_hash=get_password_hash("estagiario123"),
                role="estagiario",
                oab=None,
                ativo=True
            ),
        ]
        
        for usuario in usuarios:
            session.add(usuario)
        
        await session.commit()
        print(f"✅ {len(usuarios)} usuários criados!")


async def seed_jurisprudencias():
    """Criar jurisprudências de exemplo"""
    async with async_session_maker() as session:
        jurisprudencias = [
            # Direito Penal - Prisão Preventiva
            Jurisprudencia(
                titulo="Prisão preventiva - Fundamentação genérica",
                tribunal="STJ",
                numero_processo="REsp 1.234.567/SP",
                relator="Min. Exemplo Silva",
                orgao_julgador="5ª Turma",
                data_julgamento=datetime(2024, 1, 15),
                ementa="""RECURSO ESPECIAL. PROCESSUAL PENAL. PRISÃO PREVENTIVA. 
                FUNDAMENTAÇÃO GENÉRICA. ILEGALIDADE. ORDEM CONCEDIDA.
                1. A decretação da prisão preventiva exige fundamentação concreta, 
                não bastando a mera referência aos requisitos legais do art. 312 do CPP.
                2. A gravidade abstrata do delito não é fundamento idôneo para 
                a custódia cautelar.
                3. Recurso especial provido para revogar a prisão preventiva.""",
                inteiro_teor="[Inteiro teor do acórdão...]",
                area_direito="Penal",
                palavras_chave=["prisão preventiva", "fundamentação", "art. 312 CPP"],
                relevancia=95
            ),
            Jurisprudencia(
                titulo="Habeas Corpus - Excesso de prazo",
                tribunal="STF",
                numero_processo="HC 654.321/RJ",
                relator="Min. Exemplo Junior",
                orgao_julgador="2ª Turma",
                data_julgamento=datetime(2024, 2, 20),
                ementa="""HABEAS CORPUS. EXCESSO DE PRAZO NA FORMAÇÃO DA CULPA.
                CONSTRANGIMENTO ILEGAL CONFIGURADO. ORDEM CONCEDIDA.
                1. O excesso de prazo na instrução criminal, quando não 
                atribuível à defesa, configura constrangimento ilegal.
                2. A razoável duração do processo é garantia constitucional 
                (art. 5º, LXXVIII, CF).
                3. Ordem concedida para relaxar a prisão do paciente.""",
                inteiro_teor="[Inteiro teor do acórdão...]",
                area_direito="Penal",
                palavras_chave=["habeas corpus", "excesso de prazo", "razoável duração"],
                relevancia=90
            ),
            
            # Direito Civil - Dano Moral
            Jurisprudencia(
                titulo="Dano moral - Quantum indenizatório",
                tribunal="STJ",
                numero_processo="REsp 2.345.678/MG",
                relator="Min. Exemplo Neto",
                orgao_julgador="3ª Turma",
                data_julgamento=datetime(2024, 3, 10),
                ementa="""RECURSO ESPECIAL. RESPONSABILIDADE CIVIL. DANO MORAL.
                QUANTUM INDENIZATÓRIO. RAZOABILIDADE E PROPORCIONALIDADE.
                1. A fixação do valor da indenização por danos morais deve 
                observar os princípios da razoabilidade e proporcionalidade.
                2. Considera-se a extensão do dano, as condições das partes 
                e o caráter pedagógico da condenação.
                3. Valor reduzido para adequar-se aos parâmetros desta Corte.""",
                inteiro_teor="[Inteiro teor do acórdão...]",
                area_direito="Civil",
                palavras_chave=["dano moral", "quantum", "proporcionalidade"],
                relevancia=85
            ),
            
            # Direito do Consumidor
            Jurisprudencia(
                titulo="Relação de consumo - Inversão do ônus da prova",
                tribunal="STJ",
                numero_processo="REsp 3.456.789/RS",
                relator="Min. Exemplo Filho",
                orgao_julgador="4ª Turma",
                data_julgamento=datetime(2024, 4, 5),
                ementa="""RECURSO ESPECIAL. DIREITO DO CONSUMIDOR. INVERSÃO DO 
                ÔNUS DA PROVA. ART. 6º, VIII, CDC. HIPOSSUFICIÊNCIA.
                1. A inversão do ônus da prova é direito básico do consumidor, 
                cabível quando presentes a verossimilhança das alegações ou 
                a hipossuficiência técnica.
                2. Trata-se de regra de instrução, devendo ser determinada 
                preferencialmente na fase de saneamento do processo.
                3. Recurso especial não provido.""",
                inteiro_teor="[Inteiro teor do acórdão...]",
                area_direito="Consumidor",
                palavras_chave=["consumidor", "inversão ônus prova", "hipossuficiência"],
                relevancia=88
            ),
            
            # Direito Trabalhista
            Jurisprudencia(
                titulo="Horas extras - Controle de jornada",
                tribunal="TST",
                numero_processo="RR 4.567.890/PR",
                relator="Min. Exemplo Trabalhista",
                orgao_julgador="7ª Turma",
                data_julgamento=datetime(2024, 5, 12),
                ementa="""RECURSO DE REVISTA. HORAS EXTRAS. ÔNUS DA PROVA.
                ART. 74, §2º, CLT. CONTROLE DE JORNADA.
                1. Empresa com mais de 20 empregados é obrigada a manter 
                controle de jornada.
                2. Não apresentados os cartões de ponto, presume-se verdadeira 
                a jornada declinada na inicial.
                3. Súmula 338 do TST. Recurso de revista não conhecido.""",
                inteiro_teor="[Inteiro teor do acórdão...]",
                area_direito="Trabalhista",
                palavras_chave=["horas extras", "controle jornada", "ônus da prova"],
                relevancia=82
            ),
        ]
        
        for jur in jurisprudencias:
            session.add(jur)
        
        await session.commit()
        print(f"✅ {len(jurisprudencias)} jurisprudências criadas!")


async def seed_legislacao():
    """Criar legislação de exemplo"""
    async with async_session_maker() as session:
        legislacoes = [
            Legislacao(
                tipo="Lei",
                numero="10.406/2002",
                nome="Código Civil",
                ementa="Institui o Código Civil.",
                data_publicacao=datetime(2002, 1, 10),
                vigencia="Em vigor",
                texto_integral="[Texto integral do Código Civil...]",
                link_oficial="http://www.planalto.gov.br/ccivil_03/leis/2002/l10406.htm"
            ),
            Legislacao(
                tipo="Lei",
                numero="13.105/2015",
                nome="Código de Processo Civil",
                ementa="Código de Processo Civil.",
                data_publicacao=datetime(2015, 3, 16),
                vigencia="Em vigor",
                texto_integral="[Texto integral do CPC...]",
                link_oficial="http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm"
            ),
            Legislacao(
                tipo="Decreto-Lei",
                numero="3.689/1941",
                nome="Código de Processo Penal",
                ementa="Código de Processo Penal.",
                data_publicacao=datetime(1941, 10, 3),
                vigencia="Em vigor",
                texto_integral="[Texto integral do CPP...]",
                link_oficial="http://www.planalto.gov.br/ccivil_03/decreto-lei/del3689.htm"
            ),
            Legislacao(
                tipo="Lei",
                numero="8.078/1990",
                nome="Código de Defesa do Consumidor",
                ementa="Dispõe sobre a proteção do consumidor e dá outras providências.",
                data_publicacao=datetime(1990, 9, 11),
                vigencia="Em vigor",
                texto_integral="[Texto integral do CDC...]",
                link_oficial="http://www.planalto.gov.br/ccivil_03/leis/l8078.htm"
            ),
            Legislacao(
                tipo="Decreto-Lei",
                numero="5.452/1943",
                nome="Consolidação das Leis do Trabalho (CLT)",
                ementa="Aprova a Consolidação das Leis do Trabalho.",
                data_publicacao=datetime(1943, 5, 1),
                vigencia="Em vigor",
                texto_integral="[Texto integral da CLT...]",
                link_oficial="http://www.planalto.gov.br/ccivil_03/decreto-lei/del5452.htm"
            ),
        ]
        
        for leg in legislacoes:
            session.add(leg)
        
        await session.commit()
        print(f"✅ {len(legislacoes)} legislações criadas!")


async def seed_doutrina():
    """Criar doutrina de exemplo"""
    async with async_session_maker() as session:
        doutrinas = [
            Doutrina(
                titulo="Manual de Direito Civil",
                autor="Carlos Roberto Gonçalves",
                editora="Saraiva",
                ano_publicacao=2024,
                isbn="978-85-XXX-XXXX-X",
                area_direito="Civil",
                resumo="Manual completo de Direito Civil abordando teoria geral, obrigações, contratos, responsabilidade civil, direitos reais, família e sucessões."
            ),
            Doutrina(
                titulo="Curso de Processo Penal",
                autor="Fernando Capez",
                editora="Saraiva",
                ano_publicacao=2024,
                isbn="978-85-XXX-XXXX-Y",
                area_direito="Penal",
                resumo="Curso completo de processo penal com análise da jurisprudência dos tribunais superiores."
            ),
            Doutrina(
                titulo="Manual de Direito do Consumidor",
                autor="Flávio Tartuce e Daniel Neves",
                editora="GEN",
                ano_publicacao=2024,
                isbn="978-85-XXX-XXXX-Z",
                area_direito="Consumidor",
                resumo="Manual didático sobre direito do consumidor com casos práticos e jurisprudência atualizada."
            ),
            Doutrina(
                titulo="Curso de Direito Processual Civil",
                autor="Fredie Didier Jr.",
                editora="JusPodivm",
                ano_publicacao=2024,
                isbn="978-85-XXX-XXXX-W",
                area_direito="Processual Civil",
                resumo="Curso completo e atualizado de processo civil conforme o CPC/2015."
            ),
        ]
        
        for dout in doutrinas:
            session.add(dout)
        
        await session.commit()
        print(f"✅ {len(doutrinas)} doutrinas criadas!")


async def main():
    """Executar todos os seeds"""
    print("\n🌱 Iniciando seed de dados...\n")
    
    try:
        await create_tables()
        await seed_usuarios()
        await seed_jurisprudencias()
        await seed_legislacao()
        await seed_doutrina()
        
        print("\n✅ Seed concluído com sucesso!")
        print("\n📋 Credenciais de teste:")
        print("   Admin: admin@iajuridica.com.br / admin123")
        print("   Advogado: joao@advocacia.com.br / advogado123")
        print("   Estagiário: maria@escritorio.com.br / estagiario123")
        
    except Exception as e:
        print(f"\n❌ Erro no seed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
