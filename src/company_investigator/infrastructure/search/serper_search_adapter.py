import httpx
from pydantic import BaseModel, ValidationError

from company_investigator.domain.entities.search_result import SearchResult
from company_investigator.domain.ports.search_provider import (
    SearchProviderError,
    SearchProviderPort,
)

_ENDPOINT = "https://google.serper.dev/search"
_PROVIDER_NAME = "serper"


class _SerperOrganicResult(BaseModel):
    title: str
    link: str
    snippet: str = ""


class _SerperSearchResponse(BaseModel):
    organic: list[_SerperOrganicResult] = []


class SerperSearchAdapter(SearchProviderPort):
    """Busca via Serper.dev (https://serper.dev): um wrapper da API de resultados do
    Google Search. POST https://google.serper.dev/search, autenticado por X-API-KEY.
    Como retorna o SERP real do Google, suporta os mesmos operadores (site:, aspas
    etc.) usados nas queries dos services de investigacao."""

    def __init__(self, client: httpx.AsyncClient, api_key: str) -> None:
        self._client = client
        self._api_key = api_key

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        try:
            response = await self._client.post(
                _ENDPOINT,
                json={"q": query, "num": max_results},
                headers={"X-API-KEY": self._api_key, "Content-Type": "application/json"},
            )
        except httpx.TimeoutException as exc:
            raise SearchProviderError(
                f"Tempo limite excedido ao pesquisar '{query}' no Serper."
            ) from exc
        except httpx.HTTPError as exc:
            raise SearchProviderError(
                f"Falha de comunicacao ao pesquisar '{query}' no Serper."
            ) from exc

        if response.status_code in (401, 403):
            raise SearchProviderError("Serper rejeitou a API key (autenticacao invalida).")

        if response.status_code != 200:
            raise SearchProviderError(
                f"Serper retornou status {response.status_code} para a busca '{query}'."
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise SearchProviderError(
                f"Serper retornou uma resposta que nao e JSON valido para '{query}'."
            ) from exc

        try:
            parsed = _SerperSearchResponse.model_validate(payload)
        except ValidationError as exc:
            raise SearchProviderError(
                f"Serper retornou um formato de resposta inesperado para '{query}'."
            ) from exc

        return [
            SearchResult(
                title=item.title, url=item.link, snippet=item.snippet, source=_PROVIDER_NAME
            )
            for item in parsed.organic
        ]
