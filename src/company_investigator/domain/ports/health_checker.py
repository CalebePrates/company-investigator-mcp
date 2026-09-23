from abc import ABC, abstractmethod

from company_investigator.domain.entities.health_status import HealthStatus


class HealthCheckerPort(ABC):
    @abstractmethod
    def check(self) -> HealthStatus: ...
