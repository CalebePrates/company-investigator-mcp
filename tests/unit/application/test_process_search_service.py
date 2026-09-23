from datetime import UTC, datetime

import pytest

from company_investigator.application.services.process_search_service import ProcessSearchService
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import DadosOficiaisProcesso, Movimento
from company_investigator.domain.entities.search_result import SearchResult
from company_investigator.domain.ports.process_lookup import (
    ProcessLookupError,
    ProcessNumberLookupPort,
)
from company_investigator.domain.ports.search_provider import (
    SearchProviderError,
    SearchProviderPort,
)

_EMPRESA = Company(
    cnpj="11444777000161",
    razao_social="Empresa Exemplo LTDA",
    nome_fantasia="Empresa Exemplo",
    situacao="ATIVA",
)

_DADOS_OFICIAIS = DadosOficiaisProcesso(
    numero_processo="00012345620208260100",
    tribunal="TJSP",
    grau="G1",
    orgao_julgador="1a Vara Civel",
    classe="Procedimento Comum Civel",
    assuntos=["Rescisao"],
    movimentos=[Movimento(nome="Distribuicao", data="2020-05-20T10:00:00Z")],
    data_ajuizamento="2020-05-20T10:00:00Z",
    sistema="PJe",
    fonte="DataJud (CNJ)",
    consultado_em=datetime.now(UTC),
)


class FakeSearchProvider(SearchProviderPort):
    def __init__(
        self, by_query_substring: dict[str, list[SearchResult]] | None = None, error=None
    ) -> None:
        self._by_query_substring = by_query_substring or {}
        self._error = error
        self.queries: list[str] = []

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        self.queries.append(query)
        if self._error is not None:
            raise self._error
        for substring, results in self._by_query_substring.items():
            if substring in query:
                return results
        return []


class FakeProcessNumberLookup(ProcessNumberLookupPort):
    def __init__(self, dados: dict[str, DadosOficiaisProcesso] | None = None, error=None) -> None:
        self._dados = dados or {}
        self._error = error
        self.consultados: list[str] = []

    async def find_by_number(self, numero_processo: str) -> DadosOficiaisProcesso | None:
        self.consultados.append(numero_processo)
        if self._error is not None:
            raise self._error
        return self._dados.get(numero_processo)


@pytest.mark.asyncio
async def test_no_references_found_results_in_nao_confirmada() -> None:
    service = ProcessSearchService(search_provider=FakeSearchProvider({}))

    resultado = await service.search(_EMPRESA, pessoas=[])

    assert resultado.confirmados == []
    assert resultado.referencias == []
    assert resultado.status.status == "nao_confirmada"


@pytest.mark.asyncio
async def test_reference_found_without_a_detectable_process_number_stays_a_reference() -> None:
    provider = FakeSearchProvider(
        {
            "Empresa Exemplo": [
                SearchResult(
                    title="Empresa Exemplo processada",
                    url="https://noticia.exemplo/1",
                    snippet="Sem numero de processo aqui",
                    source="serper",
                )
            ]
        }
    )
    service = ProcessSearchService(search_provider=provider)

    resultado = await service.search(_EMPRESA, pessoas=[])

    assert len(resultado.referencias) == 1
    assert resultado.referencias[0].numero_processo_detectado is None
    assert resultado.confirmados == []
    assert resultado.status.status == "parcial"


@pytest.mark.asyncio
async def test_reference_with_process_number_gets_confirmed_via_lookup() -> None:
    provider = FakeSearchProvider(
        {
            "Empresa Exemplo": [
                SearchResult(
                    title="Empresa Exemplo - processo 0001234-56.2020.8.26.0100",
                    url="https://noticia.exemplo/1",
                    snippet="processo judicial",
                    source="serper",
                )
            ]
        }
    )
    lookup = FakeProcessNumberLookup({"0001234-56.2020.8.26.0100": _DADOS_OFICIAIS})
    service = ProcessSearchService(search_provider=provider, process_number_lookup=lookup)

    resultado = await service.search(_EMPRESA, pessoas=[])

    assert len(resultado.confirmados) == 1
    confirmado = resultado.confirmados[0]
    assert confirmado.dados.numero_processo == "00012345620208260100"
    assert confirmado.relacionado_a == "Empresa Exemplo"
    assert confirmado.tipo_relacionado == "empresa"
    assert resultado.status.status == "realizada"


@pytest.mark.asyncio
async def test_search_failure_for_one_subject_does_not_prevent_others() -> None:
    provider = FakeSearchProvider(
        {
            "Empresa Exemplo": [
                SearchResult(
                    title="Empresa Exemplo - processo 0001234-56.2020.8.26.0100",
                    url="https://noticia.exemplo/1",
                    snippet="processo judicial",
                    source="serper",
                )
            ],
        }
    )
    service = ProcessSearchService(search_provider=provider)

    resultado = await service.search(_EMPRESA, pessoas=["Fulano de Tal"])

    assert len(resultado.referencias) == 1
    assert resultado.referencias[0].relacionado_a == "Empresa Exemplo"


