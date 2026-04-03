"""
Módulo de Integração com LLM - OpenAI
Orquestrador Jurídico com Chain of Thought
"""

import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from app.core.config import settings

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    AsyncOpenAI = None  # type: ignore
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


class TipoPeca(Enum):
    """Tipos de peças processuais"""
    INICIAL = "inicial"
    CONTESTACAO = "contestacao"
    RECURSO = "recurso"
    HABEAS_CORPUS = "habeas_corpus"
    EMBARGOS = "embargos"
    AGRAVO = "agravo"
    APELACAO = "apelacao"
    PARECER = "parecer"
    MEMORIAIS = "memoriais"


@dataclass
class LLMResponse:
    """Resposta do LLM"""
    content: str
    tokens_used: int
    model: str
    sources_used: List[str] = None
    confidence: float = 0.0


class LLMEngine:
    """Engine de integração com LLM para processamento jurídico"""
    
    def __init__(self):
        if OPENAI_AVAILABLE and settings.OPENAI_API_KEY:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            self.client = None
            if not OPENAI_AVAILABLE:
                logger.warning("Pacote 'openai' não instalado. LLM indisponível.")
            elif not settings.OPENAI_API_KEY:
                logger.warning("OPENAI_API_KEY não configurada. LLM indisponível.")
        self.model = settings.OPENAI_MODEL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE
        
    async def _call_openai(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        stream: bool = False
    ) -> tuple[str, int]:
        """Chamada à API da OpenAI"""
        if not self.client:
            raise Exception("OpenAI não configurado. Defina OPENAI_API_KEY no ambiente.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            content = response.choices[0].message.content or ""
            usage = response.usage.total_tokens if response.usage else None
            tokens_used = usage if usage is not None else len(content.split()) * 2
            return content, tokens_used
        except Exception as e:
            logger.error(f"Erro na chamada à OpenAI: {e}")
            raise Exception(f"Erro ao comunicar com LLM: {str(e)}")

    def _build_system_prompt_juridico(self) -> str:
        """Constrói prompt de sistema jurídico"""
        return """Você é um assistente jurídico especializado em direito brasileiro.

REGRAS FUNDAMENTAIS:
1. NUNCA invente jurisprudência ou citações
2. SEMPRE cite a fonte quando mencionar decisões ou leis
3. Diferencie entendimento MAJORITÁRIO de MINORITÁRIO
4. Use linguagem formal e técnica jurídica
5. Seja preciso nas referências a artigos e dispositivos legais

FORMATAÇÃO:
- Use estrutura clara com tópicos quando apropriado
- Cite dispositivos no formato: Art. X, da Lei Y
- Cite jurisprudência no formato: Tribunal, Recurso Nº, Relator, Data

AVISO IMPORTANTE:
Este conteúdo é gerado por IA e não substitui a consulta a um advogado habilitado.
Toda informação deve ser verificada antes do uso em processos reais."""

    async def processar_consulta_juridica(
        self,
        consulta: str,
        contexto_rag: List[Dict[str, Any]] = None,
        historico: List[Dict[str, str]] = None
    ) -> LLMResponse:
        """Processa consulta jurídica com RAG context"""
        
        # Construir contexto
        context_text = ""
        sources = []
        
        if contexto_rag:
            context_text = "\n\n=== CONTEXTO JURÍDICO (RAG) ===\n"
            for i, doc in enumerate(contexto_rag, 1):
                context_text += f"\n[{i}] {doc.get('fonte', 'Fonte não identificada')}:\n"
                context_text += f"{doc.get('conteudo', '')}\n"
                sources.append(doc.get('fonte', f'Documento {i}'))
        
        # Construir prompt final
        prompt = f"""
{context_text}

=== CONSULTA ===
{consulta}

=== INSTRUÇÕES ===
1. Analise a consulta considerando o contexto fornecido
2. Fundamente sua resposta nas fontes disponíveis
3. Se não houver informação suficiente, indique claramente
4. Cite as fontes utilizadas
"""
        
        system_prompt = self._build_system_prompt_juridico()
        
        content, tokens_used = await self._call_openai(prompt, system_prompt)
        
        return LLMResponse(
            content=content,
            tokens_used=tokens_used,
            model=self.model,
            sources_used=sources,
            confidence=0.85 if contexto_rag else 0.5
        )

    async def gerar_peticao(
        self,
        tipo_peca: TipoPeca,
        dados_processo: Dict[str, Any],
        jurisprudencias: List[Dict[str, Any]],
        objetivo: str,
        estilo_tribunal: str = "formal"
    ) -> LLMResponse:
        """Gera petição jurídica estruturada"""
        
        # Template base por tipo de peça
        templates = {
            TipoPeca.INICIAL: self._template_inicial(),
            TipoPeca.CONTESTACAO: self._template_contestacao(),
            TipoPeca.RECURSO: self._template_recurso(),
            TipoPeca.HABEAS_CORPUS: self._template_hc(),
        }
        
        template_base = templates.get(tipo_peca, self._template_generico())
        
        # Formatar jurisprudências
        juris_text = "\n".join([
            f"- {j.get('tribunal', 'N/D')}: {j.get('ementa', 'N/D')} ({j.get('numero', 'N/D')})"
            for j in jurisprudencias
        ])
        
        prompt = f"""
=== DADOS DO PROCESSO ===
{json.dumps(dados_processo, indent=2, ensure_ascii=False)}

=== JURISPRUDÊNCIAS APLICÁVEIS ===
{juris_text}

=== OBJETIVO DA PEÇA ===
{objetivo}

=== ESTILO ===
{estilo_tribunal}

=== TEMPLATE BASE ===
{template_base}

=== INSTRUÇÕES ===
Gere uma {tipo_peca.value} completa seguindo o template, fundamentada nas jurisprudências fornecidas.
Mantenha linguagem formal e técnica.
Cite corretamente todas as fontes.
"""
        
        system_prompt = """Você é um advogado experiente redigindo peças processuais.
Use linguagem jurídica formal e técnica.
Estruture a peça de forma profissional.
Cite corretamente leis, doutrinas e jurisprudências."""
        
        content, tokens_used = await self._call_openai(prompt, system_prompt)
        
        sources = [j.get('numero', 'N/D') for j in jurisprudencias]
        
        return LLMResponse(
            content=content,
            tokens_used=tokens_used,
            model=self.model,
            sources_used=sources,
            confidence=0.9
        )

    async def analisar_processo(
        self,
        dados_processo: Dict[str, Any],
        movimentacoes: List[Dict[str, Any]]
    ) -> LLMResponse:
        """Analisa processo e sugere estratégias"""
        
        prompt = f"""
=== DADOS DO PROCESSO ===
{json.dumps(dados_processo, indent=2, ensure_ascii=False)}

=== MOVIMENTAÇÕES ===
{json.dumps(movimentacoes[-10:], indent=2, ensure_ascii=False)}

=== ANÁLISE SOLICITADA ===
1. Situação atual do processo
2. Próximos passos prováveis
3. Prazos relevantes
4. Sugestões de atuação
5. Riscos identificados
"""
        
        content, tokens_used = await self._call_openai(prompt, self._build_system_prompt_juridico())
        
        return LLMResponse(
            content=content,
            tokens_used=tokens_used,
            model=self.model,
            sources_used=[],
            confidence=0.75
        )

    def _template_inicial(self) -> str:
        return """
EXCELENTÍSSIMO(A) SENHOR(A) DOUTOR(A) JUIZ(A) DE DIREITO DA ___ VARA [ESPECIALIDADE] DA COMARCA DE [COMARCA] - [ESTADO]

[QUALIFICAÇÃO DO AUTOR]

vem, respeitosamente, perante Vossa Excelência, por seu advogado que esta subscreve, propor a presente

AÇÃO [TIPO]

em face de

[QUALIFICAÇÃO DO RÉU]

pelos fatos e fundamentos a seguir expostos:

I - DOS FATOS
[Narração dos fatos]

II - DO DIREITO
[Fundamentação jurídica]

III - DA JURISPRUDÊNCIA
[Citações jurisprudenciais]

IV - DOS PEDIDOS
[Pedidos específicos]

V - DO VALOR DA CAUSA
[Valor]

Termos em que,
Pede deferimento.

[Local], [Data].

[Advogado]
OAB/[Estado] nº [Número]
"""

    def _template_contestacao(self) -> str:
        return """
EXCELENTÍSSIMO(A) SENHOR(A) DOUTOR(A) JUIZ(A) DE DIREITO...

Processo nº: [NÚMERO]

[QUALIFICAÇÃO DO RÉU], já qualificado nos autos em epígrafe, vem, respeitosamente, por seu advogado, apresentar

CONTESTAÇÃO

à ação proposta por [AUTOR], pelos seguintes fundamentos:

I - SÍNTESE DA AÇÃO

II - PRELIMINARES
[Se houver]

III - DO MÉRITO

IV - DA JURISPRUDÊNCIA

V - DOS PEDIDOS

Termos em que,
Pede deferimento.
"""

    def _template_recurso(self) -> str:
        return """
EGRÉGIO TRIBUNAL [NOME]

Processo nº: [NÚMERO]

[RECORRENTE], já qualificado, vem interpor

RECURSO [TIPO]

contra a r. decisão/sentença de fls., pelos seguintes fundamentos:

I - DA TEMPESTIVIDADE

II - DOS FATOS

III - DAS RAZÕES DO RECURSO

IV - DA JURISPRUDÊNCIA

V - DOS PEDIDOS

Termos em que,
Pede provimento.
"""

    def _template_hc(self) -> str:
        return """
EXCELENTÍSSIMO(A) SENHOR(A) DOUTOR(A) DESEMBARGADOR(A) PRESIDENTE DO TRIBUNAL...

HABEAS CORPUS COM PEDIDO DE LIMINAR

Impetrante: [ADVOGADO]
Paciente: [NOME]
Autoridade Coatora: [AUTORIDADE]

I - DOS FATOS

II - DO DIREITO
[Fundamentação sobre ilegalidade/abuso]

III - DO PEDIDO DE LIMINAR

IV - DOS PEDIDOS

Termos em que,
Pede deferimento.
"""

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Método genérico de geração - interface simplificada para chamadas diretas.
        Retorna dict com 'content' e 'tokens_used'.
        """
        if not self.client:
            raise RuntimeError(
                "OpenAI não configurado. Defina OPENAI_API_KEY no arquivo .env."
            )

        effective_temp = temperature if temperature is not None else self.temperature
        effective_max = max_tokens if max_tokens is not None else self.max_tokens

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=effective_temp,
                max_tokens=effective_max,
            )
            content = response.choices[0].message.content or ""
            usage = response.usage.total_tokens if response.usage else None
            tokens_used = usage if usage is not None else len(content.split()) * 2
            return {
                "content": content,
                "tokens_used": tokens_used,
            }
        except Exception as e:
            logger.error(f"Erro na chamada à OpenAI (generate): {e}")
            raise

    def _template_generico(self) -> str:
        return """
[ENDEREÇAMENTO]

[QUALIFICAÇÃO]

[TIPO DE PEÇA]

[FUNDAMENTAÇÃO]

[PEDIDOS]

Termos em que,
Pede deferimento.
"""


# Instância global
llm_engine = LLMEngine()


async def get_llm_engine() -> LLMEngine:
    """Dependency para obter LLM Engine"""
    return llm_engine
