from abc import ABC, abstractmethod

from company_investigator.domain.entities.search_result import SearchResult


class SearchProviderError(Exception):
    """Falha de infraestrutura ao consultar um SearchProvider (timeout, HTTP, auth
    invalida, ou resposta em formato inesperado)."""


class SearchProviderPort(ABC):
    """Abstracao para provedores de busca (SearchProvider). Uma implementacao concreta
    fica livre para usar qualquer motor de busca por tras: o resto do sistema so
    conhece `search(query) -> list[SearchResult]`."""

    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]: ...
