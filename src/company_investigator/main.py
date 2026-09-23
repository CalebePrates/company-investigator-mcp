from company_investigator.interface.mcp_server.server import build_server


def main() -> None:
    server = build_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
