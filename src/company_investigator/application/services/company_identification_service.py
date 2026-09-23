from dataclasses import dataclass, field

from company_investigator.application.services._cnpj_extraction import extract_cnpj_candidates
from company_investigator.application.services.company_data_service import CompanyDataService
from company_investigator.domain.entities.company import Company
from company_investigator.domain.ports.search_provider import SearchProviderPort
from company_investigator.domain.value_objects.cnpj import Cnpj, InvalidCnpjError


@dataclass(frozen=True)
class CompanyIdentificationResult:
    empresa: Company | None
    candidatos: list[Company] = field(default_factory=list)


class CompanyIdentificationService:
    """Identifica uma empresa a partir de um CNPJ ou de um nome (razao social/nome
    fantasia). Um CNPJ vai direto ao CompanyDataService; um nome e pesquisado via
    SearchProvider para descobrir CNPJs candidatos, que sao entao confirmados no
    CompanyDataService antes de contarem como uma correspondencia real."""

    def __init__(
        self, company_data: CompanyDataService, search_provider: SearchProviderPort
    ) -> None:
        self._company_data = company_data
        self._search_provider = search_provider

    async def identify(self, identificador: str) -> CompanyIdentificationResult:
        try:
            cnpj = Cnpj.parse(identificador)
        except InvalidCnpjError:
            cnpj = None

        if cnpj is not None:
            company = await self._company_data.get_by_cnpj(cnpj)
            return CompanyIdentificationResult(empresa=company, candidatos=[])

        return await self._identify_by_name(identificador)

    async def _identify_by_name(self, nome: str) -> CompanyIdentificationResult:
        results = await self._search_provider.search(f'"{nome}" CNPJ', max_results=10)

        candidatos_cnpj = {
            cnpj
            for result in results
            for cnpj in extract_cnpj_candidates(result.title, result.snippet)
        }

        empresas: dict[str, Company] = {}
        for raw_cnpj in candidatos_cnpj:
            try:
                cnpj = Cnpj.parse(raw_cnpj)
            except InvalidCnpjError:
                continue
            company = await self._company_data.get_by_cnpj(cnpj)
            if company is not None:
                empresas[company.cnpj] = company

        matches = list(empresas.values())
        if len(matches) == 1:
            return CompanyIdentificationResult(empresa=matches[0], candidatos=[])
        return CompanyIdentificationResult(empresa=None, candidatos=matches)
