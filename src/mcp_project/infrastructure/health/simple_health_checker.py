from mcp_project.domain.entities.health_status import HealthStatus
from mcp_project.domain.ports.health_checker import HealthCheckerPort


class SimpleHealthChecker(HealthCheckerPort):
    def check(self) -> HealthStatus:
        return HealthStatus(status="ok", message="MCP funcionando")
