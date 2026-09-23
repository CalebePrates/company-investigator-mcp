from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ValidationError, field_validator

from company_investigator.application.exceptions import InvestigationNotFoundError
from company_investigator.application.services.investigation_storage_service import (
    InvestigationStorageService,
)
from company_investigator.interface.mcp_server.tools._investigation_output_models import (
    IndiceInvestigacaoOutput,
    PaginaSecaoOutput,
)

_SECOES_DISPONIVEIS = (
    "empresa, candidatos, socios, pessoas_chave, linkedin, redes_sociais, noticias, "
    "contatos, processos_confirmados, processos_referencias, processos_status, "
    "fontes, empresas_relacionadas, pessoas_relacionadas, relacionamentos, "
    "possiveis_relacoes_familiares, peps, limitacoes"
)

_SECAO_DESCRIPTION = (
    "Recupera o conteudo completo (paginado) de UMA secao de uma investigacao "
    "criada por 'investigar_empresa', usando o 'investigation_id' que essa tool "
    "devolveu. Nenhum dado e descartado: percorrendo todas as paginas de uma "
    "secao (veja 'total_paginas' na resposta) voce chega a 100% do que foi "
    "coletado. Parametro 'secao' (obrigatorio), uma das: "
    f"{_SECOES_DISPONIVEIS}. Para a secao 'empresas_relacionadas', cada item traz "
    "seu proprio 'investigation_id' — use-o para percorrer a sub-investigacao "
    "completa daquela empresa relacionada (recursivamente, se ela tambem tiver "
    "empresas relacionadas). Parametros 'pagina' (padrao 1) e 'tamanho_pagina' "
    "(padrao 20, maximo 50) controlam a paginacao. Erro se o investigation_id nao "
    "existir (ou tiver expirado da memoria do servidor) ou a secao for invalida."
)

_INDICE_DESCRIPTION = (
    "Recupera novamente o indice (resumo estrutural) de uma investigacao ja "
    "criada por 'investigar_empresa', usando seu 'investigation_id'. Util para "
    "re-consultar quantos itens cada secao tem sem precisar refazer a "
    "investigacao. Erro se o investigation_id nao existir."
)


class ObterSecaoInvestigacaoInput(BaseModel):
    investigation_id: str
    secao: str
    pagina: int = 1
    tamanho_pagina: int = 20

    @field_validator("investigation_id", "secao")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Este campo nao pode ser vazio.")
        return value.strip()

    @field_validator("pagina")
    @classmethod
    def _pagina_valida(cls, value: int) -> int:
        if value < 1:
            raise ValueError("pagina deve ser >= 1.")
        return value

    @field_validator("tamanho_pagina")
    @classmethod
    def _tamanho_pagina_valido(cls, value: int) -> int:
        if not (1 <= value <= 50):
            raise ValueError("tamanho_pagina deve estar entre 1 e 50.")
        return value


class ObterIndiceInvestigacaoInput(BaseModel):
    investigation_id: str

    @field_validator("investigation_id")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("investigation_id nao pode ser vazio.")
        return value.strip()


def _first_error_message(exc: ValidationError) -> str:
    errors = exc.errors()
    return str(errors[0]["msg"]) if errors else str(exc)


def register_investigation_retrieval_tools(
    server: MCPServer, storage_service: InvestigationStorageService
) -> None:
    @server.tool(name="obter_secao_investigacao", description=_SECAO_DESCRIPTION)
    async def obter_secao_investigacao(
        investigation_id: str, secao: str, pagina: int = 1, tamanho_pagina: int = 20
    ) -> dict[str, object]:
        try:
            validated = ObterSecaoInvestigacaoInput(
                investigation_id=investigation_id,
                secao=secao,
                pagina=pagina,
                tamanho_pagina=tamanho_pagina,
            )
        except ValidationError as exc:
            raise ToolError(_first_error_message(exc)) from exc

        try:
            resultado = storage_service.get_section(
                validated.investigation_id,
                validated.secao,
                pagina=validated.pagina,
                tamanho_pagina=validated.tamanho_pagina,
            )
        except InvestigationNotFoundError as exc:
            raise ToolError(str(exc)) from exc
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

        return PaginaSecaoOutput.from_entity(resultado).model_dump()

    @server.tool(name="obter_indice_investigacao", description=_INDICE_DESCRIPTION)
    async def obter_indice_investigacao(investigation_id: str) -> dict[str, object]:
        try:
            validated = ObterIndiceInvestigacaoInput(investigation_id=investigation_id)
        except ValidationError as exc:
            raise ToolError(_first_error_message(exc)) from exc

        try:
            indice = storage_service.get_index(validated.investigation_id)
        except InvestigationNotFoundError as exc:
            raise ToolError(str(exc)) from exc

        return IndiceInvestigacaoOutput.from_entity(indice).model_dump()
