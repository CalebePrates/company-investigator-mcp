from mcp_project.domain.entities.health_status import HealthStatus
from mcp_project.domain.ports.health_checker import HealthCheckerPort


class PingUseCase:
    def __init__(self, health_checker: HealthCheckerPort) -> None:
        self._health_checker = health_checker

    def execute(self) -> HealthStatus:
        return self._health_checker.check()
