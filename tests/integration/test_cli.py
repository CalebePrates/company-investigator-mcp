"""Executa os comandos de console instalados pelo pacote (os mesmos que `pip install`
e `uvx` expoem), como processos filhos reais. So usa `--version`, que responde e
sai sem subir o servidor stdio."""

import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

from company_investigator.main import main

_DISTRIBUTION = "company-investigator-mcp"


def test_distribution_is_published_as_company_investigator_mcp() -> None:
    assert version(_DISTRIBUTION) == "1.0.0"


def test_version_flag_prints_the_package_version_and_exits(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == version(_DISTRIBUTION)


@pytest.mark.parametrize("command", ["company-investigator-mcp", "company-investigator"])
def test_console_scripts_are_installed_and_answer_version(command: str) -> None:
    script = Path(sys.executable).parent / command

    completed = subprocess.run(
        [str(script), "--version"], capture_output=True, text=True, timeout=30, check=False
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == version(_DISTRIBUTION)
