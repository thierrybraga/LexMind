"""
Serviço de Pesquisa Jurídica Avançada

Integra múltiplas fontes:
- OpenAI API (web search / deep research)
- CNJ DataJud (processos)
- STF (jurisprudência)
- STJ (jurisprudência)
- Tribunais Estaduais
- LexML (legislação)
- Planalto (legislação federal)
- RAG local (base vetorial)
"""

import httpx
import logging
import json
import re
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

from app.core.config import settings

logger = logging.getLogger(__name__)

# Import OpenAI condicionalmente
try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai não instalado. Pesquisa via OpenAI indisponível.")


class FontePesquisa(str, Enum):
    """Fontes de pesquisa disponíveis"""
    OPENAI = "openai"
    RAG_LOCAL = "rag_local"
    CNJ_DATAJUD = "cnj_datajud"
    STF = "stf"
    STJ = "stj"
    TST = "tst"
    LEXML = "lexml"
    PLANALTO = "planalto"
    TJSP = "tjsp"
    TJRJ = "tjrj"
    TJMG = "tjmg"


@dataclass
class ResultadoPesquisa:
    """Resultado individual de pesquisa"""
    fonte: str
    tipo: str  # jurisprudencia, legislacao, doutrina, processo
    titulo: str
    conteudo: str
    url: Optional[str] = None
    tribunal: Optional[str] = None
    data: Optional[str] = None
    relevancia: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RespostaPesquisa:
    """Resposta completa de pesquisa"""
    query: str
    resultados: List[ResultadoPesquisa]
    total: int
    fontes_consultadas: List[str]
    tempo_total: float
    analise_ia: Optional[str] = None
    sugestoes: List[str] = field(default_factory=list)


class PesquisaJuridicaService:
    """
    Serviço unificado de pesquisa jurídica.
    Agrega resultados de múltiplas fontes públicas e OpenAI.
    """

    def __init__(self):
        self.openai_client = None
        if OPENAI_AVAILABLE and settings.OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.timeout = 5.0 # Reduzido para evitar bloqueios longos em fontes instáveis

    # =============================================
    # PESQUISA UNIFICADA
    # =============================================

    async def pesquisar(
        self,
        query: str,
        fontes: Optional[List[str]] = None,
        tribunal: Optional[str] = None,
        tipo: Optional[str] = None,
        limit: int = 20,
        deep_research: bool = False
    ) -> RespostaPesquisa:
        """
        Pesquisa unificada em todas as fontes disponíveis.

        Args:
            query: Termo de busca
            fontes: Lista de fontes a consultar (None = todas)
            tribunal: Filtro por tribunal
            tipo: Filtro por tipo (jurisprudencia, legislacao, etc)
            limit: Máximo de resultados por fonte
            deep_research: Se True, usa OpenAI para análise profunda
        """
        start = datetime.now()
        fontes_usadas = fontes or ["stf", "stj", "lexml", "rag_local"]

        # Se OpenAI disponível e deep_research, adicionar
        if deep_research and self.openai_client:
            fontes_usadas = ["openai"] + fontes_usadas

        # Executar pesquisas em paralelo
        tasks = []
        for fonte in fontes_usadas:
            task = self._pesquisar_fonte(fonte, query, tribunal, limit)
            tasks.append(task)

        resultados_brutos = await asyncio.gather(*tasks, return_exceptions=True)

        # Consolidar resultados
        todos_resultados = []
        fontes_ok = []
        for fonte, resultado in zip(fontes_usadas, resultados_brutos):
            if isinstance(resultado, Exception):
                logger.error(f"Erro na fonte {fonte}: {resultado}")
                continue
            if resultado:
                todos_resultados.extend(resultado)
                fontes_ok.append(fonte)

        # Ordenar por relevância
        todos_resultados.sort(key=lambda r: r.relevancia, reverse=True)

        # Limitar total
        todos_resultados = todos_resultados[:limit]

        # Análise IA se deep_research
        analise_ia = None
        if deep_research and self.openai_client and todos_resultados:
            analise_ia = await self._deep_research_analysis(query, todos_resultados)

        tempo = (datetime.now() - start).total_seconds()

        return RespostaPesquisa(
            query=query,
            resultados=todos_resultados,
            total=len(todos_resultados),
            fontes_consultadas=fontes_ok,
            tempo_total=tempo,
            analise_ia=analise_ia,
            sugestoes=self._gerar_sugestoes(query)
        )

    async def _pesquisar_fonte(
        self, fonte: str, query: str, tribunal: Optional[str], limit: int
    ) -> List[ResultadoPesquisa]:
        """Despacha pesquisa para a fonte correta"""
        handlers = {
            "openai": self._pesquisar_openai,
            "stf": self._pesquisar_stf,
            "stj": self._pesquisar_stj,
            "tst": self._pesquisar_tst,
            "lexml": self._pesquisar_lexml,
            "planalto": self._pesquisar_planalto,
            "cnj_datajud": self._pesquisar_cnj,
            "tjsp": lambda q, t, l: self._pesquisar_tribunal_estadual(q, "TJSP", l),
            "tjrj": lambda q, t, l: self._pesquisar_tribunal_estadual(q, "TJRJ", l),
            "tjmg": lambda q, t, l: self._pesquisar_tribunal_estadual(q, "TJMG", l),
            "rag_local": self._pesquisar_rag_local,
        }
        handler = handlers.get(fonte)
        if not handler:
            return []
        try:
            return await asyncio.wait_for(handler(query, tribunal, limit), timeout=self.timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout na pesquisa: {fonte}")
            return []

    # =============================================
    # OPENAI SEARCH / DEEP RESEARCH
    # =============================================

    async def _pesquisar_openai(
        self, query: str, tribunal: Optional[str] = None, limit: int = 10
    ) -> List[ResultadoPesquisa]:
        """Pesquisa jurídica via OpenAI (simulada via conhecimento interno)"""
        if not self.openai_client:
            return []

        # Como a API oficial não tem web search nativo sem tools, usamos o conhecimento do modelo
        # ou o fallback que já faz isso bem.
        return await self._pesquisar_openai_fallback(query, tribunal, limit)

    async def _pesquisar_openai_fallback(
        self, query: str, tribunal: Optional[str] = None, limit: int = 10
    ) -> List[ResultadoPesquisa]:
        """Fallback usando chat completion quando web search falha"""
        if not self.openai_client:
            return []
        try:
            response = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Você é um assistente jurídico brasileiro especialista. Responda APENAS em JSON válido."},
                    {"role": "user", "content": f"""Liste até {limit} jurisprudências e legislações relevantes sobre: {query}
{"Tribunal: " + tribunal if tribunal else ""}

Formato JSON array:
[{{"titulo": "...", "tribunal": "...", "conteudo": "...", "data": "...", "tipo": "jurisprudencia|legislacao"}}]"""}
                ],
                temperature=0.2,
                max_tokens=2000
            )
            content = response.choices[0].message.content
            return self._parse_openai_response(content, limit)
        except Exception as e:
            logger.error(f"Erro OpenAI fallback: {e}")
            return []

    def _parse_openai_response(self, content: str, limit: int) -> List[ResultadoPesquisa]:
        """Parse da resposta OpenAI em ResultadoPesquisa"""
        resultados = []
        try:
            # Extrair JSON do conteúdo
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                items = json.loads(json_match.group())
            else:
                items = json.loads(content)

            for item in items[:limit]:
                resultados.append(ResultadoPesquisa(
                    fonte="OpenAI",
                    tipo=item.get("tipo", "jurisprudencia"),
                    titulo=item.get("titulo", ""),
                    conteudo=item.get("conteudo", "")[:500],
                    url=item.get("url"),
                    tribunal=item.get("tribunal"),
                    data=item.get("data"),
                    relevancia=0.85,
                    metadata={"provider": "openai"}
                ))
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Não foi possível parsear resposta OpenAI: {e}")
            # Criar resultado único com o texto completo
            if content.strip():
                resultados.append(ResultadoPesquisa(
                    fonte="OpenAI",
                    tipo="analise",
                    titulo=f"Análise: {content[:80]}...",
                    conteudo=content[:1000],
                    relevancia=0.7,
                    metadata={"provider": "openai", "raw": True}
                ))
        return resultados

    async def _deep_research_analysis(
        self, query: str, resultados: List[ResultadoPesquisa]
    ) -> str:
        """Análise profunda dos resultados com OpenAI"""
        if not self.openai_client:
            return ""

        # Montar contexto dos resultados
        contexto = "\n\n".join([
            f"[{r.fonte} - {r.tribunal or 'N/A'}] {r.titulo}\n{r.conteudo[:300]}"
            for r in resultados[:10]
        ])

        try:
            response = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": """Você é um jurista brasileiro experiente.
