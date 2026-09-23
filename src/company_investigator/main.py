import argparse
from collections.abc import Sequence

from company_investigator.interface.mcp_server.server import build_server
from company_investigator.version import __version__


def main(argv: Sequence[str] | None = None) -> None:
    # Sem argumentos o comportamento e o de sempre: sobe o servidor MCP via stdio.
    # `--version`/`--help` respondem e saem antes de qualquer coisa tocar o stdio.
    parser = argparse.ArgumentParser(
        prog="company-investigator-mcp",
        description="Company Investigator MCP - servidor MCP (stdio) de inteligencia "
        "publica sobre empresas brasileiras.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.parse_args(argv)

    server = build_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
