import pytest

from company_investigator.application.services.linkedin_search_service import LinkedInSearchService
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import ConfidenceLevel
from company_investigator.domain.entities.search_result import SearchResult
from company_investigator.domain.ports.search_provider import SearchProviderPort

_EMPRESA = Company(
    cnpj="11444777000161",
    razao_social="Empresa Exemplo LTDA",
    nome_fantasia="Empresa Exemplo",
    situacao="ATIVA",
)


class FakeSearchProvider(SearchProviderPort):
    def __init__(self, by_query_substring: dict[str, list[SearchResult]] | None = None) -> None:
        self._by_query_substring = by_query_substring or {}
        self.queries: list[str] = []

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        self.queries.append(query)
        for substring, results in self._by_query_substring.items():
            if substring in query:
                return results
        return []


@pytest.mark.asyncio
async def test_finds_the_company_linkedin_page() -> None:
    provider = FakeSearchProvider(
        {
            "linkedin.com/company": [
                SearchResult(
                    title="Empresa Exemplo | LinkedIn",
                    url="https://linkedin.com/company/empresa-exemplo",
                    snippet="Empresa Exemplo LTDA no LinkedIn",
                    source="serper",
                )
            ]
        }
    )
    service = LinkedInSearchService(search_provider=provider)

    resultado = await service.search(_EMPRESA)

    assert resultado.empresa is not None
    assert resultado.empresa.url == "https://linkedin.com/company/empresa-exemplo"
    assert resultado.empresa.confianca == ConfidenceLevel.ALTA


@pytest.mark.asyncio
async def test_returns_none_company_page_when_not_found() -> None:
    provider = FakeSearchProvider({})
    service = LinkedInSearchService(search_provider=provider)

    resultado = await service.search(_EMPRESA)

    assert resultado.empresa is None


@pytest.mark.asyncio
async def test_finds_a_key_person_and_parses_name_and_role() -> None:
    provider = FakeSearchProvider(
        {
            "linkedin.com/in": [
                SearchResult(
                    title="Joana Silva - CEO - Empresa Exemplo | LinkedIn",
                    url="https://linkedin.com/in/joanasilva",
                    snippet="Joana Silva atua na Empresa Exemplo LTDA",
                    source="serper",
                )
            ]
        }
    )
    service = LinkedInSearchService(search_provider=provider)

    resultado = await service.search(_EMPRESA)

    assert len(resultado.pessoas_chave) >= 1
    pessoa = next(
        p for p in resultado.pessoas_chave if p.url_linkedin == "https://linkedin.com/in/joanasilva"
    )
    assert pessoa.nome == "Joana Silva"
    assert pessoa.cargo == "CEO"
    assert pessoa.confianca == ConfidenceLevel.MEDIA


@pytest.mark.asyncio
async def test_deduplicates_the_same_person_found_across_multiple_role_queries() -> None:
    same_result = [
        SearchResult(
            title="Joana Silva - CEO e Founder - Empresa Exemplo | LinkedIn",
            url="https://linkedin.com/in/joanasilva",
            snippet="Joana Silva",
            source="serper",
        )
    ]
    provider = FakeSearchProvider({"linkedin.com/in": same_result})
    service = LinkedInSearchService(search_provider=provider)

    resultado = await service.search(_EMPRESA)

    urls = [p.url_linkedin for p in resultado.pessoas_chave]
    assert urls.count("https://linkedin.com/in/joanasilva") == 1


@pytest.mark.asyncio
async def test_low_confidence_for_likely_homonym_without_company_match() -> None:
    provider = FakeSearchProvider(
        {
            "linkedin.com/in": [
                SearchResult(
                    title="Joana Silva - CEO - Outra Empresa Completamente Diferente | LinkedIn",
                    url="https://linkedin.com/in/joanasilva-homonimo",
                    snippet="Sem relacao com a empresa pesquisada",
                    source="serper",
                )
            ]
        }
    )
    service = LinkedInSearchService(search_provider=provider)

    resultado = await service.search(_EMPRESA)

    pessoa = next(
        p
        for p in resultado.pessoas_chave
        if p.url_linkedin == "https://linkedin.com/in/joanasilva-homonimo"
    )
    assert pessoa.confianca == ConfidenceLevel.BAIXA


@pytest.mark.asyncio
async def test_searches_multiple_priority_roles() -> None:
    provider = FakeSearchProvider({})
    service = LinkedInSearchService(search_provider=provider)

    await service.search(_EMPRESA)

    role_queries = [q for q in provider.queries if "linkedin.com/in" in q]
    assert len(role_queries) >= 3
    assert any("CEO" in q for q in role_queries)
    assert any("CFO" in q for q in role_queries)
