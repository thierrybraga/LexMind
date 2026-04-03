from app.schemas.cliente_schemas import ClienteIntakeRequest, AdvogadoOutput, ClienteResumo, ContatoAdv, AnaliseJuridica, PecaSugerida
from app.core.llm import llm_engine
from app.core.config import settings
import logging
import json
import re

logger = logging.getLogger(__name__)


class IAJuridicaService:
    async def processar_caso(self, intake: ClienteIntakeRequest) -> AdvogadoOutput:
        """
        Processa os dados do cliente e gera o dossiê jurídico via OpenAI.

        Raises:
            RuntimeError: Se OPENAI_API_KEY não estiver configurada.
            ValueError: Se a resposta do LLM não for um JSON válido com a estrutura esperada.
        """
        if not settings.OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY não configurada. "
                "Defina a variável de ambiente OPENAI_API_KEY para usar o serviço de IA jurídica."
            )

        return await self._processar_com_llm(intake)

    async def _processar_com_llm(self, intake: ClienteIntakeRequest) -> AdvogadoOutput:
        """Processamento real via OpenAI."""
        prompt = self._construir_prompt(intake)

        response = await llm_engine.generate(
            prompt=prompt,
            system_prompt="Responda apenas com JSON válido, sem markdown ou texto adicional.",
            temperature=0.2,
            max_tokens=2000,
        )
        content = (response.get("content") or "").strip()

        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            raise ValueError(f"LLM retornou resposta sem JSON válido: {content[:200]}")

        try:
            llm_response = json.loads(match.group(0))
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON inválido na resposta do LLM: {e}") from e

        analise_data = llm_response.get("analise_juridica")
        peca_data = llm_response.get("peca_sugerida")

        if not analise_data:
            raise ValueError("Resposta do LLM não contém 'analise_juridica'.")
        if not peca_data:
            raise ValueError("Resposta do LLM não contém 'peca_sugerida'.")

        return AdvogadoOutput(
            cliente=ClienteResumo(
                nome=intake.dados_pessoais.nome_completo,
                cpf=intake.dados_pessoais.cpf,
                contato=ContatoAdv(
                    email=intake.dados_pessoais.email,
                    telefone=intake.dados_pessoais.telefone,
                ),
            ),
            analise_juridica=AnaliseJuridica(**analise_data),
            peca_sugerida=PecaSugerida(**peca_data),
            alertas=llm_response.get("alertas", []),
        )

    def _construir_prompt(self, intake: ClienteIntakeRequest) -> str:
        return f"""
        Você é um Assistente Jurídico Sênior especialista em Direito Brasileiro.
        Analise o seguinte caso e gere um parecer técnico estruturado em JSON.

        RELATO DO CLIENTE:
        "{intake.dados_juridicos.relato_da_causa}"

        DOCUMENTOS:
        {", ".join(intake.dados_juridicos.documentos_anexos)}

        Responda APENAS com um JSON válido seguindo esta estrutura exata:
        {{
            "analise_juridica": {{
                "tipo_causa": "Área do Direito",
                "acao_cabivel": "Nome da Ação",
                "competencia": "Juízo Competente",
                "foro": "Foro Adequado (considere cidade: {intake.dados_pessoais.endereco.cidade})",
                "prazo_critico": "Prazo prescricional ou decadencial aplicável"
            }},
            "peca_sugerida": {{
                "estrutura": ["Tópico 1", "Tópico 2", "Tópico 3"]
            }},
            "alertas": ["Risco 1", "Sugestão 1"]
        }}
        """
