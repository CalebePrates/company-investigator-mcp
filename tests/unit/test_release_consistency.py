"""O launcher npm executa `uvx company-investigator-mcp@<versao do package.json>`.
Se as versoes divergirem, `npx company-investigator-mcp` rodaria outro pacote Python
(ou nenhum) - estes testes impedem isso de chegar a uma release."""

import json
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _pyproject() -> dict:
    return tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def _package_json() -> dict:
    return json.loads((_ROOT / "npm" / "package.json").read_text(encoding="utf-8"))


def test_npm_launcher_version_matches_python_package_version() -> None:
    assert _package_json()["version"] == _pyproject()["version"]


def test_npm_launcher_and_python_package_share_the_same_name() -> None:
    assert _package_json()["name"] == _pyproject()["name"] == "company-investigator-mcp"


def test_npm_package_ships_the_same_license() -> None:
    assert (_ROOT / "npm" / "LICENSE").read_text(encoding="utf-8") == (_ROOT / "LICENSE").read_text(
        encoding="utf-8"
    )
    assert _package_json()["license"] == _pyproject()["license"] == "MIT"
