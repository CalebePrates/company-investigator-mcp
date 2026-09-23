import pytest

from company_investigator.application.exceptions import CompanyNotFoundError
from company_investigator.application.use_cases.buscar_empresa_use_case import BuscarEmpresaUseCase
from company_investigator.domain.entities.company import Company
from company_investigator.domain.ports.company_repository import (
    CompanyRepositoryError,
    CompanyRepositoryPort,
)
from company_investigator.domain.value_objects.cnpj import Cnpj


class FakeCompanyRepository(CompanyRepositoryPort):
    def __init__(
        self,
        companies: dict[str, Company] | None = None,
        error: CompanyRepositoryError | None = None,
    ) -> None:
        self._companies = companies or {}
        self._error = error

    async def find_by_cnpj(self, cnpj: Cnpj) -> Company | None:
        if self._error is not None:
            raise self._error
        return self._companies.get(cnpj.value)


@pytest.mark.asyncio
async def test_execute_returns_the_company_matching_the_cnpj() -> None:
    cnpj = Cnpj.parse("11.444.777/0001-61")
    expected = Company(
        cnpj=cnpj.value,
        razao_social="Empresa Exemplo LTDA",
        nome_fantasia="Empresa Exemplo",
        situacao="ATIVA",
    )
    use_case = BuscarEmpresaUseCase(FakeCompanyRepository({cnpj.value: expected}))

    result = await use_case.execute(cnpj)

    assert result == expected


@pytest.mark.asyncio
async def test_execute_raises_when_no_company_matches_the_cnpj() -> None:
    cnpj = Cnpj.parse("11.222.333/0001-81")
    use_case = BuscarEmpresaUseCase(FakeCompanyRepository({}))

    with pytest.raises(CompanyNotFoundError):
        await use_case.execute(cnpj)


@pytest.mark.asyncio
async def test_execute_propagates_repository_errors_without_wrapping_them() -> None:
    cnpj = Cnpj.parse("11.444.777/0001-61")
    use_case = BuscarEmpresaUseCase(
        FakeCompanyRepository(error=CompanyRepositoryError("falha de comunicacao"))
    )

    with pytest.raises(CompanyRepositoryError):
        await use_case.execute(cnpj)
