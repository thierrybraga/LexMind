"""
Service CNJ - Integração Real com DataJud API Pública
https://datajud-wiki.cnj.jus.br/api-publica/

A API do DataJud usa Elasticsearch e expõe um índice por tribunal.
Endpoint: POST https://api-publica.datajud.cnj.jus.br/api_publica_{tribunal}/_search
Auth: Header "Authorization: APIKey <chave>"
"""

import httpx
import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from app.core.config import settings


def _retry_datajud(exc: BaseException) -> bool:
    """Decide se a exceção deve gerar nova tentativa na API DataJud."""
    if isinstance(exc, (httpx.RequestError, httpx.ConnectTimeout)):
        return True
    # Retry em 429 (rate limit) e erros 5xx (servidor)
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False

logger = logging.getLogger(__name__)

# Chave pública padrão do DataJud — usada apenas se CNJ_API_KEY não estiver no .env.
# Fonte: https://datajud-wiki.cnj.jus.br/api-publica/acesso
# Pode ser rotacionada pelo CNJ; prefira sempre configurar CNJ_API_KEY no .env.
DATAJUD_PUBLIC_KEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRnliTE9xRnVJWDlYZw=="

# ============================================================
# Mapeamento de código de tribunal (posições 14-15 do nº CNJ)
# para o alias do índice na API DataJud
# ============================================================
# Formato CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO
#   J  = segmento de justiça (posição 13)
#   TR = tribunal (posições 14-15)

SEGMENTO_TRIBUNAL_MAP: Dict[str, Dict[str, str]] = {
    # 1 = STF
    "1": {"00": "stf"},
    # 2 = CNJ (sem índice público)
    # 3 = STJ
    "3": {"00": "stj"},
    # 4 = Justiça Federal (TRFs)
    "4": {
        "01": "trf1", "02": "trf2", "03": "trf3",
        "04": "trf4", "05": "trf5", "06": "trf6",
    },
    # 5 = Justiça do Trabalho
    "5": {
        "00": "tst",
        **{f"{i:02d}": f"trt{i}" for i in range(1, 25)},
    },
    # 6 = Justiça Eleitoral
    "6": {
        "00": "tse",
    },
    # 7 = Justiça Militar da União
    "7": {"00": "stm"},
    # 8 = Justiça Estadual (TJs)
    "8": {
        "01": "tjac", "02": "tjal", "03": "tjap", "04": "tjam",
        "05": "tjba", "06": "tjce", "07": "tjdft", "08": "tjes",
        "09": "tjgo", "10": "tjma", "11": "tjmt", "12": "tjms",
        "13": "tjmg", "14": "tjpa", "15": "tjpb", "16": "tjpr",
        "17": "tjpe", "18": "tjpi", "19": "tjrj", "20": "tjrn",
        "21": "tjrs", "22": "tjro", "23": "tjrr", "24": "tjsc",
        "25": "tjse", "26": "tjsp", "27": "tjto",
    },
    # 9 = Justiça Militar Estadual
    "9": {
        "13": "tjmmg", "21": "tjmrs", "26": "tjmsp",
    },
}

# Mapeamento de alias → TRE (Justiça Eleitoral estadual usa padrão diferente)
TRE_MAP: Dict[str, str] = {
    "01": "tre-ac", "02": "tre-al", "03": "tre-ap", "04": "tre-am",
    "05": "tre-ba", "06": "tre-ce", "07": "tre-df", "08": "tre-es",
    "09": "tre-go", "10": "tre-ma", "11": "tre-mt", "12": "tre-ms",
    "13": "tre-mg", "14": "tre-pa", "15": "tre-pb", "16": "tre-pr",
    "17": "tre-pe", "18": "tre-pi", "19": "tre-rj", "20": "tre-rn",
    "21": "tre-rs", "22": "tre-ro", "23": "tre-rr", "24": "tre-sc",
    "25": "tre-se", "26": "tre-sp", "27": "tre-to",
}

