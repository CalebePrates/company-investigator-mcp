from mcp_project.application.use_cases.ping_use_case import PingUseCase
from mcp_project.domain.entities.health_status import HealthStatus
from mcp_project.domain.ports.health_checker import HealthCheckerPort


class FakeHealthChecker(HealthCheckerPort):
    def __init__(self, result: HealthStatus) -> None:
        self._result = result

    def check(self) -> HealthStatus:
        return self._result


def test_execute_returns_whatever_the_health_checker_reports() -> None:
    expected = HealthStatus(status="ok", message="MCP funcionando")
    use_case = PingUseCase(health_checker=FakeHealthChecker(expected))

    result = use_case.execute()

    assert result == expected
