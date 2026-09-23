import pytest

from company_investigator.application.services.social_media_search_service import (
    SocialMediaSearchService,
)
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
    def __init__(self, results_by_domain: dict[str, list[SearchResult]]) -> None:
        self._results_by_domain = results_by_domain
        self.queries: list[str] = []

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        self.queries.append(query)
        for domain, results in self._results_by_domain.items():
            if domain in query:
                return results
        return []


@pytest.mark.asyncio
async def test_finds_profiles_on_platforms_with_results() -> None:
    provider = FakeSearchProvider(
        {
            "instagram.com": [
                SearchResult(
                    title="Empresa Exemplo (@empresaexemplo) Instagram",
                    url="https://instagram.com/empresaexemplo",
                    snippet="Empresa Exemplo - perfil oficial",
                    source="serper",
                )
            ]
        }
    )
    service = SocialMediaSearchService(search_provider=provider)

    perfis = await service.search(_EMPRESA)

    instagram = next(p for p in perfis if p.plataforma == "Instagram")
    assert instagram.url == "https://instagram.com/empresaexemplo"
    assert instagram.tipo == "empresa"
    assert instagram.confianca == ConfidenceLevel.ALTA


@pytest.mark.asyncio
async def test_skips_platforms_without_results() -> None:
    provider = FakeSearchProvider({})
    service = SocialMediaSearchService(search_provider=provider)

    perfis = await service.search(_EMPRESA)

    assert perfis == []


@pytest.mark.asyncio
async def test_low_confidence_when_company_name_does_not_appear_in_result() -> None:
    provider = FakeSearchProvider(
        {
            "facebook.com": [
                SearchResult(
                    title="Alguma coisa completamente diferente",
                    url="https://facebook.com/outrapagina",
                    snippet="Nada relacionado",
                    source="serper",
                )
            ]
        }
    )
    service = SocialMediaSearchService(search_provider=provider)

    perfis = await service.search(_EMPRESA)

    facebook = next(p for p in perfis if p.plataforma == "Facebook")
    assert facebook.confianca == ConfidenceLevel.BAIXA


@pytest.mark.asyncio
async def test_searches_all_five_expected_platforms() -> None:
    provider = FakeSearchProvider({})
    service = SocialMediaSearchService(search_provider=provider)

    await service.search(_EMPRESA)

    queried_domains = {
        domain
        for domain in ("instagram.com", "facebook.com", "youtube.com", "twitter.com", "tiktok.com")
        if any(domain in q for q in provider.queries)
    }
    assert queried_domains == {
        "instagram.com",
        "facebook.com",
        "youtube.com",
        "twitter.com",
        "tiktok.com",
    }
