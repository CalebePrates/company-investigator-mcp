from dataclasses import dataclass


@dataclass(frozen=True)
class HealthStatus:
    status: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"status": self.status, "message": self.message}