@pytest.mark.asyncio
async def test_person_reference_is_marked_with_tipo_pessoa() -> None:
    provider = FakeSearchProvider(
        {
            "Fulano de Tal": [
                SearchResult(
                    title="Fulano de Tal e processado",
                    url="https://noticia.exemplo/2",
                    snippet="processo envolvendo Fulano de Tal",
                    source="serper",
                )
            ]
        }
    )
    service = ProcessSearchService(search_provider=provider)

    resultado = await service.search(_EMPRESA, pessoas=["Fulano de Tal"])

    referencia = next(r for r in resultado.referencias if r.relacionado_a == "Fulano de Tal")
    assert referencia.tipo_relacionado == "pessoa"


@pytest.mark.asyncio
async def test_homonym_reference_gets_low_confidence() -> None:
    provider = FakeSearchProvider(
        {
            "Fulano de Tal": [
                SearchResult(
                    title="Processo envolvendo uma pessoa qualquer",
                    url="https://noticia.exemplo/3",
                    snippet="nada relacionado ao nome pesquisado",
                    source="serper",
                )
            ]
        }
    )
    service = ProcessSearchService(search_provider=provider)

    resultado = await service.search(_EMPRESA, pessoas=["Fulano de Tal"])

    referencia = next(r for r in resultado.referencias if r.relacionado_a == "Fulano de Tal")
    assert referencia.confianca.value == "baixa"


@pytest.mark.asyncio
async def test_search_provider_failure_is_recorded_without_raising() -> None:
    service = ProcessSearchService(
        search_provider=FakeSearchProvider(error=SearchProviderError("falha de busca"))
    )

    resultado = await service.search(_EMPRESA, pessoas=[])

    assert resultado.confirmados == []
    assert resultado.referencias == []
    assert resultado.status.status == "nao_confirmada"
    assert resultado.status.motivo is not None


@pytest.mark.asyncio
async def test_lookup_not_configured_leaves_references_unconfirmed() -> None:
    provider = FakeSearchProvider(
        {
            "Empresa Exemplo": [
                SearchResult(
                    title="Empresa Exemplo - processo 0001234-56.2020.8.26.0100",
                    url="https://noticia.exemplo/1",
                    snippet="processo judicial",
                    source="serper",
                )
            ]
        }
    )
    service = ProcessSearchService(search_provider=provider, process_number_lookup=None)

    resultado = await service.search(_EMPRESA, pessoas=[])

    assert resultado.confirmados == []
    assert len(resultado.referencias) == 1
    assert resultado.status.status == "parcial"


@pytest.mark.asyncio
async def test_lookup_failure_for_a_number_keeps_it_as_reference_only() -> None:
    provider = FakeSearchProvider(
        {
            "Empresa Exemplo": [
                SearchResult(
                    title="Empresa Exemplo - processo 0001234-56.2020.8.26.0100",
                    url="https://noticia.exemplo/1",
                    snippet="processo judicial",
                    source="serper",
                )
            ]
        }
    )
    lookup = FakeProcessNumberLookup(error=ProcessLookupError("DataJud indisponivel"))
    service = ProcessSearchService(search_provider=provider, process_number_lookup=lookup)

    resultado = await service.search(_EMPRESA, pessoas=[])

    assert resultado.confirmados == []
    assert len(resultado.referencias) == 1
    assert resultado.status.status == "parcial"


@pytest.mark.asyncio
async def test_multiple_processes_are_all_confirmed() -> None:
    outros_dados = DadosOficiaisProcesso(
        numero_processo="00098765420208260200",
        tribunal="TJSP",
        grau="G1",
        orgao_julgador="2a Vara Civel",
        classe="Execucao",
        assuntos=["Divida"],
        movimentos=[],
        data_ajuizamento=None,
        sistema="PJe",
        fonte="DataJud (CNJ)",
        consultado_em=datetime.now(UTC),
    )
    provider = FakeSearchProvider(
        {
            "Empresa Exemplo": [
                SearchResult(
                    title="processo 0001234-56.2020.8.26.0100",
                    url="https://noticia.exemplo/1",
                    snippet="processo judicial",
                    source="serper",
                ),
                SearchResult(
                    title="processo 0009876-54.2020.8.26.0200",
                    url="https://noticia.exemplo/2",
                    snippet="processo judicial",
                    source="serper",
                ),
            ]
        }
    )
    lookup = FakeProcessNumberLookup(
        {
            "0001234-56.2020.8.26.0100": _DADOS_OFICIAIS,
            "0009876-54.2020.8.26.0200": outros_dados,
        }
    )
    service = ProcessSearchService(search_provider=provider, process_number_lookup=lookup)

    resultado = await service.search(_EMPRESA, pessoas=[])

    assert len(resultado.confirmados) == 2