# Nomes legíveis dos tribunais
TRIBUNAL_NOMES: Dict[str, str] = {
    "stf": "Supremo Tribunal Federal",
    "stj": "Superior Tribunal de Justiça",
    "tst": "Tribunal Superior do Trabalho",
    "tse": "Tribunal Superior Eleitoral",
    "stm": "Superior Tribunal Militar",
    "trf1": "TRF 1ª Região", "trf2": "TRF 2ª Região", "trf3": "TRF 3ª Região",
    "trf4": "TRF 4ª Região", "trf5": "TRF 5ª Região", "trf6": "TRF 6ª Região",
    "tjsp": "TJSP", "tjrj": "TJRJ", "tjmg": "TJMG", "tjrs": "TJRS",
    "tjpr": "TJPR", "tjba": "TJBA", "tjdft": "TJDFT", "tjsc": "TJSC",
    "tjpe": "TJPE", "tjce": "TJCE", "tjgo": "TJGO", "tjes": "TJES",
    "tjpa": "TJPA", "tjma": "TJMA", "tjpb": "TJPB", "tjrn": "TJRN",
    "tjpi": "TJPI", "tjse": "TJSE", "tjal": "TJAL", "tjac": "TJAC",
    "tjam": "TJAM", "tjap": "TJAP", "tjmt": "TJMT", "tjms": "TJMS",
    "tjro": "TJRO", "tjrr": "TJRR", "tjto": "TJTO",
}


