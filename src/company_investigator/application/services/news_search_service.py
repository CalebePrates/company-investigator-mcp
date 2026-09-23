from datetime import UTC, datetime

from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import Noticia
from company_investigator.domain.ports.search_provider import SearchProviderPort


class NewsSearchService:
    """Pesquisa noticias publicas sobre a empresa via SearchProvider."""

    def __init__(self, search_provider: SearchProviderPort) -> None:
        self._search_provider = search_provider

    async def search(self, company: Company) -> list[Noticia]:
        nome = company.nome_fantasia or company.razao_social
        results = await self._search_provider.search(f'"{nome}" noticias', max_results=10)

        consultado_em = datetime.now(UTC)
        noticias: list[Noticia] = []
        seen_urls: set[str] = set()
        for result in results:
            if result.url in seen_urls:
                continue
            seen_urls.add(result.url)
            noticias.append(
                Noticia(
                    titulo=result.title,
                    url=result.url,
                    fonte=result.source,
                    resumo=result.snippet,
                    consultado_em=consultado_em,
                )
            )
        return noticias
