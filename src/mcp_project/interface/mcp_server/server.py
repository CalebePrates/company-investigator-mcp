from mcp.server.mcpserver import MCPServer

from mcp_project.application.use_cases.ping_use_case import PingUseCase
from mcp_project.infrastructure.health.simple_health_checker import SimpleHealthChecker
from mcp_project.interface.mcp_server.tools.ping_tool import register_ping_tool


def build_server() -> MCPServer:
    server = MCPServer("mcp-project")

    health_checker = SimpleHealthChecker()
    ping_use_case = PingUseCase(health_checker=health_checker)

    register_ping_tool(server, ping_use_case)

    return server
