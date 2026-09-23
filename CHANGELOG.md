# Changelog

All notable changes to this project are documented here. Versions follow
[Semantic Versioning](https://semver.org/); the PyPI package, the npm launcher and
the GitHub release always share the same version number.

## [1.0.0] - 2026-09-23

First public release.

### Added

- Distribution on PyPI as `company-investigator-mcp`
  (`uvx company-investigator-mcp`, `pip install company-investigator-mcp`).
- npm launcher `company-investigator-mcp` (`npx company-investigator-mcp`), which
  runs the PyPI package of the same version through `uvx`.
- `company-investigator-mcp --version`.
- MCP `serverInfo.version` now reports the package version.
- Clear error with install instructions when Playwright's Chromium is missing
  (the browser is never downloaded automatically).
- MIT license.
- GitHub Actions CI: lint, format and tests (Linux, macOS), npm launcher tests
  (Linux, macOS, Windows), package build and an npx → uvx → Python smoke test.
- Public README: installation (uvx, npx, pip), Chromium setup, MCP client
  configuration, tool examples, limitations and responsible use.

### Tools

- `ping`, `buscar_empresa`, `buscar_informacoes_publicas`, `investigar_empresa`,
  `obter_secao_investigacao`, `obter_indice_investigacao` and the
  `investigation://{investigation_id}/{secao}` resource.

### Changed

- The distribution was renamed from `company-investigator` to
  `company-investigator-mcp`. The import package is still `company_investigator`,
  and the `company-investigator` command is kept as an alias.

[1.0.0]: https://github.com/CalebePrates/company-investigator-mcp/releases/tag/v1.0.0
