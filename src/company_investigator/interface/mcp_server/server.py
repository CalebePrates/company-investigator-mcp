import os

import httpx
from mcp.server.mcpserver import MCPServer

from company_investigator.application.services.company_data_service import CompanyDataService
from company_investigator.application.services.company_identification_service import (
    CompanyIdentificationService,
)
from company_investigator.application.services.family_relationship_service import (
    FamilyRelationshipService,
)
from company_investigator.application.services.linkedin_search_service import LinkedInSearchService
from company_investigator.application.services.news_search_service import NewsSearchService
from company_investigator.application.services.partner_search_service import PartnerSearchService
from company_investigator.application.services.pep_service import PEPService
from company_investigator.application.services.process_search_service import ProcessSearchService
from company_investigator.application.services.related_companies_service import (
    RelatedCompaniesService,
)
from company_investigator.application.services.related_people_service import RelatedPeopleService
from company_investigator.application.services.social_media_search_service import (
    SocialMediaSearchService,
)
from company_investigator.application.use_cases.buscar_empresa_use_case import BuscarEmpresaUseCase
from company_investigator.application.use_cases.buscar_informacoes_publicas_use_case import (
    BuscarInformacoesPublicasUseCase,
)
from company_investigator.application.use_cases.investigar_empresa_use_case import (
    InvestigarEmpresaUseCase,
)
from company_investigator.application.use_cases.ping_use_case import PingUseCase
from company_investigator.domain.ports.browser import BrowserPort
from company_investigator.domain.ports.company_repository import CompanyRepositoryPort
from company_investigator.domain.ports.pep_lookup import PEPLookupPort
from company_investigator.domain.ports.process_lookup import ProcessNumberLookupPort
from company_investigator.domain.ports.search_provider import SearchProviderPort
from company_investigator.infrastructure.browser.playwright_browser import PlaywrightBrowser
from company_investigator.infrastructure.company.http.brasilapi_company_repository import (
    BrasilApiCompanyRepository,
)
from company_investigator.infrastructure.health.simple_health_checker import SimpleHealthChecker
from company_investigator.infrastructure.pep.portal_transparencia_pep_adapter import (
    PortalTransparenciaPEPAdapter,
)
from company_investigator.infrastructure.process.datajud_process_adapter import (
    DataJudProcessAdapter,
)
from company_investigator.infrastructure.search.serper_search_adapter import SerperSearchAdapter
from company_investigator.infrastructure.search.unconfigured_search_provider import (
    UnconfiguredSearchProvider,
)
from company_investigator.interface.mcp_server.tools.buscar_empresa_tool import (
    register_buscar_empresa_tool,
)
from company_investigator.interface.mcp_server.tools.buscar_informacoes_publicas_tool import (
    register_buscar_informacoes_publicas_tool,
)
from company_investigator.interface.mcp_server.tools.investigar_empresa_tool import (
    register_investigar_empresa_tool,
)
from company_investigator.interface.mcp_server.tools.ping_tool import register_ping_tool

_HTTP_TIMEOUT_SECONDS = 10.0


def build_server(
    *,
    company_repository: CompanyRepositoryPort | None = None,
    browser: BrowserPort | None = None,
    search_provider: SearchProviderPort | None = None,
    process_number_lookup: ProcessNumberLookupPort | None = None,
    pep_lookup: PEPLookupPort | None = None,
) -> MCPServer:
    """Composition root: monta o MCPServer e injeta as dependencias concretas.

    `company_repository`, `browser`, `search_provider`, `process_number_lookup` e
    `pep_lookup` existem para permitir que testes substituam as fontes reais
    (BrasilAPI, Playwright, Serper, DataJud, Portal da Transparencia) por fakes,
    sem tocar a rede, abrir um navegador ou gastar cota de uma API paga.
    `process_number_lookup`/`pep_lookup` tambem podem ficar `None` de proposito em
    producao: sem DATAJUD_API_KEY/PORTAL_TRANSPARENCIA_API_KEY, a investigacao
    continua funcionando, so sem confirmacao oficial de processos/PEP.
    """
    server = MCPServer("Company Investigator MCP")

    health_checker = SimpleHealthChecker()
    ping_use_case = PingUseCase(health_checker=health_checker)
    register_ping_tool(server, ping_use_case)

    repository = company_repository or BrasilApiCompanyRepository(
        client=httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS)
    )
    buscar_empresa_use_case = BuscarEmpresaUseCase(company_repository=repository)
    register_buscar_empresa_tool(server, buscar_empresa_use_case)

    browser_adapter = browser or PlaywrightBrowser()
    buscar_informacoes_publicas_use_case = BuscarInformacoesPublicasUseCase(browser=browser_adapter)
    register_buscar_informacoes_publicas_tool(server, buscar_informacoes_publicas_use_case)

    search = search_provider or _build_default_search_provider()
    process_lookup = process_number_lookup or _build_default_process_number_lookup()
    pep = pep_lookup or _build_default_pep_lookup()

    company_data_service = CompanyDataService(company_repository=repository)
    identification_service = CompanyIdentificationService(
        company_data=company_data_service, search_provider=search
    )
    investigar_empresa_use_case = InvestigarEmpresaUseCase(
        identification_service=identification_service,
        partner_service=PartnerSearchService(),
        news_service=NewsSearchService(search_provider=search),
        social_media_service=SocialMediaSearchService(search_provider=search),
        linkedin_service=LinkedInSearchService(search_provider=search),
        process_service=ProcessSearchService(
            search_provider=search, process_number_lookup=process_lookup
        ),
        related_companies_service=RelatedCompaniesService(
            company_data=company_data_service, search_provider=search
        ),
        related_people_service=RelatedPeopleService(),
        family_relationship_service=FamilyRelationshipService(search_provider=search),
        pep_service=PEPService(pep_lookup=pep),
    )
    register_investigar_empresa_tool(server, investigar_empresa_use_case)

    return server


def _build_default_search_provider() -> SearchProviderPort:
    provider_name = os.environ.get("SEARCH_PROVIDER", "serper").strip().lower()
    api_key = os.environ.get("SEARCH_API_KEY")

    if not api_key or provider_name != "serper":
        return UnconfiguredSearchProvider()

    return SerperSearchAdapter(
        client=httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS), api_key=api_key
    )


def _build_default_process_number_lookup() -> ProcessNumberLookupPort | None:
    api_key = os.environ.get("DATAJUD_API_KEY")
    if not api_key:
        return None

    return DataJudProcessAdapter(
        client=httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS), api_key=api_key
    )


def _build_default_pep_lookup() -> PEPLookupPort | None:
    api_key = os.environ.get("PORTAL_TRANSPARENCIA_API_KEY")
    if not api_key:
        return None

    return PortalTransparenciaPEPAdapter(
        client=httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS), api_key=api_key
    )
