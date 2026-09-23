"""Fala com o servidor como um cliente MCP externo de verdade: um processo filho
real, pelo transporte stdio (o mesmo caminho do `.mcp.json`), usando o cliente
oficial do SDK - sem `build_server()` em processo e sem nenhum fake. So usa
caminhos que nunca tocam a rede."""

import json
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_SERVER = StdioServerParameters(
    command=sys.executable,
    args=["-c", "from company_investigator import main; main()"],
)


@pytest.mark.asyncio
async def test_external_client_can_discover_and_call_the_server_over_stdio() -> None:
    async with stdio_client(_SERVER) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        tools = {tool.name for tool in (await session.list_tools()).tools}
        assert tools == {
            "ping",
            "buscar_empresa",
            "buscar_informacoes_publicas",
            "investigar_empresa",
            "obter_secao_investigacao",
            "obter_indice_investigacao",
        }

        templates = (await session.list_resource_templates()).resource_templates
        assert any(t.uri_template.startswith("investigation://") for t in templates)

        pong = await session.call_tool("ping", {})
        assert pong.is_error is False
        assert pong.structured_content == {"status": "ok", "message": "MCP funcionando"}


@pytest.mark.asyncio
async def test_external_client_gets_readable_errors_for_bad_investigation_ids() -> None:
    async with stdio_client(_SERVER) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        via_tool = await session.call_tool(
            "obter_secao_investigacao", {"investigation_id": "nao-existe", "secao": "socios"}
        )
        assert via_tool.is_error is True
        assert "Nenhuma investigacao encontrada" in json.dumps(
            [c.model_dump() for c in via_tool.content]
        )

        indice = await session.call_tool("obter_indice_investigacao", {"investigation_id": " "})
        assert indice.is_error is True

        invalido = await session.call_tool("investigar_empresa", {"identificador": "  "})
        assert invalido.is_error is True
