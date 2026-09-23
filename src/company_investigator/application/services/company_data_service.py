from company_investigator.domain.entities.company import Company
from company_investigator.domain.ports.company_repository import CompanyRepositoryPort
from company_investigator.domain.value_objects.cnpj import Cnpj


class CompanyDataService:
    """Ponto unico de acesso aos dados cadastrais de uma empresa (BrasilAPI)."""

    def __init__(self, company_repository: CompanyRepositoryPort) -> None:
        self._company_repository = company_repository

    async def get_by_cnpj(self, cnpj: Cnpj) -> Company | None:
        return await self._company_repository.find_by_cnpj(cnpj)
