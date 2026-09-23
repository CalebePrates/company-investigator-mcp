import pytest

from company_investigator.application.services.news_search_service import NewsSearchService
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.search_result import SearchResult
from company_investigator.domain.ports.search_provider import SearchProviderPort

_EMPRESA = Company(
    cnpj="11444777000161",
    razao_social="Empresa Exemplo LTDA",
    nome_fantasia="Empresa Exemplo",
    situacao="ATIVA",
)


class FakeSearchProvider(SearchProviderPort):
    def __init__(self, results: list[SearchResult]) -> None:
        self._results = results
        self.queries: list[str] = []

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        self.queries.append(query)
        return self._results


@pytest.mark.asyncio
async def test_returns_news_found_via_search() -> None:
    provider = FakeSearchProvider(
        [
            SearchResult(
                title="Empresa Exemplo capta investimento",
                url="https://noticias.exemplo/1",
                snippet="A Empresa Exemplo anunciou...",
                source="serper",
            )
        ]
    )
    service = NewsSearchService(search_provider=provider)

    noticias = await service.search(_EMPRESA)

    assert len(noticias) == 1
    assert noticias[0].titulo == "Empresa Exemplo capta investimento"
    assert noticias[0].url == "https://noticias.exemplo/1"
    assert "razão social" not in provider.queries[0].lower()


@pytest.mark.asyncio
async def test_returns_empty_list_when_source_has_no_results() -> None:
    provider = FakeSearchProvider([])
    service = NewsSearchService(search_provider=provider)

    noticias = await service.search(_EMPRESA)

    assert noticias == []


@pytest.mark.asyncio
async def test_deduplicates_results_with_the_same_url() -> None:
    duplicated = SearchResult(
        title="Empresa Exemplo",
        url="https://noticias.exemplo/1",
        snippet="...",
        source="serper",
    )
    provider = FakeSearchProvider([duplicated, duplicated])
    service = NewsSearchService(search_provider=provider)

    noticias = await service.search(_EMPRESA)

    assert len(noticias) == 1
