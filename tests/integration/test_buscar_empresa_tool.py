import pytest
from mcp.server.mcpserver.exceptions import ToolError

from company_investigator.domain.entities.company import Company
from company_investigator.domain.ports.company_repository import (
    CompanyRepositoryError,
    CompanyRepositoryPort,
)
from company_investigator.domain.value_objects.cnpj import Cnpj
from company_investigator.interface.mcp_server.server import build_server


class FakeCompanyRepository(CompanyRepositoryPort):
    """Substitui a BrasilApiCompanyRepository real nestes testes, sem tocar a rede."""

    def __init__(
        self,
        companies: dict[str, Company] | None = None,
        error: CompanyRepositoryError | None = None,
    ) -> None:
        self._companies = companies or {}
        self._error = error

    async def find_by_cnpj(self, cnpj: Cnpj) -> Company | None:
        if self._error is not None:
            raise self._error
        return self._companies.get(cnpj.value)


_EMPRESA_EXEMPLO = Company(
    cnpj="11444777000161",
    razao_social="Empresa Exemplo LTDA",
    nome_fantasia="Empresa Exemplo",
    situacao="ATIVA",
)


@pytest.mark.asyncio
async def test_buscar_empresa_tool_is_registered_on_the_server() -> None:
    server = build_server(company_repository=FakeCompanyRepository())

    tools = await server.list_tools()

    assert any(tool.name == "buscar_empresa" for tool in tools)


@pytest.mark.asyncio
async def test_buscar_empresa_tool_documents_the_cnpj_parameter() -> None:
    server = build_server(company_repository=FakeCompanyRepository())

    tools = await server.list_tools()
    tool = next(tool for tool in tools if tool.name == "buscar_empresa")

    assert "cnpj" in tool.input_schema["properties"]


@pytest.mark.asyncio
async def test_buscar_empresa_tool_returns_structured_company_data() -> None:
    server = build_server(
        company_repository=FakeCompanyRepository({"11444777000161": _EMPRESA_EXEMPLO})
    )

    result = await server.call_tool("buscar_empresa", {"cnpj": "11.444.777/0001-61"})

    assert result.is_error is False
    assert result.structured_content == {
        "cnpj": "11444777000161",
        "razao_social": "Empresa Exemplo LTDA",
        "nome_fantasia": "Empresa Exemplo",
        "situacao": "ATIVA",
    }


@pytest.mark.asyncio
async def test_buscar_empresa_tool_accepts_cnpj_already_normalized() -> None:
    server = build_server(
        company_repository=FakeCompanyRepository({"11444777000161": _EMPRESA_EXEMPLO})
    )

    result = await server.call_tool("buscar_empresa", {"cnpj": "11444777000161"})

    assert result.is_error is False
    assert result.structured_content["cnpj"] == "11444777000161"


@pytest.mark.asyncio
async def test_buscar_empresa_tool_rejects_empty_cnpj() -> None:
    server = build_server(company_repository=FakeCompanyRepository())

    with pytest.raises(ToolError):
        await server.call_tool("buscar_empresa", {"cnpj": ""})


@pytest.mark.asyncio
async def test_buscar_empresa_tool_rejects_cnpj_with_letters() -> None:
    server = build_server(company_repository=FakeCompanyRepository())

    with pytest.raises(ToolError):
        await server.call_tool("buscar_empresa", {"cnpj": "abc"})


@pytest.mark.asyncio
async def test_buscar_empresa_tool_rejects_cnpj_with_wrong_amount_of_digits() -> None:
    server = build_server(company_repository=FakeCompanyRepository())

    with pytest.raises(ToolError):
        await server.call_tool("buscar_empresa", {"cnpj": "123"})


@pytest.mark.asyncio
async def test_buscar_empresa_tool_rejects_cnpj_with_invalid_check_digits() -> None:
    server = build_server(company_repository=FakeCompanyRepository())

    with pytest.raises(ToolError):
        await server.call_tool("buscar_empresa", {"cnpj": "12345678000190"})


@pytest.mark.asyncio
async def test_buscar_empresa_tool_raises_when_company_is_not_found() -> None:
    server = build_server(company_repository=FakeCompanyRepository({}))

    with pytest.raises(ToolError):
        await server.call_tool("buscar_empresa", {"cnpj": "11.222.333/0001-81"})


@pytest.mark.asyncio
async def test_buscar_empresa_tool_raises_on_repository_failure() -> None:
    server = build_server(
        company_repository=FakeCompanyRepository(
            error=CompanyRepositoryError("falha de comunicacao com a BrasilAPI")
        )
    )

    with pytest.raises(ToolError):
        await server.call_tool("buscar_empresa", {"cnpj": "11.444.777/0001-61"})


@pytest.mark.asyncio
async def test_ping_tool_keeps_working_alongside_buscar_empresa() -> None:
    server = build_server(company_repository=FakeCompanyRepository())

    result = await server.call_tool("ping", {})

    assert result.is_error is False
    assert result.structured_content == {"status": "ok", "message": "MCP funcionando"}
