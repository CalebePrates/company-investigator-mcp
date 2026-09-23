from abc import ABC, abstractmethod

from mcp_project.domain.entities.health_status import HealthStatus


class HealthCheckerPort(ABC):
    @abstractmethod
    def check(self) -> HealthStatus: ...