class CNJService:
    """
    Serviço de integração real com a API Pública do CNJ DataJud.

    Cada tribunal possui seu próprio índice Elasticsearch na API.
    O número CNJ contém o código do tribunal, permitindo auto-detecção.
    """

    def __init__(self):
        self.base_url = settings.CNJ_API_URL or "https://api-publica.datajud.cnj.jus.br"
        self.api_key = settings.CNJ_API_KEY or DATAJUD_PUBLIC_KEY
        self.timeout = settings.CNJ_TIMEOUT or 30

    def _get_headers(self, api_key: Optional[str] = None) -> Dict[str, str]:
        key = api_key or self.api_key
        return {
            "Authorization": f"APIKey {key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Parsing do número CNJ
    # ------------------------------------------------------------------

    @staticmethod
    def parse_numero_cnj(numero: str) -> Dict[str, str]:
        """
        Parse do número CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO

        Retorna dict com sequencial, digito, ano, segmento, tribunal_codigo, origem.
        """
        limpo = re.sub(r"[^0-9]", "", numero)
        if len(limpo) != 20:
            return {}

        return {
            "sequencial": limpo[:7],
            "digito": limpo[7:9],
            "ano": limpo[9:13],
            "segmento": limpo[13],
            "tribunal_codigo": limpo[14:16],
            "origem": limpo[16:20],
            "numero_limpo": limpo,
        }

    def _resolver_indice(self, numero: str) -> Optional[str]:
        """
        Detecta o alias do índice DataJud a partir do número CNJ.
        Retorna ex: 'api_publica_tjsp'
        """
        partes = self.parse_numero_cnj(numero)
        if not partes:
            return None

        seg = partes["segmento"]
        tr = partes["tribunal_codigo"]

        # Justiça Eleitoral estadual (seg 6, TR != 00)
        if seg == "6" and tr != "00":
            alias = TRE_MAP.get(tr)
            if alias:
                return f"api_publica_{alias}"

        mapa_seg = SEGMENTO_TRIBUNAL_MAP.get(seg, {})
        alias = mapa_seg.get(tr)
        if alias:
            return f"api_publica_{alias}"

        # Fallback: tentar tjXX para estadual
        if seg == "8":
            return f"api_publica_tj{tr}"

        logger.warning(f"Não foi possível resolver índice para: {numero} (seg={seg}, tr={tr})")
        return None

    def _resolver_tribunal_nome(self, numero: str) -> str:
        """Retorna o nome legível do tribunal a partir do número CNJ."""
        indice = self._resolver_indice(numero)
        if indice:
            alias = indice.replace("api_publica_", "")
            return TRIBUNAL_NOMES.get(alias, alias.upper())
        return "Desconhecido"

    def _formatar_numero_cnj(self, numero_limpo: str) -> str:
        """Formata número limpo (20 dígitos) no padrão NNNNNNN-DD.AAAA.J.TR.OOOO"""
        if len(numero_limpo) != 20:
            return numero_limpo
        return (
            f"{numero_limpo[:7]}-{numero_limpo[7:9]}."
            f"{numero_limpo[9:13]}.{numero_limpo[13]}."
            f"{numero_limpo[14:16]}.{numero_limpo[16:20]}"
        )

    # ------------------------------------------------------------------
    # Consulta principal
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(_retry_datajud),
        reraise=True,
    )
    async def consultar_processo(
        self,
        numero_processo: str,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Consulta processo na API real do DataJud.

        Auto-detecta o tribunal pelo número CNJ e consulta o índice correto.
        """
        numero_limpo = re.sub(r"[^0-9]", "", numero_processo)
        indice = self._resolver_indice(numero_processo)

        if not indice:
            raise ValueError(
                f"Não foi possível determinar o tribunal para o número: {numero_processo}"
            )

        url = f"{self.base_url}/{indice}/_search"
        headers = self._get_headers(api_key)

        payload = {
            "query": {
                "match": {
                    "numeroProcesso": numero_limpo,
                }
            },
            "size": 1,
        }

        logger.info(f"Consultando DataJud: {url} | processo: {numero_processo}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        total = data.get("hits", {}).get("total", {})
        total_value = total.get("value", 0) if isinstance(total, dict) else total

        if total_value > 0:
            source = data["hits"]["hits"][0]["_source"]
            return self._normalizar_dados(source, numero_processo)

        logger.warning(f"Processo não encontrado no DataJud ({indice}): {numero_processo}")
        raise ValueError(f"Processo {numero_processo} não encontrado no tribunal {indice.replace('api_publica_', '').upper()}")

    async def consultar_processo_multi_tribunal(
        self,
        numero_processo: str,
        tribunais: Optional[List[str]] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Tenta consultar o processo em múltiplos tribunais caso não saiba o exato.
        Primeiro tenta o tribunal detectado automaticamente pelo número CNJ.
        Se tribunais for fornecido, tenta cada um deles em sequência.
        """
        # Primeiro tenta o tribunal detectado automaticamente
        try:
            return await self.consultar_processo(numero_processo, api_key)
        except ValueError as e:
            logger.info(f"Tribunal auto-detectado não encontrou o processo: {e}")
        except httpx.HTTPStatusError as e:
            # Só continua se for 404 (não encontrado); propaga erros de autenticação/servidor
            if e.response.status_code != 404:
                logger.error(f"Erro HTTP {e.response.status_code} na consulta CNJ: {e}")
                raise
            logger.info(f"Processo não encontrado no tribunal auto-detectado (404): {numero_processo}")

        if not tribunais:
            raise ValueError(f"Processo {numero_processo} não encontrado no tribunal detectado")

        # Tentar nos tribunais especificados
        numero_limpo = re.sub(r"[^0-9]", "", numero_processo)
        headers = self._get_headers(api_key)

        for tribunal_alias in tribunais:
            alias = tribunal_alias.lower().replace("-", "")
            url = f"{self.base_url}/api_publica_{alias}/_search"
            payload = {
                "query": {"match": {"numeroProcesso": numero_limpo}},
                "size": 1,
            }

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                total = data.get("hits", {}).get("total", {})
                total_value = total.get("value", 0) if isinstance(total, dict) else total
                if total_value > 0:
                    source = data["hits"]["hits"][0]["_source"]
                    logger.info(f"Processo encontrado no tribunal {alias}: {numero_processo}")
                    return self._normalizar_dados(source, numero_processo)

                logger.debug(f"Processo não encontrado em {alias}")
            except httpx.HTTPStatusError as e:
                logger.warning(f"Tribunal {alias}: HTTP {e.response.status_code}")
            except httpx.RequestError as e:
                logger.warning(f"Tribunal {alias}: erro de conexão — {e}")

        raise ValueError(f"Processo {numero_processo} não encontrado nos tribunais consultados: {tribunais}")

    # ------------------------------------------------------------------
    # Busca por critérios (classe, assunto, órgão julgador, data)
    # ------------------------------------------------------------------

    async def buscar_processos(
        self,
        tribunal: str,
        classe_codigo: Optional[int] = None,
        assunto_codigo: Optional[int] = None,
        orgao_julgador_codigo: Optional[int] = None,
        data_inicio: Optional[str] = None,
        data_fim: Optional[str] = None,
        grau: Optional[str] = None,
        texto_livre: Optional[str] = None,
        size: int = 10,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Busca processos por critérios no DataJud.
        """
        alias = tribunal.lower().replace("-", "")
        url = f"{self.base_url}/api_publica_{alias}/_search"
        headers = self._get_headers(api_key)

        must_clauses = []

        if classe_codigo:
            must_clauses.append({"match": {"classe.codigo": classe_codigo}})
        if assunto_codigo:
            must_clauses.append({"match": {"assuntos.codigo": assunto_codigo}})
        if orgao_julgador_codigo:
            must_clauses.append({"match": {"orgaoJulgador.codigo": orgao_julgador_codigo}})
        if grau:
            must_clauses.append({"match": {"grau": grau}})

        if data_inicio or data_fim:
            date_range = {}
            if data_inicio:
                date_range["gte"] = data_inicio
            if data_fim:
                date_range["lte"] = data_fim
            must_clauses.append({"range": {"dataAjuizamento": date_range}})

        if texto_livre:
            must_clauses.append({"multi_match": {
                "query": texto_livre,
                "fields": ["classe.nome", "assuntos.nome", "orgaoJulgador.nome", "movimentos.nome"],
            }})

        if not must_clauses:
            raise ValueError("Pelo menos um critério de busca deve ser informado")

        payload = {
            "query": {"bool": {"must": must_clauses}},
            "size": min(size, 100),
            "sort": [{"dataAjuizamento": {"order": "desc"}}],
        }

        logger.info(f"Buscando processos no DataJud: {tribunal} ({len(must_clauses)} critérios)")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        hits = data.get("hits", {}).get("hits", [])
        total = data.get("hits", {}).get("total", {})
        total_value = total.get("value", 0) if isinstance(total, dict) else total

        processos = [self._normalizar_dados(h["_source"], "") for h in hits]

        return {
            "total": total_value,
            "processos": processos,
            "tribunal": tribunal.upper(),
        }

    # ------------------------------------------------------------------
    # Busca de jurisprudência
    # ------------------------------------------------------------------

    async def buscar_jurisprudencia_cnj(
        self,
        query: str,
        tribunal: str = "stj",
        limit: int = 10,
        api_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Busca processos por texto no DataJud (movimentos, classe, assuntos).
        """
        alias = tribunal.lower()
        url = f"{self.base_url}/api_publica_{alias}/_search"
        headers = self._get_headers(api_key)

        payload = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "classe.nome",
                        "assuntos.nome",
                        "movimentos.nome",
                        "orgaoJulgador.nome",
                    ],
                }
            },
            "size": min(limit, 100),
            "sort": [{"dataAjuizamento": {"order": "desc"}}],
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            hits = data.get("hits", {}).get("hits", [])
            return [self._normalizar_dados(h["_source"], "") for h in hits]

        except Exception as e:
            logger.error(f"Erro na busca de jurisprudência DataJud ({tribunal}): {e}")
            return []

    # ------------------------------------------------------------------
    # Normalização de dados
    # ------------------------------------------------------------------

    def _normalizar_dados(self, source: Dict[str, Any], numero_original: str) -> Dict[str, Any]:
        """
        Normaliza os dados reais retornados pelo DataJud (_source)
        para o schema interno do sistema.
        """
        numero_raw = source.get("numeroProcesso", "")
        numero_formatado = self._formatar_numero_cnj(numero_raw) if len(numero_raw) == 20 else (numero_original or numero_raw)

        # Classe processual
        classe_obj = source.get("classe", {})
        classe_nome = classe_obj.get("nome", "Não informada") if isinstance(classe_obj, dict) else str(classe_obj)

        # Assuntos (pode ser lista de dicts ou strings)
        assuntos = source.get("assuntos", [])
        assunto_principal = "Não informado"
        if assuntos:
            primeiro = assuntos[0]
            assunto_principal = primeiro.get("nome", "Não informado") if isinstance(primeiro, dict) else str(primeiro)
        assuntos_lista = [a.get("nome", "") for a in assuntos if isinstance(a, dict)]

        # Órgão julgador
        orgao = source.get("orgaoJulgador", {})
        orgao_nome = orgao.get("nome", "Não informado") if isinstance(orgao, dict) else str(orgao)
        municipio_ibge = orgao.get("codigoMunicipioIBGE") if isinstance(orgao, dict) else None

        # Tribunal
        tribunal = source.get("tribunal", "")

        # Grau
        grau = source.get("grau", "")
        grau_map = {
            "G1": "1º Grau", "G2": "2º Grau",
            "JE": "Juizado Especial", "TR": "Turma Recursal",
            "SUP": "Tribunal Superior",
        }
        grau_descricao = grau_map.get(grau, grau)

        # Data de ajuizamento
        data_ajuizamento = source.get("dataAjuizamento")

        # Formato e sistema
        formato = source.get("formato", {})
        formato_nome = formato.get("nome", "") if isinstance(formato, dict) else ""
        sistema = source.get("sistema", {})
        sistema_nome = sistema.get("nome", "") if isinstance(sistema, dict) else ""

        # Movimentações - normalizar
        movimentos_raw = source.get("movimentos", [])
        movimentacoes = []
        for mov in movimentos_raw:
            if not isinstance(mov, dict):
                continue

            complementos = mov.get("complementosTabelados", [])
            complemento_texto = "; ".join(
                f"{c.get('nome', '')}: {c.get('descricao', '')}"
                for c in complementos
                if isinstance(c, dict)
            )

            movimentacoes.append({
                "codigo": mov.get("codigo"),
                "descricao": mov.get("nome", "Sem descrição"),
                "data": mov.get("dataHora"),
                "complemento": complemento_texto or None,
                "orgao_julgador": (
                    mov.get("orgaoJulgador", {}).get("nomeOrgao")
                    if isinstance(mov.get("orgaoJulgador"), dict) else None
                ),
            })

        # Ordenar movimentações por data (mais recente primeiro)
        movimentacoes.sort(
            key=lambda m: m.get("data") or "1900-01-01",
            reverse=True,
        )

        # Inferir status pela última movimentação
        status_processo = "Em andamento"
        if movimentacoes:
            ultima = movimentacoes[0].get("descricao", "").lower()
            if any(t in ultima for t in ["baixa", "arquiv", "transit"]):
                status_processo = "Arquivado"
            elif "sentença" in ultima or "julgamento" in ultima:
                status_processo = "Sentenciado"

        # Sigilo
        nivel_sigilo = source.get("nivelSigilo", 0)

        # Última atualização
        ultima_atualizacao = source.get("dataHoraUltimaAtualizacao")

        return {
            "numero_cnj": numero_formatado,
            "classe": classe_nome,
            "assunto": assunto_principal,
            "assuntos": assuntos_lista,
            "comarca": orgao_nome,
            "vara": orgao_nome,
            "tribunal": tribunal.upper() if tribunal else self._resolver_tribunal_nome(numero_original),
            "grau": grau_descricao,
            "polo_ativo": [],  # DataJud NÃO expõe nomes das partes (sigilo)
            "polo_passivo": [],
            "status": status_processo,
            "valor_causa": None,  # DataJud não expõe valor da causa
            "data_distribuicao": data_ajuizamento,
            "movimentacoes": movimentacoes,
            "formato": formato_nome,
            "sistema": sistema_nome,
            "nivel_sigilo": nivel_sigilo,
            "ultima_atualizacao": ultima_atualizacao,
            "municipio_ibge": municipio_ibge,
            "dados_completos": source,
        }

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    async def verificar_disponibilidade(self, tribunal: str = "tjsp") -> Dict[str, Any]:
        """Verifica se a API do DataJud está acessível para um tribunal."""
        alias = tribunal.lower()
        url = f"{self.base_url}/api_publica_{alias}/_search"
        headers = self._get_headers()

        # Busca mínima
        payload = {"query": {"match_all": {}}, "size": 1}

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                total = data.get("hits", {}).get("total", {})
                total_value = total.get("value", 0) if isinstance(total, dict) else total
                return {
                    "disponivel": True,
                    "tribunal": tribunal.upper(),
                    "total_processos": total_value,
                }
        except Exception as e:
            logger.error(f"API DataJud indisponível ({tribunal}): {e}")
            return {"disponivel": False, "tribunal": tribunal.upper(), "erro": str(e)}

    @staticmethod
    def listar_tribunais() -> List[Dict[str, str]]:
        """Retorna lista de todos os tribunais disponíveis na API."""
        tribunais = []
        for seg, mapa in SEGMENTO_TRIBUNAL_MAP.items():
            for cod, alias in mapa.items():
                tribunais.append({
                    "alias": alias,
                    "indice": f"api_publica_{alias}",
                    "nome": TRIBUNAL_NOMES.get(alias, alias.upper()),
                })
        # TREs
        for cod, alias in TRE_MAP.items():
            tribunais.append({
                "alias": alias,
                "indice": f"api_publica_{alias}",
                "nome": f"TRE-{alias.split('-')[1].upper()}",
            })
        return tribunais


# Instância global
_cnj_service = None


def get_cnj_service() -> CNJService:
    """Dependency para obter CNJ Service"""
    global _cnj_service
    if _cnj_service is None:
        _cnj_service = CNJService()
    return _cnj_service
