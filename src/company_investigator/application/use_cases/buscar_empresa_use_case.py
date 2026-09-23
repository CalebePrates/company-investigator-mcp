from company_investigator.application.exceptions import CompanyNotFoundError
from company_investigator.domain.entities.company import Company
from company_investigator.domain.ports.company_repository import CompanyRepositoryPort
from company_investigator.domain.value_objects.cnpj import Cnpj


class BuscarEmpresaUseCase:
    def __init__(self, company_repository: CompanyRepositoryPort) -> None:
        self._company_repository = company_repository

    async def execute(self, cnpj: Cnpj) -> Company:
        company = await self._company_repository.find_by_cnpj(cnpj)

        if company is None:
            raise CompanyNotFoundError(f"Nenhuma empresa encontrada para o CNPJ {cnpj.value}.")

        return company
