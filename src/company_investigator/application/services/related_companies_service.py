from dataclasses import dataclass

from company_investigator.application.services._cnpj_extraction import extract_cnpj_candidates
from company_investigator.application.services.company_data_service import CompanyDataService
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import ConfidenceLevel
from company_investigator.domain.entities.socio import Socio
from company_investigator.domain.ports.search_provider import SearchProviderPort
from company_investigator.domain.value_objects.cnpj import Cnpj, InvalidCnpjError

_TERMOS_HISTORICOS = ("ex-socio", "ex-socia", "foi socio", "foi socia", "deixou a sociedade")


@dataclass(frozen=True)
class EmpresaRelacionadaEncontrada:
    """Resultado bruto da descoberta: uma empresa + de qual socio ela veio. Ainda
    nao inclui a sub-investigacao completa (isso e responsabilidade do Use Case,
    que decide se/quando expandir mais um nivel da rede)."""

    empresa: Company
    origem_socio: str
    participacao: str  # "atual" | "historica" | "desconhecida"
    fonte: str
    confianca: ConfidenceLevel


class RelatedCompaniesService:
    """Descobre outras empresas de um socio. Nao existe uma API oficial e gratuita
    para 'buscar empresas por nome de socio' sem baixar toda a base da Receita
    Federal (o que exigiria persistencia, fora de escopo) - por isso o desenho e o
    mesmo do CompanyIdentificationService: pesquisa via SearchProvider, extrai
    CNPJs candidatos do texto, e so confirma via CompanyDataService (BrasilAPI, a
    fonte oficial de CNPJ/QSA do projeto)."""

    def __init__(
        self, company_data: CompanyDataService, search_provider: SearchProviderPort
    ) -> None:
        self._company_data = company_data
        self._search_provider = search_provider

    async def find_related(
        self, socios: list[Socio], excluir_cnpj: str | None = None
    ) -> list[EmpresaRelacionadaEncontrada]:
        encontradas: list[EmpresaRelacionadaEncontrada] = []

        for socio in socios:
            results = await self._search_provider.search(
                f'"{socio.nome}" socio OR administrador CNPJ', max_results=10
            )

            candidatos = {
                cnpj
                for result in results
                for cnpj in extract_cnpj_candidates(result.title, result.snippet)
            }

            for raw_cnpj in candidatos:
                try:
                    cnpj = Cnpj.parse(raw_cnpj)
                except InvalidCnpjError:
                    continue
                if excluir_cnpj is not None and cnpj.value == excluir_cnpj:
                    continue

                empresa = await self._company_data.get_by_cnpj(cnpj)
                if empresa is None:
                    continue

                texto = " ".join(f"{r.title} {r.snippet}" for r in results).lower()
                participacao = (
                    "historica" if any(t in texto for t in _TERMOS_HISTORICOS) else "atual"
                )

                encontradas.append(
                    EmpresaRelacionadaEncontrada(
                        empresa=empresa,
                        origem_socio=socio.nome,
                        participacao=participacao,
                        fonte="serper",
                        confianca=ConfidenceLevel.MEDIA,
                    )
                )

        return encontradas
