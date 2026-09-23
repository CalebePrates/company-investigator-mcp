import dataclasses

import pytest

from mcp_project.domain.entities.health_status import HealthStatus


def test_to_dict_returns_status_and_message() -> None:
    status = HealthStatus(status="ok", message="MCP funcionando")

    assert status.to_dict() == {"status": "ok", "message": "MCP funcionando"}


def test_is_immutable() -> None:
    status = HealthStatus(status="ok", message="MCP funcionando")

    with pytest.raises(dataclasses.FrozenInstanceError):
        status.status = "error"  # type: ignore[misc]