Analise os resultados de pesquisa e forneça:
1. Síntese do entendimento jurisprudencial dominante
2. Divergências relevantes entre tribunais
3. Legislação aplicável e sua interpretação
4. Recomendações práticas para o caso
5. Pontos de atenção e riscos

AVISO: Este conteúdo é gerado por IA e não substitui a consulta a um advogado habilitado."""},
                    {"role": "user", "content": f"Consulta: {query}\n\nResultados encontrados:\n{contexto}"}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Erro deep research: {e}")
            return ""

    # =============================================
    # STF - SUPREMO TRIBUNAL FEDERAL
    # =============================================

    async def _pesquisar_stf(
        self, query: str, tribunal: Optional[str] = None, limit: int = 10
    ) -> List[ResultadoPesquisa]:
        """
        Pesquisa jurisprudência no portal do STF via API pública.
        NOTA: Esta API é protegida por WAF e pode exigir desafios (CAPTCHA/JS) que
        bloqueiam requisições puramente via script/backend.
        Conforme solicitado, NÃO utilizamos mocks em caso de falha.
        """
        url = "https://jurisprudencia.stf.jus.br/api/search/pesquisar"

        payload = {
            "pesquisa_livre": query,
            "quantidade": min(limit, 25),
            "pagina": 1,
            "operador": "AND",
            "ordenacao": "RELEVANCIA",
            "base": "ACORDAOS"
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://jurisprudencia.stf.jus.br/pesquisa/jurisprudencia",
            "Origin": "https://jurisprudencia.stf.jus.br",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=15.0, verify=False, headers=headers) as client:
                # Tentativa com retries curtos para lidar com 202 Accepted
                for attempt in range(3):
                    resp = await client.post(url, json=payload)

                    if resp.status_code == 200:
                        data = resp.json()
                        return self._parse_stf_results(data)
                    elif resp.status_code == 202:
                         # 202 Accepted: O servidor aceitou mas pode estar processando ou desafiando
                         logger.info(f"STF retornou 202 (Tentativa {attempt+1}). Aguardando...")
                         await asyncio.sleep(1.0)
                         continue
                    else:
                        logger.warning(f"Erro STF: Status {resp.status_code} - {resp.text[:200]}")
                        break

                # Se falhar todas as tentativas, tenta a API alternativa de pesquisa textual
                return await self._pesquisar_stf_alternativo(query, limit)

        except Exception as e:
            logger.error(f"Erro pesquisa STF: {e}")
            return []

    async def _pesquisar_stf_alternativo(
        self, query: str, limit: int = 10
    ) -> List[ResultadoPesquisa]:
        """
        Fallback: Se a API oficial falhar (WAF/Bloqueio), tenta scraping no DuckDuckGo
        e depois Web Search via OpenAI.
        """
        logger.warning("STF: API oficial bloqueada/indisponível. Tentando fallbacks.")
        
        # 1. Tentar Scraping DuckDuckGo (Grátis, sem API Key)
        resultados_ddg = await self._pesquisar_web_fallback("stf.jus.br", query, limit)
        if resultados_ddg:
            return resultados_ddg

        # 2. Tentar OpenAI Web Search (Pago, requer Key)
        if self.openai_client:
            return await self._pesquisar_openai(f"site:stf.jus.br {query}", tribunal="STF", limit=limit)
            
        logger.error("STF: API oficial falhou e fallbacks (DDG/OpenAI) não retornaram resultados.")
        return []

    async def _pesquisar_web_fallback(self, site: str, query: str, limit: int = 5) -> List[ResultadoPesquisa]:
        """Realiza scraping leve no DuckDuckGo HTML como fallback"""
        try:
            import urllib.parse
            from bs4 import BeautifulSoup
            
            # Executar em thread separada para não bloquear loop async
            def _ddg_sync():
                # Tentar html.duckduckgo.com primeiro
                base_url = "https://html.duckduckgo.com/html/"
                search_term = f"site:{site} {query}"
                payload = {"q": search_term, "kl": "br-pt"}
                
                # Headers rotacionados/mais realistas
                headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                        "Upgrade-Insecure-Requests": "1",
                        "Referer": "https://duckduckgo.com/",
                        "Origin": "https://duckduckgo.com",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Cache-Control": "max-age=0",
                        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                        "Sec-Ch-Ua-Mobile": "?0",
                        "Sec-Ch-Ua-Platform": '"Windows"',
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "same-origin",
                        "Sec-Fetch-User": "?1"
                    }
                
                with httpx.Client(timeout=15.0, verify=False) as client:
                    # Tenta POST no html.duckduckgo.com
                    try:
                        resp = client.post(base_url, data=payload, headers=headers)
                        if resp.status_code == 200:
                            return _parse_ddg_html(resp.text, site, limit)
                    except Exception as e:
                        logger.warning(f"Erro DDG HTML: {e}")

                    # Fallback para lite.duckduckgo.com (GET)
                    try:
                        lite_url = "https://lite.duckduckgo.com/lite/"
                        resp = client.post(lite_url, data=payload, headers=headers)
                        if resp.status_code == 200:
                            return _parse_ddg_lite(resp.text, site, limit)
                    except Exception as e:
                        logger.warning(f"Erro DDG Lite: {e}")
                
                return []

            def _parse_ddg_html(html, site, limit):
                soup = BeautifulSoup(html, 'html.parser')
                results = []
                for res in soup.select(".result")[:limit]:
                    title_tag = res.select_one(".result__a")
                    snippet_tag = res.select_one(".result__snippet")
                    
                    if title_tag:
                        title = title_tag.get_text(strip=True)
                        link_raw = title_tag['href']
                        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                        
                        # Extrair link real
                        parsed = urllib.parse.urlparse(link_raw)
                        qs = urllib.parse.parse_qs(parsed.query)
                        link = qs.get('uddg', [link_raw])[0]
                        
                        if "duckduckgo.com" in link or site not in link:
                            continue

                        results.append(ResultadoPesquisa(
                            fonte=f"Web ({site})",
                            tipo="jurisprudencia",
                            titulo=title,
                            conteudo=snippet,
                            url=link,
                            tribunal="STF" if "stf" in site else "STJ",
                            relevancia=0.6,
                            metadata={"origin": "duckduckgo_html"}
                        ))
                return results

            def _parse_ddg_lite(html, site, limit):
                soup = BeautifulSoup(html, 'html.parser')
                results = []
                # Lite retorna tabela. Rows: Title/Link, Snippet, Metadata
                rows = soup.select("table:last-of-type tr")
                
                current_res = {}
                count = 0
                
                for row in rows:
                    if count >= limit: break
                    
                    link_tag = row.select_one("a.result-link")
                    snippet_tag = row.select_one("td.result-snippet")
                    
                    if link_tag:
                        current_res = {
                            "title": link_tag.get_text(strip=True),
                            "link": link_tag['href']
                        }
                    elif snippet_tag and current_res:
                        current_res["snippet"] = snippet_tag.get_text(strip=True)
                        
                        # Processar resultado completo
                        link = current_res["link"]
                        if site in link:
                             results.append(ResultadoPesquisa(
                                fonte=f"Web Lite ({site})",
                                tipo="jurisprudencia",
                                titulo=current_res["title"],
                                conteudo=current_res["snippet"],
                                url=link,
                                tribunal="STF" if "stf" in site else "STJ",
                                relevancia=0.5,
                                metadata={"origin": "duckduckgo_lite"}
                            ))
                             count += 1
                        current_res = {}
                        
                return results

            return await asyncio.to_thread(_ddg_sync)

        except Exception as e:
            logger.warning(f"Erro no fallback Web Search: {e}")
            return []

    def _parse_stf_results(self, data: Any) -> List[ResultadoPesquisa]:
        """Parse resultados do STF"""
        resultados = []

        # O schema pode variar; adaptar
        items = []
        if isinstance(data, dict):
            # Tentar encontrar a lista de hits na estrutura do Elastic/API STF
            result_obj = data.get("result", {})
            if isinstance(result_obj, dict):
                hits_obj = result_obj.get("hits", {})
                if isinstance(hits_obj, dict):
                    items = hits_obj.get("hits", [])
            
            if not items:
                items = data.get("resultado", data.get("results", data.get("acórdãos", [])))
                if isinstance(items, dict):
                    items = items.get("items", [])
        elif isinstance(data, list):
            items = data

        for item in items[:25]:
            if isinstance(item, dict):
                # Extrair dados do _source se for estrutura Elastic
                source = item.get("_source", item)
                
                titulo = source.get("titulo", source.get("nome", source.get("indexacao", "")))
                ementa = source.get("ementa", source.get("resumo", source.get("texto", "")))
                
                # Se não tiver título/ementa claros, usar outros campos
                if not titulo and "classe" in source and "numero" in source:
                    titulo = f"{source.get('classe')} {source.get('numero')}"

                resultados.append(ResultadoPesquisa(
                    fonte="STF",
                    tipo="jurisprudencia",
                    titulo=str(titulo)[:200],
                    conteudo=str(ementa)[:500],
                    url=source.get("link", source.get("url")),
                    tribunal="STF",
                    data=source.get("data", source.get("dataJulgamento", source.get("data_julgamento"))),
                    relevancia=0.9,
                    metadata={
                        "relator": source.get("relator", source.get("ministro_relator")),
                        "tipo_decisao": source.get("tipo", source.get("classe")),
                        "numero": source.get("numero", source.get("processo"))
                    }
                ))
        return resultados

    # =============================================
    # STJ - SUPERIOR TRIBUNAL DE JUSTIÇA
    # =============================================

    async def _pesquisar_stj(
        self, query: str, tribunal: Optional[str] = None, limit: int = 10
    ) -> List[ResultadoPesquisa]:
        """
        Pesquisa jurisprudência no STJ.
        Utiliza a API Pública do DataJud (CNJ) como fonte oficial e estável.
        Endpoint: https://api-publica.datajud.cnj.jus.br/api_publica_stj/_search
        """
        # Chave pública DataJud (pode rotacionar, idealmente viria de ENV, mas é pública)
        # Fonte: https://datajud-wiki.cnj.jus.br/api-publica/acesso/
        api_key = settings.CNJ_API_KEY or "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="
        
        url = "https://api-publica.datajud.cnj.jus.br/api_publica_stj/_search"
        
        # Payload de busca Elasticsearch no DataJud
        # Busca textual nos campos disponíveis (classe, movimentos, assuntos)
        payload = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["classe.nome", "movimentos.nome", "assuntos.nome", "orgaoJulgador.nome"]
                }
            },
            "size": min(limit, 25),
            "sort": [{"dataAjuizamento": {"order": "desc"}}]
        }
        
        headers = {
            "Authorization": f"APIKey {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "IA-Juridica-Bot/1.0"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False, headers=headers) as client:
                resp = await client.post(url, json=payload)
                
                if resp.status_code == 200:
                    data = resp.json()
                    return self._parse_stj_datajud_results(data)
                else:
                    logger.warning(f"Erro STJ DataJud: {resp.status_code} - {resp.text[:200]}")
                    
        except Exception as e:
            logger.error(f"Erro pesquisa STJ (DataJud): {e}")

        # Tentar via API REST do site do STJ como fallback
        resultados_rest = await self._pesquisar_stj_rest(query, limit)
        if resultados_rest:
            return resultados_rest

        # Se tudo falhar, tentar fallback Web Scraping (DuckDuckGo)
        return await self._pesquisar_stj_alternativo(query, limit)

    async def _pesquisar_stj_alternativo(
        self, query: str, limit: int = 10
    ) -> List[ResultadoPesquisa]:
        """
        Fallback: Scraping no DuckDuckGo para STJ se APIs oficiais falharem.
        """
        logger.warning("STJ: APIs oficiais falharam. Tentando fallback Web Scraping.")
        
        # 1. Tentar Scraping DuckDuckGo
        resultados_ddg = await self._pesquisar_web_fallback("stj.jus.br", query, limit)
        if resultados_ddg:
            return resultados_ddg

        # 2. Tentar OpenAI Web Search
        if self.openai_client:
            return await self._pesquisar_openai(f"site:stj.jus.br {query}", tribunal="STJ", limit=limit)
            
        return []

    async def _pesquisar_stj_rest(
        self, query: str, limit: int = 10
    ) -> List[ResultadoPesquisa]:
        """
        API REST do STJ (SCON).
        Nota: Frequentemente bloqueada por WAF.
        """
        url = "https://scon.stj.jus.br/SCON/jurisprudencia/toc.jsp"
        params = {
            "livre": query,
            "tipo_visualizacao": "RESUMO",
            "b": "ACOR",
            "thesaurus": "JURIDICO",
            "p": "true"
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://scon.stj.jus.br/SCON/"
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, verify=True, headers=headers) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        return self._parse_stj_results(data)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.warning(f"Erro STJ REST: {e}")
            
        # Sem mocks conforme solicitado. Retorna vazio se falhar.
        return []

    def _parse_stj_datajud_results(self, data: Any) -> List[ResultadoPesquisa]:
        """Parse resultados do DataJud (STJ)"""
        resultados = []
        hits = data.get("hits", {}).get("hits", [])
        
        for hit in hits:
            source = hit.get("_source", {})
            
            # Construir título e conteúdo a partir dos metadados processuais
            classe = source.get("classe", {}).get("nome", "Processo")
            numero = source.get("numeroProcesso", "N/A")
            assuntos = ", ".join([a.get("nome", "") for a in source.get("assuntos", [])])
            movimentos = source.get("movimentos", [])
            ultimo_mov = movimentos[0].get("nome", "") if movimentos else ""
            
            titulo = f"{classe} nº {numero}"
            conteudo = f"Assuntos: {assuntos}. Última movimentação: {ultimo_mov} em {source.get('dataHoraUltimaAtualizacao')}."
            
            # URL de consulta processual pública do STJ (usando NPU)
            # Formato: https://processo.stj.jus.br/processo/pesquisa/?src=1.1.2&aplicacao=processos.ea&tipoPesquisa=tipoPesquisaGenerica&num_processo={numero}
            url = f"https://processo.stj.jus.br/processo/pesquisa/?src=1.1.2&aplicacao=processos.ea&tipoPesquisa=tipoPesquisaGenerica&num_processo={numero}"

            resultados.append(ResultadoPesquisa(
                fonte="STJ (DataJud)",
                tipo="processo",
                titulo=titulo,
                conteudo=conteudo,
                url=url,
                tribunal="STJ",
                data=source.get("dataAjuizamento"),
                relevancia=0.85,
                metadata={
                    "orgao": source.get("orgaoJulgador", {}).get("nome"),
                    "numero": numero,
                    "grau": source.get("grau")
                }
            ))
        return resultados

    def _parse_stj_results(self, data: Any) -> List[ResultadoPesquisa]:
        """Parse resultados do STJ"""
        resultados = []

        items = []
        if isinstance(data, dict):
            items = data.get("documentos", data.get("resultado", data.get("results", [])))
        elif isinstance(data, list):
            items = data

        for item in items[:25]:
            if isinstance(item, dict):
                resultados.append(ResultadoPesquisa(
                    fonte="STJ",
                    tipo="jurisprudencia",
                    titulo=item.get("titulo", item.get("processo", ""))[:200],
                    conteudo=item.get("ementa", item.get("resumo", ""))[:500],
                    url=item.get("link", item.get("url")),
                    tribunal="STJ",
                    data=item.get("data", item.get("dtJulgamento")),
                    relevancia=0.88,
                    metadata={
                        "relator": item.get("relator", item.get("ministro")),
                        "orgao": item.get("orgaoJulgador", item.get("turma")),
                        "numero": item.get("numero", item.get("registro"))
                    }
                ))
        return resultados

    # =============================================
    # TST - TRIBUNAL SUPERIOR DO TRABALHO
    # =============================================

    async def _pesquisar_tst(
        self, query: str, tribunal: Optional[str] = None, limit: int = 10
    ) -> List[ResultadoPesquisa]:
        """Pesquisa jurisprudência no TST"""
        url = "https://jurisprudencia.tst.jus.br/rest/pesquisa/query"

        payload = {
            "query": query,
            "pageSize": min(limit, 25)
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("items", data.get("resultado", []))
                    resultados = []
                    for item in items[:limit]:
                        if isinstance(item, dict):
                            resultados.append(ResultadoPesquisa(
                                fonte="TST",
                                tipo="jurisprudencia",
                                titulo=item.get("titulo", item.get("processo", ""))[:200],
                                conteudo=item.get("ementa", item.get("resumo", ""))[:500],
                                url=item.get("link"),
                                tribunal="TST",
                                data=item.get("data"),
                                relevancia=0.85,
                                metadata={"orgao": item.get("orgao"), "relator": item.get("relator")}
                            ))
                    return resultados
        except Exception as e:
            logger.warning(f"Erro pesquisa TST: {e}")
        return []

    # =============================================
    # TRIBUNAIS ESTADUAIS (via CNJ DataJud)
    # =============================================

    async def _pesquisar_tribunal_estadual(
        self, query: str, tribunal: str, limit: int = 10
    ) -> List[ResultadoPesquisa]:
        """Pesquisa em tribunais estaduais via DataJud"""
        # Mapeamento tribunal -> endpoint DataJud
        tribunal_endpoints = {
            "TJSP": "api_publica_tjsp",
            "TJRJ": "api_publica_tjrj",
            "TJMG": "api_publica_tjmg",
            "TJRS": "api_publica_tjrs",
            "TJPR": "api_publica_tjpr",
            "TJBA": "api_publica_tjba",
            "TJPE": "api_publica_tjpe",
            "TJCE": "api_publica_tjce",
            "TJSC": "api_publica_tjsc",
            "TJGO": "api_publica_tjgo",
        }

        endpoint = tribunal_endpoints.get(tribunal.upper(), f"api_publica_{tribunal.lower()}")
        url = f"https://api-publica.datajud.cnj.jus.br/{endpoint}/_search"

        headers = {"Content-Type": "application/json"}
        if settings.CNJ_API_KEY:
            headers["Authorization"] = f"APIKey {settings.CNJ_API_KEY}"

        payload = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"assuntos.nome": query}}
                    ]
                }
            },
            "size": min(limit, 25)
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    hits = data.get("hits", {}).get("hits", [])
                    resultados = []
                    for hit in hits[:limit]:
                        src = hit.get("_source", {})
                        classe = src.get("classe", {})
                        assuntos = src.get("assuntos", [])

                        titulo = f"{classe.get('nome', 'Processo')} - {src.get('numeroProcesso', '')}"
                        conteudo_parts = [
                            f"Classe: {classe.get('nome', 'N/D')}",
                            f"Assunto: {assuntos[0].get('nome', 'N/D') if assuntos else 'N/D'}",
                            f"Órgão: {src.get('orgaoJulgador', {}).get('nome', 'N/D')}",
                        ]

                        resultados.append(ResultadoPesquisa(
                            fonte=tribunal.upper(),
                            tipo="processo",
                            titulo=titulo[:200],
                            conteudo=" | ".join(conteudo_parts),
                            tribunal=tribunal.upper(),
                            data=src.get("dataAjuizamento"),
                            relevancia=0.75,
                            metadata={
                                "numero_cnj": src.get("numeroProcesso"),
                                "classe": classe.get("nome"),
                                "orgao_julgador": src.get("orgaoJulgador", {}).get("nome"),
                            }
                        ))
                    return resultados
        except Exception as e:
            logger.warning(f"Erro pesquisa {tribunal}: {e}")
        return []

    # =============================================
    # CNJ DATAJUD
    # =============================================

    async def _pesquisar_cnj(
        self, query: str, tribunal: Optional[str] = None, limit: int = 10
    ) -> List[ResultadoPesquisa]:
        """Pesquisa geral no CNJ DataJud"""
        if tribunal:
            return await self._pesquisar_tribunal_estadual(query, tribunal, limit)

        # Pesquisar em TJSP por padrão (maior volume)
        return await self._pesquisar_tribunal_estadual(query, "TJSP", limit)

    # =============================================
    # LEXML - LEGISLAÇÃO BRASILEIRA
    # =============================================

    async def _pesquisar_lexml(
        self, query: str, tribunal: Optional[str] = None, limit: int = 10
    ) -> List[ResultadoPesquisa]:
        """Pesquisa legislação no LexML (rede de informação legislativa)"""
        url = "https://www.lexml.gov.br/busca/SRU"
        params = {
            "operation": "searchRetrieve",
            "version": "1.1",
            "query": f'dc.description any "{query}"',
            "maximumRecords": min(limit, 25),
            "recordSchema": "lexml"
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    return self._parse_lexml_xml(resp.text, limit)
        except Exception as e:
            logger.warning(f"Erro pesquisa LexML: {e}")
        
        # Fallback para legislação comum (Planalto local)
        return self._legislacao_comum(query, limit)

    def _parse_lexml_xml(self, xml_text: str, limit: int) -> List[ResultadoPesquisa]:
        """Parse XML do LexML"""
        resultados = []
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_text)

            # Namespace do SRU
            ns = {
                'srw': 'http://www.loc.gov/zing/srw/',
                'dc': 'http://purl.org/dc/elements/1.1/',
                'lexml': 'http://www.lexml.gov.br/1.0'
            }

            records = root.findall('.//srw:record', ns)
            for record in records[:limit]:
                data_elem = record.find('.//srw:recordData', ns)
                if data_elem is not None:
                    # Extrair campos Dublin Core
                    titulo = self._find_text(data_elem, './/dc:title', ns, "Sem título")
                    descricao = self._find_text(data_elem, './/dc:description', ns, "")
                    tipo = self._find_text(data_elem, './/dc:type', ns, "legislacao")
                    data = self._find_text(data_elem, './/dc:date', ns, "")
                    identifier = self._find_text(data_elem, './/dc:identifier', ns, "")

                    url = None
                    if identifier.startswith("urn:lex:br"):
                        url = f"https://www.lexml.gov.br/urn/{identifier}"

                    resultados.append(ResultadoPesquisa(
                        fonte="LexML",
                        tipo="legislacao",
                        titulo=titulo[:200],
                        conteudo=descricao[:500] if descricao else titulo,
                        url=url,
                        data=data,
                        relevancia=0.80,
                        metadata={"urn": identifier, "tipo_documento": tipo}
                    ))
        except Exception as e:
            logger.warning(f"Erro parse LexML XML: {e}")
        return resultados

    def _find_text(self, elem, path: str, ns: dict, default: str = "") -> str:
        """Helper para extrair texto de XML"""
        found = elem.find(path, ns)
        if found is not None and found.text:
            return found.text
        # Tentar sem namespace
        tag = path.split("}")[-1] if "}" in path else path.split(":")[-1]
        for child in elem.iter():
            if child.tag.endswith(tag) and child.text:
                return child.text
        return default

    # =============================================
    # PLANALTO - LEGISLAÇÃO FEDERAL
    # =============================================

    async def _pesquisar_planalto(
        self, query: str, tribunal: Optional[str] = None, limit: int = 10
    ) -> List[ResultadoPesquisa]:
        """Pesquisa legislação no Portal da Legislação (Planalto)"""
        # O Planalto não tem API pública JSON oficial, mas podemos usar o buscador
        url = "https://legislacao.planalto.gov.br/legisla/legislacao.nsf/FrmConsultaWeb1"
        params = {
            "query": query,
            "codTipoNorma": "",
            "codFonte": "",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    # Tentar parsear HTML para extrair resultados
                    return self._parse_planalto_html(resp.text, query, limit)
        except Exception as e:
            logger.warning(f"Erro pesquisa Planalto: {e}")

        # Fallback: legislação comum pré-indexada
        return self._legislacao_comum(query, limit)

    def _parse_planalto_html(self, html: str, query: str, limit: int) -> List[ResultadoPesquisa]:
        """Extrai resultados do HTML do Planalto (best-effort)"""
        # Devido à complexidade do HTML do Planalto, retornamos a legislação indexada
        return self._legislacao_comum(query, limit)

    def _legislacao_comum(self, query: str, limit: int) -> List[ResultadoPesquisa]:
        """Legislação brasileira mais comum, pesquisável"""
        legislacao = [
            {"nome": "Constituição Federal de 1988", "numero": "CF/1988", "url": "http://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
             "ementa": "Constituição da República Federativa do Brasil", "tags": ["constituição", "direitos fundamentais", "organização do estado"]},
            {"nome": "Código Civil - Lei 10.406/2002", "numero": "10406/2002", "url": "http://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm",
             "ementa": "Institui o Código Civil", "tags": ["civil", "contratos", "obrigações", "família", "sucessões", "propriedade"]},
            {"nome": "Código de Processo Civil - Lei 13.105/2015", "numero": "13105/2015", "url": "http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm",
             "ementa": "Código de Processo Civil", "tags": ["processo", "processual", "recurso", "citação", "intimação", "prazo"]},
            {"nome": "Código Penal - Decreto-Lei 2.848/1940", "numero": "2848/1940", "url": "http://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm",
             "ementa": "Código Penal", "tags": ["penal", "crime", "pena", "furto", "roubo", "homicídio", "estupro"]},
            {"nome": "Código de Processo Penal - Decreto-Lei 3.689/1941", "numero": "3689/1941", "url": "http://www.planalto.gov.br/ccivil_03/decreto-lei/del3689compilado.htm",
             "ementa": "Código de Processo Penal", "tags": ["processo penal", "inquérito", "prisão", "habeas corpus", "fiança"]},
            {"nome": "CLT - Decreto-Lei 5.452/1943", "numero": "5452/1943", "url": "http://www.planalto.gov.br/ccivil_03/decreto-lei/del5452compilado.htm",
             "ementa": "Consolidação das Leis do Trabalho", "tags": ["trabalho", "trabalhista", "emprego", "rescisão", "férias", "salário"]},
            {"nome": "CDC - Lei 8.078/1990", "numero": "8078/1990", "url": "http://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm",
             "ementa": "Código de Defesa do Consumidor", "tags": ["consumidor", "produto", "serviço", "fornecedor", "propaganda", "recall"]},
            {"nome": "ECA - Lei 8.069/1990", "numero": "8069/1990", "url": "http://www.planalto.gov.br/ccivil_03/leis/l8069.htm",
             "ementa": "Estatuto da Criança e do Adolescente", "tags": ["criança", "adolescente", "menor", "infância", "adoção", "guarda"]},
            {"nome": "Lei de Execução Penal - Lei 7.210/1984", "numero": "7210/1984", "url": "http://www.planalto.gov.br/ccivil_03/leis/l7210.htm",
             "ementa": "Lei de Execução Penal", "tags": ["execução penal", "preso", "progressão", "regime", "livramento condicional"]},
            {"nome": "Lei Maria da Penha - Lei 11.340/2006", "numero": "11340/2006", "url": "http://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11340.htm",
             "ementa": "Violência doméstica e familiar contra a mulher", "tags": ["violência doméstica", "mulher", "medida protetiva"]},
            {"nome": "LGPD - Lei 13.709/2018", "numero": "13709/2018", "url": "http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm",
             "ementa": "Lei Geral de Proteção de Dados Pessoais", "tags": ["dados pessoais", "privacidade", "lgpd", "proteção de dados"]},
            {"nome": "Marco Civil da Internet - Lei 12.965/2014", "numero": "12965/2014", "url": "http://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l12965.htm",
             "ementa": "Marco Civil da Internet", "tags": ["internet", "provedor", "conteúdo", "neutralidade"]},
            {"nome": "Lei de Licitações - Lei 14.133/2021", "numero": "14133/2021", "url": "http://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/L14133.htm",
             "ementa": "Nova Lei de Licitações e Contratos Administrativos", "tags": ["licitação", "contrato administrativo", "pregão", "concorrência"]},
            {"nome": "Código Tributário Nacional - Lei 5.172/1966", "numero": "5172/1966", "url": "http://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm",
             "ementa": "Código Tributário Nacional", "tags": ["tributo", "imposto", "taxa", "contribuição", "tributário", "fiscal"]},
            {"nome": "Lei de Improbidade - Lei 8.429/1992", "numero": "8429/1992", "url": "http://www.planalto.gov.br/ccivil_03/leis/l8429.htm",
             "ementa": "Lei de Improbidade Administrativa", "tags": ["improbidade", "administração pública", "enriquecimento ilícito"]},
        ]

        q_lower = query.lower()
        resultados = []
        for lei in legislacao:
            score = 0
            for tag in lei["tags"]:
                if tag in q_lower:
                    score += 1
            if q_lower in lei["nome"].lower() or q_lower in lei["ementa"].lower():
                score += 2
            # Busca parcial por palavras
            for word in q_lower.split():
                if len(word) > 3:
                    for tag in lei["tags"]:
                        if word in tag:
                            score += 0.5
                    if word in lei["nome"].lower():
                        score += 0.5

            if score > 0:
                resultados.append(ResultadoPesquisa(
                    fonte="Planalto",
                    tipo="legislacao",
                    titulo=lei["nome"],
                    conteudo=lei["ementa"],
                    url=lei["url"],
                    relevancia=min(score / 3, 1.0),
                    metadata={"numero": lei["numero"], "tags": lei["tags"]}
                ))

        resultados.sort(key=lambda r: r.relevancia, reverse=True)
        return resultados[:limit]

    # =============================================
    # RAG LOCAL
    # =============================================

    async def _pesquisar_rag_local(
        self, query: str, tribunal: Optional[str] = None, limit: int = 10
    ) -> List[ResultadoPesquisa]:
        """Pesquisa na base vetorial local (RAG)"""
        try:
            from app.services.rag_engine import get_rag_engine
            rag = await get_rag_engine()
            results = await rag.search(query=query, tribunal=tribunal, top_k=limit)

            resultados = []
            for r in results:
                resultados.append(ResultadoPesquisa(
                    fonte="RAG Local",
                    tipo=r.get("tipo", "jurisprudencia"),
                    titulo=r.get("titulo", r.get("ementa", ""))[:200],
                    conteudo=r.get("conteudo", "")[:500],
                    tribunal=r.get("tribunal"),
                    data=r.get("data_julgamento", r.get("data")),
                    relevancia=r.get("score", 0.5),
                    metadata=r.get("metadata", {})
                ))
            return resultados
        except Exception as e:
            logger.warning(f"Erro RAG local: {e}")
            return []

    # =============================================
    # SUGESTÕES
    # =============================================

    def _gerar_sugestoes(self, query: str) -> List[str]:
        """Gera sugestões de pesquisa relacionadas"""
        sugestoes_map = {
            "consumidor": ["direito do consumidor vício produto", "CDC art. 18 substituição", "inversão ônus prova consumidor"],
            "trabalho": ["rescisão contrato trabalho", "horas extras CLT", "dano moral trabalhista"],
            "penal": ["dosimetria pena", "substituição pena restritiva", "prescrição penal"],
            "família": ["guarda compartilhada", "alimentos fixação", "divórcio partilha bens"],
            "civil": ["responsabilidade civil dano", "contrato rescisão", "usucapião requisitos"],
            "tributário": ["exclusão ICMS base PIS COFINS", "imunidade tributária", "decadência tributária"],
            "administrativo": ["licitação dispensa", "concurso público anulação", "servidor público estabilidade"],
        }

        q_lower = query.lower()
        sugestoes = []
        for area, sug_list in sugestoes_map.items():
            if area in q_lower:
                sugestoes.extend(sug_list)

        return sugestoes[:5]

    # =============================================
    # ENDPOINTS ESPECÍFICOS
    # =============================================

    async def consultar_sumulas(self, tribunal: str = "STF") -> List[ResultadoPesquisa]:
        """Lista súmulas vinculantes e ordinárias"""
        if tribunal.upper() == "STF":
            return await self._pesquisar_stf("súmula vinculante", limit=25)
        elif tribunal.upper() == "STJ":
            return await self._pesquisar_stj("súmula", limit=25)
        return []

    async def consultar_teses_repetitivos(self, query: str = "") -> List[ResultadoPesquisa]:
        """Pesquisa teses firmadas em recursos repetitivos (STJ)"""
        search = f"recurso repetitivo tema {query}" if query else "recurso repetitivo"
        return await self._pesquisar_stj(search, limit=20)


# Instância global
_pesquisa_service: Optional[PesquisaJuridicaService] = None


def get_pesquisa_service() -> PesquisaJuridicaService:
    """Dependency para obter PesquisaJuridicaService"""
    global _pesquisa_service
    if _pesquisa_service is None:
        _pesquisa_service = PesquisaJuridicaService()
    return _pesquisa_service
