"""
Serviço MCP - Model Context Protocol para ferramentas externas
"""

import logging
import asyncio
import re
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum

from app.core.config import settings
from app.services.cnj_service import get_cnj_service
from app.services.rag_engine import get_rag_engine

logger = logging.getLogger(__name__)


class MCPTool(Enum):
    """Ferramentas MCP disponíveis"""
    BUSCAR_JURISPRUDENCIA = "buscar_jurisprudencia"
    CONSULTAR_PROCESSO = "consultar_processo"
    CRIAR_DOCUMENTO = "criar_documento"
    CONVERTER_PDF = "converter_pdf"
    BUSCAR_LEI = "buscar_lei"
    CALCULAR_PRAZOS = "calcular_prazos"
    VALIDAR_DOCUMENTO = "validar_documento"
    PESQUISAR_DOUTRINHA = "pesquisar_doutrina"
    ANALISAR_DOCUMENTO = "analisar_documento"


class MCPService:
    """
    Serviço MCP para execução de ferramentas externas em sandbox controlado
    """

    # Ferramentas permitidas por padrão
    ALLOWED_TOOLS = [
        MCPTool.BUSCAR_JURISPRUDENCIA,
        MCPTool.CONSULTAR_PROCESSO,
        MCPTool.CRIAR_DOCUMENTO,
        MCPTool.CONVERTER_PDF,
        MCPTool.BUSCAR_LEI,
        MCPTool.CALCULAR_PRAZOS,
        MCPTool.VALIDAR_DOCUMENTO,
        MCPTool.PESQUISAR_DOUTRINHA,
        MCPTool.ANALISAR_DOCUMENTO,
    ]

    def __init__(self):
        self.execution_timeout = 30  # segundos
        self.tools_registry: Dict[str, Callable] = {}
        self._register_tools()

    def _register_tools(self):
        """Registra todas as ferramentas disponíveis"""
        self.tools_registry = {
            MCPTool.BUSCAR_JURISPRUDENCIA.value: self._buscar_jurisprudencia,
            MCPTool.CONSULTAR_PROCESSO.value: self._consultar_processo,
            MCPTool.CRIAR_DOCUMENTO.value: self._criar_documento,
            MCPTool.CONVERTER_PDF.value: self._converter_pdf,
            MCPTool.BUSCAR_LEI.value: self._buscar_lei,
            MCPTool.CALCULAR_PRAZOS.value: self._calcular_prazos,
            MCPTool.VALIDAR_DOCUMENTO.value: self._validar_documento,
            MCPTool.PESQUISAR_DOUTRINHA.value: self._pesquisar_doutrina,
            MCPTool.ANALISAR_DOCUMENTO.value: self._analisar_documento,
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        Lista todas as ferramentas MCP disponíveis

        Returns:
            Lista de ferramentas com descrições
        """
        tools = [
            {
                "name": MCPTool.BUSCAR_JURISPRUDENCIA.value,
                "description": "Busca jurisprudência em tribunais superiores",
                "parameters": {
                    "query": {"type": "string", "description": "Termos de busca"},
                    "tribunal": {"type": "string", "description": "Tribunal (STF, STJ, etc.)", "optional": True},
                    "area": {"type": "string", "description": "Área do direito", "optional": True},
                    "limite": {"type": "integer", "description": "Número máximo de resultados", "default": 10}
                }
            },
            {
                "name": MCPTool.CONSULTAR_PROCESSO.value,
                "description": "Consulta dados de processo judicial via número CNJ",
                "parameters": {
                    "numero_cnj": {"type": "string", "description": "Número do processo no formato CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO)"}
                }
            },
            {
                "name": MCPTool.CRIAR_DOCUMENTO.value,
                "description": "Cria documento jurídico (petição, contrato, etc.)",
                "parameters": {
                    "tipo": {"type": "string", "description": "Tipo do documento"},
                    "conteudo": {"type": "string", "description": "Conteúdo do documento"},
                    "formato": {"type": "string", "description": "Formato de saída (docx, pdf)", "default": "docx"}
                }
            },
            {
                "name": MCPTool.CONVERTER_PDF.value,
                "description": "Converte documento para PDF",
                "parameters": {
                    "documento_id": {"type": "string", "description": "ID do documento a converter"}
                }
            },
            {
                "name": MCPTool.BUSCAR_LEI.value,
                "description": "Busca legislação por número ou tema",
                "parameters": {
                    "query": {"type": "string", "description": "Número da lei ou termos de busca"},
                    "tipo": {"type": "string", "description": "Tipo (lei, decreto, portaria)", "optional": True}
                }
            },
            {
                "name": MCPTool.CALCULAR_PRAZOS.value,
                "description": "Calcula prazos processuais",
                "parameters": {
                    "data_inicial": {"type": "string", "description": "Data inicial (YYYY-MM-DD)"},
                    "tipo_prazo": {"type": "string", "description": "Tipo do prazo (úteis, corridos)"},
                    "quantidade_dias": {"type": "integer", "description": "Quantidade de dias"},
                    "estado": {"type": "string", "description": "UF para feriados estaduais (ex.: SP)", "optional": True}
                }
            },
            {
                "name": MCPTool.VALIDAR_DOCUMENTO.value,
                "description": "Valida estrutura e formatação de documento jurídico",
                "parameters": {
                    "documento_id": {"type": "string", "description": "ID do documento a validar"},
                    "tipo": {"type": "string", "description": "Tipo esperado do documento"}
                }
            },
            {
                "name": MCPTool.PESQUISAR_DOUTRINHA.value,
                "description": "Pesquisa em base de doutrina jurídica",
                "parameters": {
                    "query": {"type": "string", "description": "Termos de busca"},
                    "autores": {"type": "array", "description": "Lista de autores", "optional": True},
                    "area": {"type": "string", "description": "Área do direito", "optional": True}
                }
            },
            {
                "name": MCPTool.ANALISAR_DOCUMENTO.value,
                "description": "Analisa conteúdo de documento com IA",
                "parameters": {
                    "conteudo": {"type": "string", "description": "Conteúdo do documento para análise"},
                    "tipo_analise": {"type": "string", "description": "Tipo de análise (geral, riscos, conformidade)", "optional": True}
                }
            }
        ]

        return tools

    async def execute(
        self,
        tool_name: str = None,
        arguments: Dict[str, Any] = None,
        user_id: int = 0,
        *,
        tool: str = None,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        # Compatibilidade com chamadas usando tool=/params=
        if tool is not None and tool_name is None:
            tool_name = tool
        if params is not None and arguments is None:
            arguments = params
        if arguments is None:
            arguments = {}
        """
        Executa uma ferramenta MCP em sandbox controlado

        Args:
            tool_name: Nome da ferramenta
            arguments: Argumentos para a ferramenta
            user_id: ID do usuário executando

        Returns:
            Resultado da execução
        """
        # Validar ferramenta permitida
        if tool_name not in [t.value for t in self.ALLOWED_TOOLS]:
            return {
                "success": False,
                "error": f"Ferramenta '{tool_name}' não permitida",
                "tool": tool_name
            }

        # Buscar handler da ferramenta
        handler = self.tools_registry.get(tool_name)
        if not handler:
            return {
                "success": False,
                "error": f"Ferramenta '{tool_name}' não encontrada",
                "tool": tool_name
            }

        # Executar com timeout
        start_time = datetime.now()

        try:
            result = await asyncio.wait_for(
                handler(arguments),
                timeout=self.execution_timeout
            )

            execution_time = (datetime.now() - start_time).total_seconds()

            return {
                "success": True,
                "tool": tool_name,
                "result": result,
                "execution_time_seconds": execution_time,
                "executed_at": datetime.now().isoformat()
            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Timeout na execução da ferramenta (>{self.execution_timeout}s)",
                "tool": tool_name
            }
        except Exception as e:
            logger.error(f"Erro ao executar ferramenta {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool": tool_name
            }

    # === Implementações das Ferramentas ===

    async def _buscar_jurisprudencia(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Busca jurisprudência via RAG Engine"""
        query = args.get("query", "")
        tribunal = args.get("tribunal")
        area = args.get("area")
        limite = args.get("limite", 10)

        try:
            rag = await get_rag_engine()
            resultados = await rag.search(
                query=query,
                tribunal=tribunal,
                area_direito=area,
                top_k=limite
            )

            return {
                "query": query,
                "total_encontrados": len(resultados),
                "resultados": resultados,
                "fonte": "RAG Engine (ChromaDB)"
            }
        except Exception as e:
            logger.error(f"Erro ao buscar jurisprudência no MCP: {e}")
            return {"error": str(e)}

    async def _consultar_processo(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Consulta processo via CNJ DataJud Real"""
        numero_cnj = args.get("numero_cnj", "")

        # Validar formato CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO
        padrao_cnj = r'^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$'
        if not re.match(padrao_cnj, numero_cnj):
            return {
                "error": "Número CNJ inválido. Formato esperado: NNNNNNN-DD.AAAA.J.TR.OOOO"
            }

        try:
            cnj_service = get_cnj_service()
            dados = await cnj_service.consultar_processo(numero_cnj)
            return dados
        except Exception as e:
            logger.error(f"Erro ao consultar processo MCP: {e}")
            return {"error": str(e)}

    async def _criar_documento(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Cria documento jurídico real via DocumentoService (DOCX ou PDF)."""
        from app.services.documento_service import get_documento_service
        import os

        tipo = args.get("tipo", "petição")
        conteudo = args.get("conteudo", "")
        formato = args.get("formato", "docx").lower()

        if not conteudo:
            return {"error": "O campo 'conteudo' é obrigatório."}

        doc_service = get_documento_service()
        documento_id = f"doc_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        titulo = tipo.capitalize()

        try:
            if formato == "pdf":
                file_bytes = await doc_service.gerar_pdf(conteudo=conteudo, titulo=titulo)
                extensao = "pdf"
            else:
                file_bytes = await doc_service.gerar_docx(conteudo=conteudo, titulo=titulo)
                extensao = "docx"

            output_dir = settings.OUTPUT_DIR
            os.makedirs(output_dir, exist_ok=True)
            caminho = os.path.join(output_dir, f"{documento_id}.{extensao}")

            with open(caminho, "wb") as f:
                f.write(file_bytes)

            logger.info(f"Documento criado via MCP: {caminho}")

            return {
                "documento_id": documento_id,
                "tipo": tipo,
                "formato": extensao,
                "tamanho_bytes": len(file_bytes),
                "caminho": caminho,
                "criado_em": datetime.now().isoformat(),
                "status": "criado",
            }
        except Exception as e:
            logger.error(f"Erro ao criar documento MCP: {e}")
            return {"error": str(e)}

    async def _converter_pdf(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Converte documento DOCX existente para PDF via DocumentoService."""
        from app.services.documento_service import get_documento_service
        import os

        documento_id = args.get("documento_id", "")
        if not documento_id:
            return {"error": "O campo 'documento_id' é obrigatório."}

        output_dir = settings.OUTPUT_DIR
        caminho_docx = os.path.join(output_dir, f"{documento_id}.docx")

        if not os.path.exists(caminho_docx):
            return {"error": f"Documento '{documento_id}.docx' não encontrado em {output_dir}."}

        try:
            doc_service = get_documento_service()

            with open(caminho_docx, "rb") as f:
                docx_bytes = f.read()

            texto = await doc_service.extrair_texto_docx(docx_bytes)
            pdf_bytes = await doc_service.gerar_pdf(conteudo=texto, titulo=documento_id)

            caminho_pdf = os.path.join(output_dir, f"{documento_id}.pdf")
            with open(caminho_pdf, "wb") as f:
                f.write(pdf_bytes)

            logger.info(f"Documento convertido para PDF via MCP: {caminho_pdf}")

            return {
                "documento_original": documento_id,
                "documento_pdf": f"{documento_id}.pdf",
                "caminho_pdf": caminho_pdf,
                "tamanho_bytes": len(pdf_bytes),
                "convertido_em": datetime.now().isoformat(),
                "status": "convertido",
            }
        except Exception as e:
            logger.error(f"Erro ao converter PDF MCP: {e}")
            return {"error": str(e)}

    async def _buscar_lei(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Busca legislação via PesquisaJuridicaService (LexML + Planalto)"""
        query = args.get("query", "")
        tipo = args.get("tipo")

        try:
            from app.services.pesquisa_juridica import get_pesquisa_service
            pesquisa = get_pesquisa_service()

            lexml_res = await pesquisa._pesquisar_lexml(query, limit=10)
            planalto_res = pesquisa._legislacao_comum(query, 10)

            resultados = []
            for r in lexml_res + planalto_res:
                resultados.append({
                    "tipo": tipo or r.tipo,
                    "nome": r.titulo,
                    "ementa": r.conteudo,
                    "link": r.url,
                    "fonte": r.fonte,
                    "data": r.data
                })

            # Deduplicar por título
            seen = set()
            unique = []
            for r in resultados:
                if r["nome"] not in seen:
                    seen.add(r["nome"])
                    unique.append(r)

            return {
                "query": query,
                "total_encontrados": len(unique),
                "resultados": unique[:15]
            }
        except Exception as e:
            logger.error(f"Erro buscar_lei MCP: {e}")
            return {"query": query, "total_encontrados": 0, "resultados": [], "error": str(e)}

    async def _calcular_prazos(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Calcula prazos processuais com suporte a feriados"""
        try:
            import holidays
            HAS_HOLIDAYS = True
        except ImportError:
            HAS_HOLIDAYS = False

        data_inicial_str = args.get("data_inicial", "")
        tipo_prazo = args.get("tipo_prazo", "úteis")
        quantidade_dias = args.get("quantidade_dias", 15)
        estado = args.get("estado", "SP")  # Default para SP se não informado

        try:
            data_inicial = datetime.strptime(data_inicial_str, "%Y-%m-%d").date()
        except ValueError:
            return {"error": "Data inicial inválida. Formato esperado: YYYY-MM-DD"}

        # Carregar feriados
        if HAS_HOLIDAYS:
            try:
                br_holidays = holidays.BR(state=estado)
            except Exception:
                br_holidays = holidays.BR()
        else:
            br_holidays = {}

        if tipo_prazo == "corridos":
            data_final = data_inicial + timedelta(days=quantidade_dias)
        else:  # dias úteis
            dias_adicionados = 0
            data_final = data_inicial

            while dias_adicionados < quantidade_dias:
                data_final += timedelta(days=1)

                # Verificar fim de semana
                is_weekend = data_final.weekday() >= 5  # 5=Sáb, 6=Dom

                # Verificar feriado
                is_holiday = data_final in br_holidays if HAS_HOLIDAYS else False

                if not is_weekend and not is_holiday:
                    dias_adicionados += 1

        # Listar feriados no período
        feriados_encontrados: List[str] = []
        if HAS_HOLIDAYS:
            feriados_encontrados = [
                f"{d.strftime('%Y-%m-%d')}: {br_holidays.get(d)}"
                for d in br_holidays
                if data_inicial <= d <= data_final
            ]

        return {
            "data_inicial": data_inicial_str,
            "tipo_prazo": tipo_prazo,
            "quantidade_dias": quantidade_dias,
            "data_final": data_final.strftime("%Y-%m-%d"),
            "dia_semana_final": ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][data_final.weekday()],
            "feriados_periodo": feriados_encontrados,
            "observacao": f"Cálculo considera feriados nacionais e estaduais ({estado})." if HAS_HOLIDAYS else "AVISO: Biblioteca 'holidays' não instalada. Feriados ignorados."
        }

    async def _validar_documento(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida estrutura e conteúdo de documento jurídico via LLM (OpenAI).

        Lê o arquivo do OUTPUT_DIR, extrai o texto e solicita análise ao LLM.
        """
        from app.services.documento_service import get_documento_service
        from app.core.llm import llm_engine
        from app.core.config import settings as cfg
        import os

        documento_id = args.get("documento_id", "")
        tipo = args.get("tipo", "petição")

        if not documento_id:
            return {"error": "O campo 'documento_id' é obrigatório."}

        if not cfg.OPENAI_API_KEY:
            return {"error": "OPENAI_API_KEY não configurada. Validação via LLM indisponível."}

        output_dir = settings.OUTPUT_DIR
        doc_service = get_documento_service()
        texto = ""

        # Tentar ler o documento (docx ou pdf)
        for ext, extrator in [("docx", doc_service.extrair_texto_docx), ("pdf", doc_service.extrair_texto_pdf)]:
            caminho = os.path.join(output_dir, f"{documento_id}.{ext}")
            if os.path.exists(caminho):
                try:
                    with open(caminho, "rb") as f:
                        file_bytes = f.read()
                    texto = await extrator(file_bytes)
                    break
                except Exception as e:
                    logger.warning(f"Erro ao extrair texto de {caminho}: {e}")

        if not texto:
            return {"error": f"Documento '{documento_id}' não encontrado ou sem texto extraível em {output_dir}."}

        prompt = f"""
Você é um revisor jurídico especializado. Analise o documento do tipo "{tipo}" abaixo e
retorne um JSON com a seguinte estrutura:
{{
  "resultado": "válido" ou "inválido",
  "validacoes": [
    {{"item": "NomeDoItem", "status": "ok" | "warning" | "error", "mensagem": "Descrição"}}
  ]
}}

Verifique os seguintes itens: Formatação, Endereçamento, Qualificação das partes,
Fundamentação jurídica, Clareza dos pedidos, Espaço para assinatura.

=== DOCUMENTO ===
{texto[:8000]}
"""
        try:
            response = await llm_engine.generate(
                prompt=prompt,
                system_prompt="Responda apenas com JSON válido, sem markdown ou texto adicional.",
                temperature=0.1,
                max_tokens=1000,
            )
            import json, re
            content = (response.get("content") or "").strip()
            match = re.search(r"\{[\s\S]*\}", content)
            if not match:
                raise ValueError("LLM não retornou JSON válido.")
            data = json.loads(match.group(0))
            validacoes = data.get("validacoes", [])
            return {
                "documento_id": documento_id,
                "tipo": tipo,
                "validado_em": datetime.now().isoformat(),
                "resultado": data.get("resultado", "indeterminado"),
                "validacoes": validacoes,
                "total_ok": sum(1 for v in validacoes if v.get("status") == "ok"),
                "total_warnings": sum(1 for v in validacoes if v.get("status") == "warning"),
                "total_errors": sum(1 for v in validacoes if v.get("status") == "error"),
            }
        except Exception as e:
            logger.error(f"Erro na validação LLM MCP: {e}")
            return {"error": str(e)}

    async def _analisar_documento(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analisa documento com IA"""
        from app.services.documento_service import get_documento_service

        conteudo = args.get("conteudo", "")
        tipo_analise = args.get("tipo_analise", "geral")

        try:
            doc_service = get_documento_service()
            if hasattr(doc_service, 'analisar_documento'):
                return await doc_service.analisar_documento(conteudo, tipo_analise)
            else:
                return {"error": "Serviço de análise não implementado no DocumentoService"}
        except Exception as e:
            logger.error(f"Erro ao analisar documento MCP: {e}")
            return {"error": str(e)}

    async def _pesquisar_doutrina(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pesquisa doutrina jurídica via RAG Engine (ChromaDB local) + LexML.

        Busca semântica na base vetorial local (documentos doutrinários previamente indexados)
        e complementa com resultados do LexML (legislação que embasa a doutrina).
        """
        query = args.get("query", "")
        autores = args.get("autores", [])
        area = args.get("area")

        if not query:
            return {"error": "O campo 'query' é obrigatório."}

        resultados = []

        # 1. Busca semântica na base vetorial local (documentos indexados com tipo=doutrina)
        try:
            rag = await get_rag_engine()
            rag_results = await rag.search(
                query=query,
                area_direito=area,
                tipo_fonte="doutrina",
                top_k=10,
            )
            for r in rag_results:
                if r.get("tipo") == "doutrina" or "doutrina" in r.get("fonte", "").lower():
                    item = {
                        "id": r.get("id"),
                        "titulo": r.get("titulo") or r.get("ementa") or "Documento doutrinário",
                        "autor": r.get("autor") or r.get("relator") or "Desconhecido",
                        "area": r.get("area") or area or "Geral",
                        "trecho_relevante": r.get("conteudo", "")[:300],
                        "fonte": r.get("fonte", "Base local"),
                        "score": r.get("score", 0),
                    }
                    resultados.append(item)
        except Exception as e:
            logger.warning(f"Erro ao buscar doutrina no RAG: {e}")

        # 2. Complementar com LexML (legislação de base)
        try:
            from app.services.pesquisa_juridica import get_pesquisa_service
            pesquisa = get_pesquisa_service()
            lexml_res = await pesquisa._pesquisar_lexml(query, limit=5)
            for r in lexml_res:
                resultados.append({
                    "id": f"lexml_{r.url}",
                    "titulo": r.titulo,
                    "autor": "LexML Brasil",
                    "area": area or r.tipo,
                    "trecho_relevante": r.conteudo[:300] if r.conteudo else "",
                    "fonte": r.fonte,
                    "url": r.url,
                    "data": r.data,
                    "score": None,
                })
        except Exception as e:
            logger.warning(f"Erro ao buscar doutrina no LexML: {e}")

        # Filtrar por autores se especificado
        if autores:
            resultados = [
                r for r in resultados
                if any(a.lower() in (r.get("autor") or "").lower() for a in autores)
            ]

        return {
            "query": query,
            "filtros": {"autores": autores, "area": area},
            "total_encontrados": len(resultados),
            "resultados": resultados[:15],
            "fontes": ["RAG Engine (base local)", "LexML Brasil"],
        }


# Instância global
_mcp_service: Optional[MCPService] = None


def get_mcp_service() -> MCPService:
    """Dependency para obter MCPService"""
    global _mcp_service
    if _mcp_service is None:
        _mcp_service = MCPService()
    return _mcp_service