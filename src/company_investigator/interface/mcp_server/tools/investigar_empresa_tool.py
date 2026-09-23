from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ValidationError, field_validator

from company_investigator.application.exceptions import CompanyNotFoundError
from company_investigator.application.services.investigation_storage_service import (
    InvestigationStorageService,
)
from company_investigator.application.use_cases.investigar_empresa_use_case import (
    InvestigarEmpresaUseCase,
)
from company_investigator.domain.ports.company_repository import CompanyRepositoryError
from company_investigator.domain.ports.search_provider import SearchProviderError
from company_investigator.interface.mcp_server.tools._investigation_output_models import (
    IndiceInvestigacaoOutput,
)

_PROFUNDIDADE_MAXIMA = 2

_DESCRIPTION = (
    "Investiga uma empresa a partir de um CNPJ ou de um nome (razao social/nome "
    "fantasia), combinando dados cadastrais oficiais (BrasilAPI) com buscas publicas "
    "(via uma Search API) por noticias, perfis em redes sociais (LinkedIn, Instagram, "
    "Facebook, YouTube, X/Twitter, TikTok), pessoas-chave no LinkedIn, processos "
    "judiciais publicos, rede societaria (outras empresas dos socios) e verificacao "
    "de PEP. Parametro 'identificador' (string, obrigatorio): um CNPJ (com ou sem "
    "pontuacao) ou um nome de empresa. Parametro 'profundidade' (inteiro, padrao 1, "
    f"maximo {_PROFUNDIDADE_MAXIMA}): quantos niveis de 'socio -> nova empresa' sao "
    "expandidos; 0 investiga so a empresa pedida. "
    "IMPORTANTE: esta tool NAO devolve os dados completos da investigacao — ela "
    "coleta e guarda tudo, e devolve um INDICE pequeno: um 'investigation_id' e, "
    "para cada secao (socios, noticias, empresas_relacionadas, processos, peps, "
    "etc.), quantos itens existem. Nenhum dado e descartado; para ler o conteudo de "
    "uma secao (com todos os seus itens, paginado se for grande), use a tool "
    "'obter_secao_investigacao' com esse investigation_id, ou o resource MCP "
    "'investigation://{investigation_id}/{secao}'. Empresas relacionadas tambem "
    "tem sua propria sub-investigacao completa, acessivel pelo investigation_id que "
    "aparece dentro da secao 'empresas_relacionadas' — percorra recursivamente para "
    "ver 100% da rede."
)


class InvestigarEmpresaInput(BaseModel):
    """Modelo validado dos parametros recebidos pela tool investigar_empresa."""

    identificador: str
    profundidade: int = 1

    @field_validator("identificador")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("O identificador (CNPJ ou nome da empresa) nao pode ser vazio.")
        return value.strip()

    @field_validator("profundidade")
    @classmethod
    def _within_bounds(cls, value: int) -> int:
        if not (0 <= value <= _PROFUNDIDADE_MAXIMA):
            raise ValueError(f"profundidade deve estar entre 0 e {_PROFUNDIDADE_MAXIMA}.")
        return value


def _first_error_message(exc: ValidationError) -> str:
    errors = exc.errors()
    return str(errors[0]["msg"]) if errors else str(exc)


def register_investigar_empresa_tool(
    server: MCPServer,
    use_case: InvestigarEmpresaUseCase,
    storage_service: InvestigationStorageService,
) -> None:
    @server.tool(name="investigar_empresa", description=_DESCRIPTION)
    async def investigar_empresa(identificador: str, profundidade: int = 1) -> dict[str, object]:
        try:
            validated = InvestigarEmpresaInput(
                identificador=identificador, profundidade=profundidade
            )
        except ValidationError as exc:
            raise ToolError(_first_error_message(exc)) from exc

        try:
            investigacao = await use_case.execute(
                validated.identificador, depth=validated.profundidade
            )
        except CompanyNotFoundError as exc:
            raise ToolError(str(exc)) from exc
        except CompanyRepositoryError as exc:
            raise ToolError(str(exc)) from exc
        except SearchProviderError as exc:
            raise ToolError(str(exc)) from exc

        indice = storage_service.store(investigacao)
        return IndiceInvestigacaoOutput.from_entity(indice).model_dump()
