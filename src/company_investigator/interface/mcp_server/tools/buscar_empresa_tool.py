from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from company_investigator.application.exceptions import CompanyNotFoundError
from company_investigator.application.use_cases.buscar_empresa_use_case import BuscarEmpresaUseCase
from company_investigator.domain.entities.company import Company
from company_investigator.domain.ports.company_repository import CompanyRepositoryError
from company_investigator.domain.value_objects.cnpj import Cnpj, InvalidCnpjError

_DESCRIPTION = (
    "Busca dados cadastrais reais de uma empresa a partir do CNPJ, consultando a "
    "BrasilAPI (fonte publica e oficial de dados de CNPJ da Receita Federal). "
    "Parametro 'cnpj' (string, obrigatorio): aceita com ou sem pontuacao, por "
    "exemplo '12.345.678/0001-90' ou '12345678000190'. Retorna um objeto com "
    "'cnpj' (normalizado, apenas digitos), 'razao_social', 'nome_fantasia' e "
    "'situacao'. Erros possiveis: CNPJ vazio, com letras, com quantidade errada "
    "de digitos, com digitos verificadores matematicamente invalidos, falha ao "
    "consultar a BrasilAPI, ou CNPJ valido porem sem empresa cadastrada."
)


class BuscarEmpresaInput(BaseModel):
    """Modelo validado: normaliza e valida o CNPJ recebido pela tool."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    cnpj: Cnpj

    @field_validator("cnpj", mode="before")
    @classmethod
    def _parse_cnpj(cls, value: object) -> Cnpj:
        if isinstance(value, Cnpj):
            return value
        if not isinstance(value, str):
            raise ValueError("CNPJ deve ser informado como texto.")
        try:
            return Cnpj.parse(value)
        except InvalidCnpjError as exc:
            raise ValueError(str(exc)) from exc


class BuscarEmpresaOutput(BaseModel):
    """Resposta estruturada retornada pela tool buscar_empresa."""

    cnpj: str
    razao_social: str
    nome_fantasia: str
    situacao: str

    @classmethod
    def from_entity(cls, company: Company) -> BuscarEmpresaOutput:
        return cls(
            cnpj=company.cnpj,
            razao_social=company.razao_social,
            nome_fantasia=company.nome_fantasia,
            situacao=company.situacao,
        )


def _first_error_message(exc: ValidationError) -> str:
    errors = exc.errors()
    return str(errors[0]["msg"]) if errors else str(exc)


def register_buscar_empresa_tool(server: MCPServer, use_case: BuscarEmpresaUseCase) -> None:
    @server.tool(name="buscar_empresa", description=_DESCRIPTION)
    async def buscar_empresa(cnpj: str) -> dict[str, str]:
        try:
            validated = BuscarEmpresaInput(cnpj=cnpj)
        except ValidationError as exc:
            raise ToolError(_first_error_message(exc)) from exc

        try:
            company = await use_case.execute(validated.cnpj)
        except CompanyNotFoundError as exc:
            raise ToolError(str(exc)) from exc
        except CompanyRepositoryError as exc:
            raise ToolError(str(exc)) from exc

        return BuscarEmpresaOutput.from_entity(company).model_dump()
