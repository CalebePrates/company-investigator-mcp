import httpx
import pytest

from company_investigator.domain.ports.search_provider import SearchProviderError
from company_investigator.infrastructure.search.serper_search_adapter import SerperSearchAdapter


def _adapter(handler, api_key: str = "test-key") -> SerperSearchAdapter:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return SerperSearchAdapter(client=client, api_key=api_key)


@pytest.mark.asyncio
async def test_returns_search_results_on_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-KEY"] == "test-key"
        return httpx.Response(
            200,
            json={
                "organic": [
                    {
                        "title": "Credmei | LinkedIn",
                        "link": "https://linkedin.com/company/credmei",
                        "snippet": "Credmei Securitizadora",
                        "position": 1,
                    }
                ]
            },
        )

    adapter = _adapter(handler)

    results = await adapter.search("Credmei LinkedIn")

    assert len(results) == 1
    assert results[0].title == "Credmei | LinkedIn"
    assert results[0].url == "https://linkedin.com/company/credmei"
    assert results[0].snippet == "Credmei Securitizadora"
    assert results[0].source == "serper"


@pytest.mark.asyncio
async def test_returns_empty_list_when_no_organic_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"organic": []})

    adapter = _adapter(handler)

    results = await adapter.search("consulta sem resultados")

    assert results == []


@pytest.mark.asyncio
async def test_raises_on_invalid_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Unauthorized.", "statusCode": 403})

    adapter = _adapter(handler, api_key="chave-invalida")

    with pytest.raises(SearchProviderError):
        await adapter.search("qualquer coisa")


@pytest.mark.asyncio
async def test_raises_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    adapter = _adapter(handler)

    with pytest.raises(SearchProviderError):
        await adapter.search("qualquer coisa")


@pytest.mark.asyncio
async def test_raises_on_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    adapter = _adapter(handler)

    with pytest.raises(SearchProviderError):
        await adapter.search("qualquer coisa")


@pytest.mark.asyncio
async def test_raises_on_unexpected_http_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "erro interno"})

    adapter = _adapter(handler)

    with pytest.raises(SearchProviderError):
        await adapter.search("qualquer coisa")


@pytest.mark.asyncio
async def test_raises_on_non_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="isso nao e json")

    adapter = _adapter(handler)

    with pytest.raises(SearchProviderError):
        await adapter.search("qualquer coisa")


@pytest.mark.asyncio
async def test_raises_when_organic_items_are_missing_expected_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"organic": [{"unexpected": "shape"}]})

    adapter = _adapter(handler)

    with pytest.raises(SearchProviderError):
        await adapter.search("qualquer coisa")
