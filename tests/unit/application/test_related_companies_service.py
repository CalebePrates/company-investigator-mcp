import pytest

from company_investigator.application.services.company_data_service import CompanyDataService
from company_investigator.application.services.related_companies_service import (
    RelatedCompaniesService,
)
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.search_result import SearchResult
from company_investigator.domain.entities.socio import Socio
from company_investigator.domain.ports.company_repository import CompanyRepositoryPort
from company_investigator.domain.ports.search_provider import SearchProviderPort
from company_investigator.domain.value_objects.cnpj import Cnpj

_EMPRESA_B = Company(
    cnpj="11444777000161",
    razao_social="Empresa B LTDA",
    nome_fantasia="Empresa B",
    situacao="ATIVA",
)
_EMPRESA_C = Company(
    cnpj="11222333000181",
    razao_social="Empresa C LTDA",
    nome_fantasia="Empresa C",
    situacao="ATIVA",
)
_SOCIO_A = Socio(nome="Socio A", qualificacao="Socio-Administrador")
_SOCIO_B = Socio(nome="Socio B", qualificacao="Socio")


class FakeCompanyRepository(CompanyRepositoryPort):
    def __init__(self, companies: dict[str, Company]) -> None:
        self._companies = companies

    async def find_by_cnpj(self, cnpj: Cnpj) -> Company | None:
        return self._companies.get(cnpj.value)


class FakeSearchProvider(SearchProviderPort):
    def __init__(self, by_query_substring: dict[str, list[SearchResult]] | None = None) -> None:
        self._by_query_substring = by_query_substring or {}
        self.queries: list[str] = []

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        self.queries.append(query)
        for substring, results in self._by_query_substring.items():
            if substring in query:
                return results
        return []


def _service(
    companies: dict[str, Company], results: dict[str, list[SearchResult]]
) -> RelatedCompaniesService:
    data_service = CompanyDataService(company_repository=FakeCompanyRepository(companies))
    return RelatedCompaniesService(
        company_data=data_service, search_provider=FakeSearchProvider(results)
    )


@pytest.mark.asyncio
async def test_partner_with_one_related_company() -> None:
    resultados = {
        "Socio A": [
            SearchResult(
                title="Socio A - CNPJ 11.444.777/0001-61",
                url="https://x.exemplo/1",
                snippet="Socio A e socio-administrador da Empresa B, CNPJ 11.444.777/0001-61",
                source="serper",
            )
        ]
    }
    service = _service({"11444777000161": _EMPRESA_B}, resultados)

    encontradas = await service.find_related([_SOCIO_A])

    assert len(encontradas) == 1
    assert encontradas[0].empresa == _EMPRESA_B
    assert encontradas[0].origem_socio == "Socio A"


@pytest.mark.asyncio
async def test_partner_with_multiple_companies() -> None:
    resultados = {
        "Socio A": [
            SearchResult(
                title="Socio A - CNPJ 11.444.777/0001-61",
                url="https://x.exemplo/1",
                snippet="Socio A, Empresa B, CNPJ 11.444.777/0001-61",
                source="serper",
            ),
            SearchResult(
                title="Socio A - CNPJ 11.222.333/0001-81",
                url="https://x.exemplo/2",
                snippet="Socio A, Empresa C, CNPJ 11.222.333/0001-81",
                source="serper",
            ),
        ]
    }
    service = _service({"11444777000161": _EMPRESA_B, "11222333000181": _EMPRESA_C}, resultados)

    encontradas = await service.find_related([_SOCIO_A])

    assert {e.empresa.cnpj for e in encontradas} == {"11444777000161", "11222333000181"}


@pytest.mark.asyncio
async def test_company_shared_by_two_partners_appears_once_per_partner_but_same_entity() -> None:
    resultado_b = [
        SearchResult(
            title="CNPJ 11.444.777/0001-61",
            url="https://x.exemplo/1",
            snippet="Empresa B, CNPJ 11.444.777/0001-61",
            source="serper",
        )
    ]
    resultados = {"Socio A": resultado_b, "Socio B": resultado_b}
    service = _service({"11444777000161": _EMPRESA_B}, resultados)

    encontradas = await service.find_related([_SOCIO_A, _SOCIO_B])

    assert len(encontradas) == 2
    assert (
        encontradas[0].empresa is encontradas[1].empresa
        or encontradas[0].empresa == encontradas[1].empresa
    )
    assert {e.origem_socio for e in encontradas} == {"Socio A", "Socio B"}


@pytest.mark.asyncio
async def test_partner_with_no_related_companies_found() -> None:
    service = _service({}, {})

    encontradas = await service.find_related([_SOCIO_A])

    assert encontradas == []


@pytest.mark.asyncio
async def test_does_not_include_the_company_itself_as_related() -> None:
    resultados = {
        "Socio A": [
            SearchResult(
                title="CNPJ 11.444.777/0001-61",
                url="https://x.exemplo/1",
                snippet="Empresa B, CNPJ 11.444.777/0001-61",
                source="serper",
            )
        ]
    }
    service = _service({"11444777000161": _EMPRESA_B}, resultados)

    encontradas = await service.find_related([_SOCIO_A], excluir_cnpj="11444777000161")

    assert encontradas == []
