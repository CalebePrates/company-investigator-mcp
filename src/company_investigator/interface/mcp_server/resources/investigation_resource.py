from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError
from pydantic import ValidationError

from company_investigator.application.exceptions import InvestigationNotFoundError
from company_investigator.application.services.investigation_storage_service import (
    InvestigationStorageService,
)
from company_investigator.interface.mcp_server.tools._investigation_output_models import (
    IndiceInvestigacaoOutput,
    PaginaSecaoOutput,
)
from company_investigator.interface.mcp_server.tools.investigation_retrieval_tool import (
    ObterSecaoInvestigacaoInput,
)

_DESCRIPTION = (
    "Indice ('investigation://{id}/index') ou uma secao paginada "
    "('investigation://{id}/{secao}?pagina=N&tamanho_pagina=M', padrao pagina=1 e "
    "tamanho_pagina=20, maximo 50) de uma investigacao criada por "
    "investigar_empresa. Mesmo conteudo da tool 'obter_secao_investigacao', para "
    "clientes que preferem consumir Resources; percorra 'total_paginas' para "
    "recuperar 100% de uma secao."
)


def register_investigation_resource(
    server: MCPServer, storage_service: InvestigationStorageService
) -> None:
    @server.resource(
        "investigation://{investigation_id}/{section}{?pagina,tamanho_pagina}",
        name="investigacao",
        description=_DESCRIPTION,
        mime_type="application/json",
    )
    async def investigation_resource(
        investigation_id: str, section: str, pagina: int = 1, tamanho_pagina: int = 20
    ) -> str:
        try:
            if section == "index":
                indice = storage_service.get_index(investigation_id)
                return IndiceInvestigacaoOutput.from_entity(indice).model_dump_json()

            validated = ObterSecaoInvestigacaoInput(
                investigation_id=investigation_id,
                secao=section,
                pagina=pagina,
                tamanho_pagina=tamanho_pagina,
            )
            resultado = storage_service.get_section(
                validated.investigation_id,
                validated.secao,
                pagina=validated.pagina,
                tamanho_pagina=validated.tamanho_pagina,
            )
            return PaginaSecaoOutput.from_entity(resultado).model_dump_json()
        except ValidationError as exc:
            errors = exc.errors()
            raise ResourceError(str(errors[0]["msg"]) if errors else str(exc)) from exc
        except (InvestigationNotFoundError, ValueError) as exc:
            raise ResourceError(str(exc)) from exc
