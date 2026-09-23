from importlib.metadata import version

DISTRIBUTION_NAME = "company-investigator-mcp"

# Fonte unica da versao: o `version` do pyproject.toml, lido dos metadados do pacote
# instalado (pip, uvx e `uv sync` sempre instalam esses metadados).
__version__ = version(DISTRIBUTION_NAME)
