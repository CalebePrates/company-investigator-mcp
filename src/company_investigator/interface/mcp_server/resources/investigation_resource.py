from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError

from company_investigator.application.exceptions import InvestigationNotFoundError
from company_investigator.application.services.investigation_storage_service import (
    InvestigationStorageService,
)
from company_investigator.interface.mcp_server.tools._investigation_output_models import (
    IndiceInvestigacaoOutput,
    PaginaSecaoOutput,
)

_DESCRIPTION = (
    "Indice ('investigation://{id}/index') ou primeira pagina de uma secao "
    "('investigation://{id}/{secao}') de uma investigacao criada por "
    "investigar_empresa. Para paginar alem da primeira pagina de uma secao "
    "grande, use a tool 'obter_secao_investigacao' com o mesmo investigation_id."
)


def register_investigation_resource(
    server: MCPServer, storage_service: InvestigationStorageService
) -> None:
    @server.resource(
        "investigation://{investigation_id}/{section}",
        name="investigacao",
        description=_DESCRIPTION,
        mime_type="application/json",
    )
    async def investigation_resource(investigation_id: str, section: str) -> str:
        try:
            if section == "index":
                indice = storage_service.get_index(investigation_id)
                return IndiceInvestigacaoOutput.from_entity(indice).model_dump_json()

            pagina = storage_service.get_section(investigation_id, section)
            return PaginaSecaoOutput.from_entity(pagina).model_dump_json()
        except InvestigationNotFoundError as exc:
            raise ResourceError(str(exc)) from exc
        except ValueError as exc:
            raise ResourceError(str(exc)) from exc
