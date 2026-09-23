# Releasing

## Versioning strategy

One version number, three artifacts:

| Artifact | Name | Version source |
|---|---|---|
| PyPI package | `company-investigator-mcp` | `version` in `pyproject.toml` (single source for Python: `--version` and the MCP `serverInfo.version` read it from package metadata) |
| npm launcher | `company-investigator-mcp` | `version` in `npm/package.json` |
| GitHub release | tag `vX.Y.Z` | the two above |

The npm launcher runs `uvx company-investigator-mcp@<its own version>`. It never
uses `@latest`, so a given `npx company-investigator-mcp@X.Y.Z` always runs exactly
PyPI `X.Y.Z` (reproducible, and an old launcher cannot silently start a newer
server). The trade-off is that **every Python release needs a matching npm release**,
even when the launcher code did not change. `tests/unit/test_release_consistency.py`
fails if the two versions (or names/licenses) drift apart.

Order matters: publish to **PyPI first**, then npm. An npm version published before
its PyPI counterpart exists would fail at `uvx` time.

## Checklist

1. Bump `version` in `pyproject.toml` **and** `npm/package.json`; run `uv lock`.
2. Add the entry to `CHANGELOG.md`.
3. Verify:
   ```bash
   uv run pytest && uv run ruff check . && uv run ruff format --check .
   (cd npm && npm test && npm pack --dry-run)
   rm -rf dist && uv build
   uvx --from ./dist/company_investigator_mcp-X.Y.Z-py3-none-any.whl company-investigator-mcp --version
   ```
4. Commit, tag and push: `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin main vX.Y.Z`.
5. Publish to PyPI: `uv publish` (token in `UV_PUBLISH_TOKEN`).
6. Check it resolves: `uvx company-investigator-mcp@X.Y.Z --version`.
7. Publish to npm: `cd npm && npm publish`.
8. Check it resolves: `npx -y company-investigator-mcp@X.Y.Z --version`.
9. Create the GitHub release from the tag, with the `CHANGELOG.md` entry as notes
   and the `dist/` files attached.
