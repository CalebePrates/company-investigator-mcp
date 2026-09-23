from mcp.server.mcpserver import MCPServer

from company_investigator.application.use_cases.ping_use_case import PingUseCase


def register_ping_tool(server: MCPServer, ping_use_case: PingUseCase) -> None:
    @server.tool(name="ping", description="Verifica se o servidor MCP esta operante.")
    def ping() -> dict[str, str]:
        return ping_use_case.execute().to_dict()
