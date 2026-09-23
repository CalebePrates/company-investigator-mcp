import re
from datetime import UTC, datetime

import httpx
from pydantic import BaseModel, Field, ValidationError

from company_investigator.domain.entities.investigation import DadosOficiaisProcesso, Movimento
from company_investigator.domain.ports.process_lookup import (
    ProcessLookupError,
    ProcessNumberLookupPort,
)

_BASE_URL = "https://api-publica.datajud.cnj.jus.br"

_NUMERO_PATTERN = re.compile(r"^(\d{7})-?(\d{2})\.?(\d{4})\.?(\d)\.?(\d{2})\.?(\d{4})$")

# Numeracao unica de processos (Resolucao CNJ 65/2008): o segmento (J) e o
# tribunal (TR) ficam embutidos no proprio numero. Tabela cobrindo os segmentos
# mais relevantes para investigacao de empresas (estadual, federal, trabalho e
# tribunais superiores); segmentos raramente pertinentes aqui (eleitoral, militar)
# ficam fora por ora e resultam em ProcessLookupError explicito, nunca um alias
# adivinhado.
_SEGMENTO_SUPERIOR = {"1": "stf", "3": "stj"}
_SEGMENTO_ESTADUAL = "8"
_TRIBUNAIS_ESTADUAL = {
    "01": "tjac", "02": "tjal", "03": "tjap", "04": "tjam", "05": "tjba",
    "06": "tjce", "07": "tjdft", "08": "tjes", "09": "tjgo", "10": "tjma",
    "11": "tjmt", "12": "tjms", "13": "tjmg", "14": "tjpa", "15": "tjpb",
    "16": "tjpr", "17": "tjpe", "18": "tjpi", "19": "tjrj", "20": "tjrn",
    "21": "tjrs", "22": "tjro", "23": "tjrr", "24": "tjsc", "25": "tjse",
    "26": "tjsp", "27": "tjto",
}  # fmt: skip
_SEGMENTO_FEDERAL = "4"
_TRIBUNAIS_FEDERAL = {f"{i:02d}": f"trf{i}" for i in range(1, 7)}
_SEGMENTO_TRABALHO = "5"
_TRIBUNAIS_TRABALHO = {f"{i:02d}": f"trt{i}" for i in range(1, 25)}


def _resolve_alias(digits: str) -> str | None:
    segmento = digits[13]
    tribunal = digits[14:16]

    if segmento in _SEGMENTO_SUPERIOR:
        return _SEGMENTO_SUPERIOR[segmento]
    if segmento == _SEGMENTO_ESTADUAL:
        return _TRIBUNAIS_ESTADUAL.get(tribunal)
    if segmento == _SEGMENTO_FEDERAL:
        return _TRIBUNAIS_FEDERAL.get(tribunal)
    if segmento == _SEGMENTO_TRABALHO:
        return _TRIBUNAIS_TRABALHO.get(tribunal)
    return None


class _NomeCodigo(BaseModel):
    nome: str | None = None


class _MovimentoResponse(BaseModel):
    nome: str | None = None
    dataHora: str | None = None  # noqa: N815 (nome vem assim da API)


class _ProcessoSource(BaseModel):
    numeroProcesso: str  # noqa: N815
    tribunal: str
    grau: str | None = None
    classe: _NomeCodigo | None = None
    assuntos: list[_NomeCodigo] = []
    movimentos: list[_MovimentoResponse] = []
    orgaoJulgador: _NomeCodigo | None = None  # noqa: N815
    dataAjuizamento: str | None = None  # noqa: N815
    sistema: _NomeCodigo | None = None


class _Hit(BaseModel):
    source: _ProcessoSource = Field(alias="_source")


class _Hits(BaseModel):
    hits: list[_Hit] = []


class _DataJudResponse(BaseModel):
    hits: _Hits


class DataJudProcessAdapter(ProcessNumberLookupPort):
    """Consulta a API Publica do DataJud (CNJ) por numero de processo:
    POST https://api-publica.datajud.cnj.jus.br/api_publica_<tribunal>/_search,
    autenticado via 'Authorization: APIKey <chave>'. A API nao expoe partes
    (nome/CPF/CNPJ) - so metadados processuais (classe, assuntos, movimentos,
    orgao julgador, grau, sistema). Fonte: https://datajud-wiki.cnj.jus.br/api-publica/
    """

    def __init__(self, client: httpx.AsyncClient, api_key: str) -> None:
        self._client = client
        self._api_key = api_key

    async def find_by_number(self, numero_processo: str) -> DadosOficiaisProcesso | None:
        match = _NUMERO_PATTERN.match(numero_processo.strip())
        if not match:
            raise ProcessLookupError(
                f"Numero de processo em formato invalido: {numero_processo!r}."
            )
        digits = "".join(match.groups())

        alias = _resolve_alias(digits)
        if alias is None:
            raise ProcessLookupError(
                f"Nao foi possivel identificar um tribunal suportado para o "
                f"processo {numero_processo} (segmento/tribunal fora da tabela)."
            )

        url = f"{_BASE_URL}/api_publica_{alias}/_search"
        try:
            response = await self._client.post(
                url,
                json={"query": {"match": {"numeroProcesso": digits}}},
                headers={
                    "Authorization": f"APIKey {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        except httpx.TimeoutException as exc:
            raise ProcessLookupError(
                f"Tempo limite excedido ao consultar o DataJud para {numero_processo}."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProcessLookupError(
                f"Falha de comunicacao ao consultar o DataJud para {numero_processo}."
            ) from exc

        if response.status_code in (401, 403):
            raise ProcessLookupError("DataJud rejeitou a API key (autenticacao invalida).")

        if response.status_code != 200:
            raise ProcessLookupError(
                f"DataJud retornou status {response.status_code} para {numero_processo}."
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProcessLookupError(
                f"DataJud retornou uma resposta que nao e JSON valido para {numero_processo}."
            ) from exc

        try:
            parsed = _DataJudResponse.model_validate(payload)
        except ValidationError as exc:
            raise ProcessLookupError(
                f"DataJud retornou um formato de resposta inesperado para {numero_processo}."
            ) from exc

        if not parsed.hits.hits:
            return None

        source = parsed.hits.hits[0].source
        return DadosOficiaisProcesso(
            numero_processo=source.numeroProcesso,
            tribunal=source.tribunal,
            grau=source.grau,
            orgao_julgador=source.orgaoJulgador.nome if source.orgaoJulgador else None,
            classe=source.classe.nome if source.classe else None,
            assuntos=[a.nome for a in source.assuntos if a.nome],
            movimentos=[
                Movimento(nome=m.nome, data=m.dataHora) for m in source.movimentos if m.nome
            ],
            data_ajuizamento=source.dataAjuizamento,
            sistema=source.sistema.nome if source.sistema else None,
            fonte="DataJud (CNJ)",
            consultado_em=datetime.now(UTC),
        )
