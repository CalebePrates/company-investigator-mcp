import httpx
import pytest

from company_investigator.domain.ports.process_lookup import ProcessLookupError
from company_investigator.infrastructure.process.datajud_process_adapter import (
    DataJudProcessAdapter,
)


def _adapter(handler, api_key: str = "test-key") -> DataJudProcessAdapter:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return DataJudProcessAdapter(client=client, api_key=api_key)


def _hit(**overrides: object) -> dict:
    base = {
        "numeroProcesso": "00012345620208260100",
        "tribunal": "TJSP",
        "grau": "G1",
        "classe": {"codigo": 7, "nome": "Procedimento Comum Civel"},
        "assuntos": [{"codigo": 1127, "nome": "Rescisao / Resolucao"}],
        "movimentos": [{"codigo": 51, "nome": "Distribuicao", "dataHora": "2020-05-20T10:00:00Z"}],
        "orgaoJulgador": {"codigo": 100, "nome": "1a Vara Civel"},
        "dataAjuizamento": "2020-05-20T10:00:00Z",
        "sistema": {"codigo": 1, "nome": "PJe"},
    }
    base.update(overrides)
    return {"_source": base}


@pytest.mark.asyncio
async def test_finds_process_data_by_number() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api_publica_tjsp/_search"
        assert request.headers["Authorization"] == "APIKey test-key"
        return httpx.Response(200, json={"hits": {"hits": [_hit()]}})

    adapter = _adapter(handler)

    dados = await adapter.find_by_number("0001234-56.2020.8.26.0100")

    assert dados is not None
    assert dados.numero_processo == "00012345620208260100"
    assert dados.tribunal == "TJSP"
    assert dados.classe == "Procedimento Comum Civel"
    assert dados.orgao_julgador == "1a Vara Civel"
    assert dados.sistema == "PJe"
    assert dados.assuntos == ["Rescisao / Resolucao"]
    assert dados.movimentos[0].nome == "Distribuicao"


@pytest.mark.asyncio
async def test_returns_none_when_process_is_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hits": {"hits": []}})

    adapter = _adapter(handler)

    dados = await adapter.find_by_number("0001234-56.2020.8.26.0100")

    assert dados is None


@pytest.mark.asyncio
async def test_raises_for_process_number_with_unsupported_tribunal_segment() -> None:
    adapter = _adapter(lambda request: httpx.Response(200, json={"hits": {"hits": []}}))

    with pytest.raises(ProcessLookupError):
        await adapter.find_by_number(
            "0001234-56.2020.7.00.0100"
        )  # segmento 7 (militar da uniao), fora da tabela


@pytest.mark.asyncio
async def test_raises_for_malformed_process_number() -> None:
    adapter = _adapter(lambda request: httpx.Response(200, json={"hits": {"hits": []}}))

    with pytest.raises(ProcessLookupError):
        await adapter.find_by_number("nao-e-um-numero-de-processo")


@pytest.mark.asyncio
async def test_raises_on_invalid_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "invalid key"})

    adapter = _adapter(handler, api_key="chave-invalida")

    with pytest.raises(ProcessLookupError):
        await adapter.find_by_number("0001234-56.2020.8.26.0100")


@pytest.mark.asyncio
async def test_raises_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    adapter = _adapter(handler)

    with pytest.raises(ProcessLookupError):
        await adapter.find_by_number("0001234-56.2020.8.26.0100")


@pytest.mark.asyncio
async def test_raises_on_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    adapter = _adapter(handler)

    with pytest.raises(ProcessLookupError):
        await adapter.find_by_number("0001234-56.2020.8.26.0100")


@pytest.mark.asyncio
async def test_raises_on_unexpected_http_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "erro interno"})

    adapter = _adapter(handler)

    with pytest.raises(ProcessLookupError):
        await adapter.find_by_number("0001234-56.2020.8.26.0100")


@pytest.mark.asyncio
async def test_raises_on_non_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="nao e json")

    adapter = _adapter(handler)

    with pytest.raises(ProcessLookupError):
        await adapter.find_by_number("0001234-56.2020.8.26.0100")


@pytest.mark.asyncio
async def test_raises_when_response_is_missing_expected_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hits": {"hits": [{"_source": {"unexpected": "shape"}}]}})

    adapter = _adapter(handler)

    with pytest.raises(ProcessLookupError):
        await adapter.find_by_number("0001234-56.2020.8.26.0100")


@pytest.mark.asyncio
async def test_resolves_federal_tribunal_alias() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api_publica_trf3/_search"
        return httpx.Response(200, json={"hits": {"hits": [_hit(tribunal="TRF3")]}})

    adapter = _adapter(handler)

    dados = await adapter.find_by_number("0001234-56.2020.4.03.0100")

    assert dados is not None
    assert dados.tribunal == "TRF3"


@pytest.mark.asyncio
async def test_process_with_multiple_subjects_and_movements() -> None:
    hit = _hit(
        assuntos=[
            {"codigo": 1, "nome": "Assunto 1"},
            {"codigo": 2, "nome": "Assunto 2"},
        ],
        movimentos=[
            {"codigo": 51, "nome": "Distribuicao", "dataHora": "2020-05-20T10:00:00Z"},
            {"codigo": 52, "nome": "Juntada", "dataHora": "2020-06-01T10:00:00Z"},
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hits": {"hits": [hit]}})

    adapter = _adapter(handler)

    dados = await adapter.find_by_number("0001234-56.2020.8.26.0100")

    assert dados is not None
    assert len(dados.assuntos) == 2
    assert len(dados.movimentos) == 2
