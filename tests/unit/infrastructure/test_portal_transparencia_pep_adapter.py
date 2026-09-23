import httpx
import pytest

from company_investigator.domain.ports.pep_lookup import PEPLookupError
from company_investigator.infrastructure.pep.portal_transparencia_pep_adapter import (
    PortalTransparenciaPEPAdapter,
)


def _adapter(handler, api_key: str = "test-key") -> PortalTransparenciaPEPAdapter:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return PortalTransparenciaPEPAdapter(client=client, api_key=api_key)


@pytest.mark.asyncio
async def test_returns_registros_on_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["chave-api-dados"] == "test-key"
        assert request.url.params["nome"] == "Fulano de Tal"
        return httpx.Response(
            200,
            json=[
                {
                    "cpf": "***112108**",
                    "nome": "Fulano de Tal",
                    "sigla_funcao": "MIN",
                    "descricao_funcao": "Ministro",
                    "nivel_funcao": "1",
                    "cod_orgao": "1",
                    "nome_orgao": "Ministerio Exemplo",
                    "dt_inicio_exercicio": "01/01/2020",
                    "dt_fim_exercicio": "01/01/2022",
                    "dt_fim_carencia": "01/01/2027",
                }
            ],
        )

    adapter = _adapter(handler)

    registros = await adapter.search("Fulano de Tal")

    assert len(registros) == 1
    assert registros[0].cpf == "***112108**"
    assert registros[0].funcao == "Ministro"
    assert registros[0].orgao == "Ministerio Exemplo"
    assert registros[0].data_inicio == "01/01/2020"


@pytest.mark.asyncio
async def test_returns_empty_list_when_no_registros_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    adapter = _adapter(handler)

    registros = await adapter.search("Ninguem Encontrado")

    assert registros == []


@pytest.mark.asyncio
async def test_raises_on_invalid_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "unauthorized"})

    adapter = _adapter(handler, api_key="chave-invalida")

    with pytest.raises(PEPLookupError):
        await adapter.search("Fulano de Tal")


@pytest.mark.asyncio
async def test_raises_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    adapter = _adapter(handler)

    with pytest.raises(PEPLookupError):
        await adapter.search("Fulano de Tal")


@pytest.mark.asyncio
async def test_raises_on_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    adapter = _adapter(handler)

    with pytest.raises(PEPLookupError):
        await adapter.search("Fulano de Tal")


@pytest.mark.asyncio
async def test_raises_on_unexpected_http_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "erro interno"})

    adapter = _adapter(handler)

    with pytest.raises(PEPLookupError):
        await adapter.search("Fulano de Tal")


@pytest.mark.asyncio
async def test_raises_on_non_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="nao e json")

    adapter = _adapter(handler)

    with pytest.raises(PEPLookupError):
        await adapter.search("Fulano de Tal")


@pytest.mark.asyncio
async def test_raises_when_response_is_missing_expected_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"unexpected": "shape"}])

    adapter = _adapter(handler)

    with pytest.raises(PEPLookupError):
        await adapter.search("Fulano de Tal")


@pytest.mark.asyncio
async def test_sends_cpf_when_provided() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["cpf"] == "***112108**"
        return httpx.Response(200, json=[])

    adapter = _adapter(handler)

    await adapter.search("Fulano de Tal", cpf="***112108**")
