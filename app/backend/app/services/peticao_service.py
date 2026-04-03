"""
Serviço de Petições - Lógica de negócio para geração e gestão de petições
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

from app.core.config import settings
from app.core.llm import LLMEngine as LLMClient, get_llm_engine as get_llm_client
from app.services.rag_engine import RAGEngine, get_rag_engine
from app.services.documento_service import DocumentoService, get_documento_service

logger = logging.getLogger(__name__)


class TipoPeticao(Enum):
    """Tipos de petições suportados"""
    INICIAL = "inicial"
    CONTESTACAO = "contestacao"
    RECURSO = "recurso"
    HABEAS_CORPUS = "habeas_corpus"
    EMBARGOS_DECLARACAO = "embargos_declaracao"
    AGRAVO_INSTRUMENTO = "agravo_instrumento"
    APELACAO = "apelacao"
    MANIFESTACAO = "manifestacao"
    REQUERIMENTO = "requerimento"
    CONTRARRAZOES = "contrarrazoes"
    MEMORIAIS = "memoriais"


class PeticaoService:
    """
    Serviço para geração e gestão de petições jurídicas
    """
    
    # Templates estruturais por tipo de petição
    ESTRUTURA_PETICOES = {
        TipoPeticao.INICIAL.value: [
            "ENDEREÇAMENTO",
            "QUALIFICAÇÃO DAS PARTES",
            "DOS FATOS",
            "DO DIREITO",
            "DOS PEDIDOS",
            "DO VALOR DA CAUSA",
            "REQUERIMENTOS FINAIS"
        ],
        TipoPeticao.CONTESTACAO.value: [
            "ENDEREÇAMENTO",
            "QUALIFICAÇÃO DO RÉU",
            "SÍNTESE DA INICIAL",
            "PRELIMINARES (se houver)",
            "DO MÉRITO",
            "DA IMPUGNAÇÃO AOS DOCUMENTOS",
            "DOS PEDIDOS",
            "REQUERIMENTOS FINAIS"
        ],
        TipoPeticao.HABEAS_CORPUS.value: [
            "ENDEREÇAMENTO",
            "QUALIFICAÇÃO DO PACIENTE E IMPETRANTE",
            "DA AUTORIDADE COATORA",
            "DOS FATOS",
            "DO CONSTRANGIMENTO ILEGAL",
            "DO DIREITO",
            "DOS REQUISITOS PARA CONCESSÃO",
            "DOS PEDIDOS (Liminar e Mérito)",
            "REQUERIMENTOS FINAIS"
        ],
        TipoPeticao.RECURSO.value: [
            "ENDEREÇAMENTO",
            "QUALIFICAÇÃO DO RECORRENTE",
            "DA TEMPESTIVIDADE",
            "DO CABIMENTO",
            "DOS FATOS",
            "DAS RAZÕES DO RECURSO",
            "DO DIREITO",
            "DOS PEDIDOS",
            "REQUERIMENTOS FINAIS"
        ],
        TipoPeticao.APELACAO.value: [
            "ENDEREÇAMENTO",
            "QUALIFICAÇÃO DO APELANTE",
            "DA TEMPESTIVIDADE",
            "DO CABIMENTO",
            "DA SÍNTESE DA SENTENÇA",
            "DAS RAZÕES DO RECURSO",
            "DO DIREITO",
            "DOS PEDIDOS",
            "REQUERIMENTOS FINAIS"
        ],
        TipoPeticao.EMBARGOS_DECLARACAO.value: [
            "ENDEREÇAMENTO",
            "QUALIFICAÇÃO DO EMBARGANTE",
            "DA TEMPESTIVIDADE",
            "DO CABIMENTO",
            "DA OMISSÃO/CONTRADIÇÃO/OBSCURIDADE",
            "DOS PEDIDOS",
            "REQUERIMENTOS FINAIS"
        ],
        TipoPeticao.AGRAVO_INSTRUMENTO.value: [
            "ENDEREÇAMENTO",
            "QUALIFICAÇÃO DO AGRAVANTE",
            "DA TEMPESTIVIDADE",
            "DO CABIMENTO",
            "DA DECISÃO AGRAVADA",
            "DO FUMUS BONI IURIS",
            "DO PERICULUM IN MORA",
            "DOS PEDIDOS (Liminar e Mérito)",
            "REQUERIMENTOS FINAIS"
        ]
    }
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        rag_engine: Optional[RAGEngine] = None,
        documento_service: Optional[DocumentoService] = None
    ):
        self.llm_client = llm_client
        self.rag_engine = rag_engine
        self.documento_service = documento_service
    
    async def _ensure_dependencies(self):
        """Garante que dependências estão inicializadas"""
        if self.llm_client is None:
            self.llm_client = await get_llm_client()
        if self.rag_engine is None:
            self.rag_engine = await get_rag_engine()
        if self.documento_service is None:
            self.documento_service = get_documento_service()
    
    async def gerar_peticao(
        self,
        tipo: str,
        fatos: str,
        fundamentos: Optional[str] = None,
        pedidos: Optional[List[str]] = None,
        partes: Optional[Dict[str, Any]] = None,
        processo: Optional[Dict[str, Any]] = None,
        usar_rag: bool = True,
        usuario_id: int = 0
    ) -> Dict[str, Any]:
        """
        Gera petição usando IA com fundamentação jurídica
        
        Args:
            tipo: Tipo da petição
            fatos: Descrição dos fatos
            fundamentos: Fundamentos jurídicos (opcional)
            pedidos: Lista de pedidos (opcional)
            partes: Dados das partes {autor, reu, advogado, oab}
            processo: Dados do processo {numero, vara, comarca}
            usar_rag: Se deve buscar jurisprudência
            usuario_id: ID do usuário
            
        Returns:
            Petição gerada com metadados
        """
        await self._ensure_dependencies()
        
        start_time = datetime.now()
        
        # Validar tipo
        if tipo not in [t.value for t in TipoPeticao]:
            tipo = TipoPeticao.INICIAL.value
        
        # Buscar jurisprudência relevante via RAG
        jurisprudencias = []
        if usar_rag and self.rag_engine:
            try:
                # Extrair área do direito dos fatos
                area_direito = self._detectar_area_direito(fatos)
                
                # Buscar jurisprudência
                resultados_rag = await self.rag_engine.search(
                    query=fatos[:500],  # Limitar tamanho da query
                    area_direito=area_direito,
                    top_k=5
                )
                
                jurisprudencias = [
                    {
                        "fonte": r.get("fonte", ""),
                        "ementa": r.get("conteudo", "")[:500],
                        "tribunal": r.get("tribunal", ""),
                        "relevancia": r.get("score", 0)
                    }
                    for r in resultados_rag
                    if r.get("tipo") == "jurisprudencia"
                ]
                
            except Exception as e:
                logger.warning(f"Erro ao buscar jurisprudência: {e}")
        
        # Construir contexto para LLM
        contexto = self._construir_contexto(
            tipo=tipo,
            fatos=fatos,
            fundamentos=fundamentos,
            pedidos=pedidos,
            partes=partes,
            processo=processo,
            jurisprudencias=jurisprudencias
        )
        
        # Gerar com LLM
        try:
            resposta_llm = await self.llm_client.generate(
                prompt=contexto["prompt"],
                system_prompt=contexto["system_prompt"],
                temperature=0.3,
                max_tokens=4096
            )
            
            conteudo_peticao = resposta_llm.get("content", "")
            tokens_usados = resposta_llm.get("tokens_used", 0)
            
        except Exception as e:
            logger.error(f"Erro ao gerar petição com LLM: {e}")
            raise
        
        # Calcular confiança
        confianca = self._calcular_confianca(
            conteudo=conteudo_peticao,
            jurisprudencias=jurisprudencias,
            tipo=tipo
        )
        
        # Tempo de processamento
        tempo_processamento = (datetime.now() - start_time).total_seconds()
        
        return {
            "tipo": tipo,
            "conteudo": conteudo_peticao,
            "titulo": self._gerar_titulo(tipo, partes),
            "estrutura": self.ESTRUTURA_PETICOES.get(tipo, []),
            "confianca_ia": confianca,
            "jurisprudencias_utilizadas": jurisprudencias,
            "tokens_utilizados": tokens_usados,
            "tempo_processamento_segundos": tempo_processamento,
            "gerado_em": datetime.now().isoformat(),
            "versao": 1,
            "aviso_legal": (
                "ATENÇÃO: Esta petição foi gerada por inteligência artificial. "
                "Revise cuidadosamente todo o conteúdo antes de utilizar. "
                "Este documento não substitui a análise de advogado habilitado."
            )
        }
    
    def _detectar_area_direito(self, texto: str) -> Optional[str]:
        """Detecta área do direito com base no texto"""
        texto_lower = texto.lower()
        
        areas = {
            "Penal": ["crime", "prisão", "preventiva", "tráfico", "furto", "roubo", 
                     "homicídio", "lesão corporal", "ameaça", "penal", "criminal"],
            "Civil": ["contrato", "dano moral", "indenização", "obrigação", 
                     "responsabilidade civil", "posse", "propriedade"],
            "Trabalhista": ["emprego", "trabalho", "salário", "férias", "rescisão",
                          "hora extra", "FGTS", "trabalhista", "CLT"],
            "Tributário": ["imposto", "tributo", "ICMS", "ISS", "PIS", "COFINS",
                         "fiscal", "tributário", "auto de infração"],
            "Consumidor": ["consumidor", "CDC", "produto", "serviço", "fornecedor",
                         "defeito", "propaganda enganosa"],
            "Família": ["divórcio", "pensão", "guarda", "alimentos", "casamento",
                       "união estável", "inventário", "partilha"],
            "Administrativo": ["licitação", "concurso", "servidor público",
                              "administrativo", "mandado de segurança"]
        }
        
        for area, palavras_chave in areas.items():
            if any(palavra in texto_lower for palavra in palavras_chave):
                return area
        
        return None
    
    def _construir_contexto(
        self,
        tipo: str,
        fatos: str,
        fundamentos: Optional[str],
        pedidos: Optional[List[str]],
        partes: Optional[Dict[str, Any]],
        processo: Optional[Dict[str, Any]],
        jurisprudencias: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Constrói contexto para geração via LLM"""
        
        # System prompt especializado
        system_prompt = """Você é um advogado brasileiro experiente especializado em redação de petições jurídicas.

REGRAS FUNDAMENTAIS:
1. Use APENAS jurisprudências fornecidas no contexto
2. NUNCA invente citações, números de processos ou precedentes
3. Se não houver jurisprudência relevante, fundamente apenas na lei
4. Use linguagem formal jurídica brasileira
5. Siga rigorosamente a estrutura do tipo de petição
6. Cite artigos de lei com precisão
7. Seja objetivo e direto nos argumentos

FORMATAÇÃO:
- Use numeração romana para seções principais (I., II., III.)
- Use alíneas (a, b, c) para subitens
- Mantenha parágrafos coesos
- Inclua espaçamento adequado entre seções"""

        # Montar prompt
        prompt_parts = [
            f"TIPO DE PETIÇÃO: {tipo.upper()}",
            f"\nESTRUTURA ESPERADA:\n{chr(10).join(self.ESTRUTURA_PETICOES.get(tipo, []))}",
        ]
        
        if partes:
            prompt_parts.append(f"\nPARTES:")
            if partes.get("autor"):
                prompt_parts.append(f"- Autor/Requerente: {partes['autor']}")
            if partes.get("reu"):
                prompt_parts.append(f"- Réu/Requerido: {partes['reu']}")
            if partes.get("advogado"):
                prompt_parts.append(f"- Advogado: {partes['advogado']}")
            if partes.get("oab"):
                prompt_parts.append(f"- OAB: {partes['oab']}")
        
        if processo:
            prompt_parts.append(f"\nPROCESSO:")
            if processo.get("numero"):
                prompt_parts.append(f"- Número: {processo['numero']}")
            if processo.get("vara"):
                prompt_parts.append(f"- Vara: {processo['vara']}")
            if processo.get("comarca"):
                prompt_parts.append(f"- Comarca: {processo['comarca']}")
        
        prompt_parts.append(f"\nFATOS:\n{fatos}")
        
        if fundamentos:
            prompt_parts.append(f"\nFUNDAMENTOS JURÍDICOS INDICADOS:\n{fundamentos}")
        
        if pedidos:
            prompt_parts.append(f"\nPEDIDOS:\n" + "\n".join(f"- {p}" for p in pedidos))
        
        if jurisprudencias:
            prompt_parts.append("\nJURISPRUDÊNCIAS DISPONÍVEIS (use APENAS estas):")
            for j in jurisprudencias:
                prompt_parts.append(f"\n[{j['fonte']}] ({j['tribunal']})")
                prompt_parts.append(f"{j['ementa'][:300]}...")
        
        prompt_parts.append(
            "\n\nGere a petição completa seguindo a estrutura indicada. "
            "Fundamente adequadamente cada argumento. "
            "Use as jurisprudências fornecidas quando relevantes."
        )
        
        return {
            "system_prompt": system_prompt,
            "prompt": "\n".join(prompt_parts)
        }
    
    def _calcular_confianca(
        self,
        conteudo: str,
        jurisprudencias: List[Dict[str, Any]],
        tipo: str
    ) -> int:
        """
        Calcula score de confiança da petição (0-100)
        
        Fatores:
        - Presença de jurisprudências citadas
        - Completude da estrutura
        - Tamanho adequado
        - Presença de elementos obrigatórios
        """
        score = 50  # Base
        
        # Jurisprudências utilizadas
        if jurisprudencias:
            score += min(len(jurisprudencias) * 5, 20)
        
        # Verificar estrutura
        estrutura_esperada = self.ESTRUTURA_PETICOES.get(tipo, [])
        secoes_encontradas = 0
        
        for secao in estrutura_esperada:
            if secao.lower() in conteudo.lower():
                secoes_encontradas += 1
        
        if estrutura_esperada:
            completude = secoes_encontradas / len(estrutura_esperada)
            score += int(completude * 15)
        
        # Tamanho adequado
        palavras = len(conteudo.split())
        if 500 <= palavras <= 5000:
            score += 10
        elif palavras > 5000:
            score += 5
        
        # Elementos obrigatórios
        elementos = [
            "EXCELENTÍSSIMO" if tipo != "manifestacao" else "MM.",
            "DOS FATOS" if "fatos" in tipo or tipo in ["inicial", "contestacao", "habeas_corpus"] else None,
            "requerer" in conteudo.lower() or "requer" in conteudo.lower(),
            "termos em que" in conteudo.lower() or "nestes termos" in conteudo.lower()
        ]
        
        elementos_presentes = sum(1 for e in elementos if e)
        score += elementos_presentes * 2
        
        return min(max(score, 0), 100)
    
    def _gerar_titulo(self, tipo: str, partes: Optional[Dict[str, Any]]) -> str:
        """Gera título formatado para a petição"""
        titulos = {
            TipoPeticao.INICIAL.value: "PETIÇÃO INICIAL",
            TipoPeticao.CONTESTACAO.value: "CONTESTAÇÃO",
            TipoPeticao.RECURSO.value: "RECURSO",
            TipoPeticao.HABEAS_CORPUS.value: "HABEAS CORPUS",
            TipoPeticao.EMBARGOS_DECLARACAO.value: "EMBARGOS DE DECLARAÇÃO",
            TipoPeticao.AGRAVO_INSTRUMENTO.value: "AGRAVO DE INSTRUMENTO",
            TipoPeticao.APELACAO.value: "APELAÇÃO",
            TipoPeticao.MANIFESTACAO.value: "MANIFESTAÇÃO",
            TipoPeticao.REQUERIMENTO.value: "REQUERIMENTO",
            TipoPeticao.CONTRARRAZOES.value: "CONTRARRAZÕES",
            TipoPeticao.MEMORIAIS.value: "MEMORIAIS"
        }
        
        titulo = titulos.get(tipo, "PETIÇÃO")
        
        if partes and partes.get("autor"):
            titulo += f" - {partes['autor'][:30]}"
        
        return titulo
    
    async def exportar_peticao(
        self,
        conteudo: str,
        titulo: str,
        formato: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Exporta petição para formato especificado
        
        Args:
            conteudo: Conteúdo da petição
            titulo: Título
            formato: Formato (docx, pdf)
            metadata: Metadados adicionais
            
        Returns:
            Bytes do arquivo
        """
        await self._ensure_dependencies()
        
        if formato.lower() == "pdf":
            return await self.documento_service.gerar_pdf(conteudo, titulo, metadata)
        else:
            return await self.documento_service.gerar_docx(conteudo, titulo, metadata)
    
    def listar_tipos_peticao(self) -> List[Dict[str, Any]]:
        """Lista tipos de petições disponíveis com estruturas"""
        return [
            {
                "tipo": t.value,
                "nome": t.value.replace("_", " ").title(),
                "estrutura": self.ESTRUTURA_PETICOES.get(t.value, [])
            }
            for t in TipoPeticao
        ]
    
    def validar_peticao(self, conteudo: str, tipo: str) -> Dict[str, Any]:
        """
        Valida estrutura e conteúdo de petição
        
        Returns:
            Resultado da validação com warnings e erros
        """
        validacoes = []
        warnings = []
        errors = []
        
        # Verificar tamanho mínimo
        palavras = len(conteudo.split())
        if palavras < 100:
            errors.append("Petição muito curta (mínimo 100 palavras)")
        elif palavras < 300:
            warnings.append("Petição curta - considere expandir argumentos")
        
        validacoes.append({
            "item": "Tamanho",
            "status": "error" if palavras < 100 else "warning" if palavras < 300 else "ok",
            "mensagem": f"{palavras} palavras"
        })
        
        # Verificar estrutura
        estrutura = self.ESTRUTURA_PETICOES.get(tipo, [])
        secoes_faltantes = []
        
        for secao in estrutura:
            if secao.lower() not in conteudo.lower():
                secoes_faltantes.append(secao)
        
        if secoes_faltantes:
            warnings.append(f"Seções não encontradas: {', '.join(secoes_faltantes)}")
        
        validacoes.append({
            "item": "Estrutura",
            "status": "warning" if secoes_faltantes else "ok",
            "mensagem": f"{len(estrutura) - len(secoes_faltantes)}/{len(estrutura)} seções"
        })
        
        # Verificar endereçamento
        tem_enderecamento = any(
            termo in conteudo.upper()
            for termo in ["EXCELENTÍSSIMO", "MM.", "MERITÍSSIMO", "ILUSTRÍSSIMO"]
        )
        
        if not tem_enderecamento:
            errors.append("Endereçamento não encontrado")
        
        validacoes.append({
            "item": "Endereçamento",
            "status": "error" if not tem_enderecamento else "ok",
            "mensagem": "Presente" if tem_enderecamento else "Ausente"
        })
        
        # Verificar pedidos
        tem_pedidos = any(
            termo in conteudo.lower()
            for termo in ["requer", "requerer", "pede", "pleiteia"]
        )
        
        if not tem_pedidos:
            warnings.append("Pedidos não claramente identificados")
        
        validacoes.append({
            "item": "Pedidos",
            "status": "warning" if not tem_pedidos else "ok",
            "mensagem": "Identificados" if tem_pedidos else "Não identificados"
        })
        
        # Verificar fechamento
        tem_fechamento = any(
            termo in conteudo.lower()
            for termo in ["termos em que", "nestes termos", "pede deferimento"]
        )
        
        if not tem_fechamento:
            warnings.append("Fechamento formal não encontrado")
        
        validacoes.append({
            "item": "Fechamento",
            "status": "warning" if not tem_fechamento else "ok",
            "mensagem": "Presente" if tem_fechamento else "Ausente"
        })
        
        return {
            "valido": len(errors) == 0,
            "validacoes": validacoes,
            "warnings": warnings,
            "errors": errors,
            "total_ok": sum(1 for v in validacoes if v["status"] == "ok"),
            "total_warnings": len(warnings),
            "total_errors": len(errors)
        }


# Instância global
_peticao_service = None


async def get_peticao_service() -> PeticaoService:
    """Dependency para obter PeticaoService"""
    global _peticao_service
    if _peticao_service is None:
        _peticao_service = PeticaoService()
    return _peticao_service
