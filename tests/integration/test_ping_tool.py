import pytest

from company_investigator.interface.mcp_server.server import build_server


@pytest.mark.asyncio
async def test_ping_tool_is_registered_on_the_server() -> None:
    server = build_server()

    tools = await server.list_tools()

    assert any(tool.name == "ping" for tool in tools)


@pytest.mark.asyncio
async def test_ping_tool_returns_ok_status_payload() -> None:
    server = build_server()

    result = await server.call_tool("ping", {})

    assert result.is_error is False
    assert result.structured_content == {
        "status": "ok",
        "message": "MCP funcionando",
    }
