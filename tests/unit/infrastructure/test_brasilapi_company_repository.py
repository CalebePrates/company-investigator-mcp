import httpx
import pytest

from company_investigator.domain.ports.company_repository import CompanyRepositoryError
from company_investigator.domain.value_objects.cnpj import Cnpj
from company_investigator.infrastructure.company.http.brasilapi_company_repository import (
    BrasilApiCompanyRepository,
)


def _repository(handler) -> BrasilApiCompanyRepository:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return BrasilApiCompanyRepository(client=client)


@pytest.mark.asyncio
async def test_returns_company_when_brasilapi_responds_with_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/cnpj/v1/11444777000161"
        return httpx.Response(
            200,
            json={
                "cnpj": "11444777000161",
                "razao_social": "Empresa Exemplo LTDA",
                "nome_fantasia": "Empresa Exemplo",
                "descricao_situacao_cadastral": "ATIVA",
            },
        )

    repository = _repository(handler)

    company = await repository.find_by_cnpj(Cnpj.parse("11.444.777/0001-61"))

    assert company is not None
    assert company.cnpj == "11444777000161"
    assert company.razao_social == "Empresa Exemplo LTDA"
    assert company.nome_fantasia == "Empresa Exemplo"
    assert company.situacao == "ATIVA"


@pytest.mark.asyncio
async def test_returns_none_when_brasilapi_responds_with_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "CNPJ nao encontrado.", "type": "not_found"})

    repository = _repository(handler)

    company = await repository.find_by_cnpj(Cnpj.parse("11.222.333/0001-81"))

    assert company is None


@pytest.mark.asyncio
async def test_raises_repository_error_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    repository = _repository(handler)

    with pytest.raises(CompanyRepositoryError):
        await repository.find_by_cnpj(Cnpj.parse("11.444.777/0001-61"))


@pytest.mark.asyncio
async def test_raises_repository_error_on_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    repository = _repository(handler)

    with pytest.raises(CompanyRepositoryError):
        await repository.find_by_cnpj(Cnpj.parse("11.444.777/0001-61"))


@pytest.mark.asyncio
async def test_raises_repository_error_on_unexpected_http_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "erro interno"})

    repository = _repository(handler)

    with pytest.raises(CompanyRepositoryError):
        await repository.find_by_cnpj(Cnpj.parse("11.444.777/0001-61"))


@pytest.mark.asyncio
async def test_raises_repository_error_on_non_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="isso nao e json")

    repository = _repository(handler)

    with pytest.raises(CompanyRepositoryError):
        await repository.find_by_cnpj(Cnpj.parse("11.444.777/0001-61"))


@pytest.mark.asyncio
async def test_raises_repository_error_when_response_is_missing_expected_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    repository = _repository(handler)

    with pytest.raises(CompanyRepositoryError):
        await repository.find_by_cnpj(Cnpj.parse("11.444.777/0001-61"))
