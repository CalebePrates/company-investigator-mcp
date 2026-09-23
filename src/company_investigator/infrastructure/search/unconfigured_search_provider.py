from company_investigator.domain.entities.search_result import SearchResult
from company_investigator.domain.ports.search_provider import (
    SearchProviderError,
    SearchProviderPort,
)


class UnconfiguredSearchProvider(SearchProviderPort):
    """Usado quando SEARCH_PROVIDER/SEARCH_API_KEY nao estao configuradas: falha de
    forma clara e isolada, sem impedir que as demais tools do servidor funcionem."""

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        raise SearchProviderError(
            "Nenhum SearchProvider configurado: defina as variaveis de ambiente "
            "SEARCH_PROVIDER e SEARCH_API_KEY para habilitar buscas externas "
            "(noticias, redes sociais, LinkedIn, processos)."
        )
