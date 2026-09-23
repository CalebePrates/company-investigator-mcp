import pytest

from company_investigator.application.services.company_data_service import CompanyDataService
from company_investigator.application.services.company_identification_service import (
    CompanyIdentificationService,
)
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.search_result import SearchResult
from company_investigator.domain.ports.company_repository import (
    CompanyRepositoryError,
    CompanyRepositoryPort,
)
from company_investigator.domain.ports.search_provider import (
    SearchProviderError,
    SearchProviderPort,
)
from company_investigator.domain.value_objects.cnpj import Cnpj

_EMPRESA_EXEMPLO = Company(
    cnpj="11444777000161",
    razao_social="Empresa Exemplo LTDA",
    nome_fantasia="Empresa Exemplo",
    situacao="ATIVA",
)
_OUTRA_EMPRESA = Company(
    cnpj="11222333000181",
    razao_social="Empresa Exemplo do Sul LTDA",
    nome_fantasia="Empresa Exemplo Sul",
    situacao="ATIVA",
)


class FakeCompanyRepository(CompanyRepositoryPort):
    def __init__(self, companies: dict[str, Company] | None = None) -> None:
        self._companies = companies or {}

    async def find_by_cnpj(self, cnpj: Cnpj) -> Company | None:
        return self._companies.get(cnpj.value)


class FakeSearchProvider(SearchProviderPort):
    def __init__(
        self,
        results: list[SearchResult] | None = None,
        error: SearchProviderError | None = None,
    ) -> None:
        self._results = results or []
        self._error = error

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        if self._error is not None:
            raise self._error
        return self._results


def _service(
    companies: dict[str, Company], results: list[SearchResult]
) -> CompanyIdentificationService:
    data_service = CompanyDataService(company_repository=FakeCompanyRepository(companies))
    return CompanyIdentificationService(
        company_data=data_service, search_provider=FakeSearchProvider(results)
    )


@pytest.mark.asyncio
async def test_identify_by_cnpj_finds_the_company_directly() -> None:
    service = _service({"11444777000161": _EMPRESA_EXEMPLO}, results=[])

    result = await service.identify("11.444.777/0001-61")

    assert result.empresa == _EMPRESA_EXEMPLO
    assert result.candidatos == []


@pytest.mark.asyncio
async def test_identify_by_cnpj_returns_no_match_when_company_does_not_exist() -> None:
    service = _service({}, results=[])

    result = await service.identify("11.444.777/0001-61")

    assert result.empresa is None
    assert result.candidatos == []


@pytest.mark.asyncio
async def test_identify_by_name_finds_a_single_match_via_search() -> None:
    results = [
        SearchResult(
            title="Empresa Exemplo LTDA - CNPJ 11.444.777/0001-61",
            url="https://consulta.exemplo/11444777000161",
            snippet="CNPJ: 11.444.777/0001-61",
            source="serper",
        )
    ]
    service = _service({"11444777000161": _EMPRESA_EXEMPLO}, results=results)

    result = await service.identify("Empresa Exemplo")

    assert result.empresa == _EMPRESA_EXEMPLO
    assert result.candidatos == []


@pytest.mark.asyncio
async def test_identify_by_name_returns_no_match_when_nothing_is_found() -> None:
    service = _service({}, results=[])

    result = await service.identify("Empresa Que Nao Existe")

    assert result.empresa is None
    assert result.candidatos == []


@pytest.mark.asyncio
async def test_identify_by_name_returns_multiple_candidates_when_ambiguous() -> None:
    results = [
        SearchResult(
            title="Empresa Exemplo LTDA - CNPJ 11.444.777/0001-61",
            url="https://consulta.exemplo/1",
            snippet="CNPJ: 11.444.777/0001-61",
            source="serper",
        ),
        SearchResult(
            title="Empresa Exemplo do Sul LTDA - CNPJ 11.222.333/0001-81",
            url="https://consulta.exemplo/2",
            snippet="CNPJ: 11.222.333/0001-81",
            source="serper",
        ),
    ]
    service = _service(
        {"11444777000161": _EMPRESA_EXEMPLO, "11222333000181": _OUTRA_EMPRESA},
        results=results,
    )

    result = await service.identify("Empresa Exemplo")

    assert result.empresa is None
    assert {c.cnpj for c in result.candidatos} == {"11444777000161", "11222333000181"}


@pytest.mark.asyncio
async def test_identify_by_name_propagates_search_provider_errors() -> None:
    data_service = CompanyDataService(company_repository=FakeCompanyRepository({}))
    service = CompanyIdentificationService(
        company_data=data_service,
        search_provider=FakeSearchProvider(error=SearchProviderError("falha de busca")),
    )

    with pytest.raises(SearchProviderError):
        await service.identify("Empresa Qualquer")


@pytest.mark.asyncio
async def test_identify_by_cnpj_propagates_repository_errors() -> None:
    class FailingRepository(CompanyRepositoryPort):
        async def find_by_cnpj(self, cnpj: Cnpj) -> Company | None:
            raise CompanyRepositoryError("falha ao consultar BrasilAPI")

    data_service = CompanyDataService(company_repository=FailingRepository())
    service = CompanyIdentificationService(
        company_data=data_service, search_provider=FakeSearchProvider([])
    )

    with pytest.raises(CompanyRepositoryError):
        await service.identify("11.444.777/0001-61")
