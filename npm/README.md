# company-investigator-mcp (npm launcher)

Run [Company Investigator MCP](https://github.com/CalebePrates/company-investigator-mcp)
with `npx`:

```bash
npx -y company-investigator-mcp
```

This package is a **thin launcher only**. The MCP server is written in Python and
published on PyPI as
[`company-investigator-mcp`](https://pypi.org/project/company-investigator-mcp/).
The launcher finds [`uvx`](https://docs.astral.sh/uv/) and runs
`uvx company-investigator-mcp@<this package's version>`, passing stdin, stdout,
stderr, arguments, environment variables and the exit code straight through. It
has no dependencies and contains no server logic.

## Requirements

- Node.js 18+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (provides `uvx`).
  `uvx` downloads Python 3.14 automatically if it is not installed.
- Optional, only for `buscar_informacoes_publicas` (browser automation):
  `uvx --from company-investigator-mcp playwright install chromium`

If `uvx` is not on `PATH`, the launcher also checks the uv installer's default
directories (`~/.local/bin`, `~/.cargo/bin`, …) and falls back to `uv tool run`.
Set `UVX_PATH` to point at a specific `uvx` executable.

## MCP client configuration

```json
{
  "mcpServers": {
    "company-investigator": {
      "command": "npx",
      "args": ["-y", "company-investigator-mcp"],
      "env": {
        "SEARCH_PROVIDER": "serper",
        "SEARCH_API_KEY": "...",
        "DATAJUD_API_KEY": "...",
        "PORTAL_TRANSPARENCIA_API_KEY": "..."
      }
    }
  }
}
```

All keys are optional; see the
[main README](https://github.com/CalebePrates/company-investigator-mcp#readme).

## Versioning

npm `X.Y.Z` always runs PyPI `X.Y.Z`, never `@latest`. To use a specific release,
pin the npm package: `npx -y company-investigator-mcp@1.0.0`.

## License

MIT
