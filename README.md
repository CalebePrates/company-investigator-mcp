# Company Investigator MCP

MCP server for public company intelligence, corporate relationships
and evidence-based investigation.

[![CI](https://github.com/CalebePrates/company-investigator-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/CalebePrates/company-investigator-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/company-investigator-mcp)](https://pypi.org/project/company-investigator-mcp/)
[![npm](https://img.shields.io/npm/v/company-investigator-mcp)](https://www.npmjs.com/package/company-investigator-mcp)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)
![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-6E56CF)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/CalebePrates/company-investigator-mcp/blob/main/LICENSE)

## What

An [MCP](https://modelcontextprotocol.io) server that lets an LLM client (Claude,
or any other MCP-compatible client) look up a Brazilian company by CNPJ or name,
walk its corporate network, and pull together public evidence — official
registry data, corporate relationships, news, social/LinkedIn profiles, public
judicial proceedings and Politically Exposed Person (PEP) checks — into one
structured, source-attributed result.

Looking up a company usually means checking half a dozen disconnected sources by
hand and manually piecing together who runs it and what else they are involved
in. This server does the collection:

```text
Company/CNPJ → Partners → Related companies → Related people
  → News / LinkedIn / public profiles → Public proceedings → PEP
  → Relationship graph → Structured investigation (read in pages by the client)
```

The server **collects and structures** the evidence; it does not interpret it.
Deciding what to dig into, cross-checking sources and writing the final analysis
is the job of the MCP client / AI agent (Claude, a local Qwen, …). There is
deliberately no LLM inside this server.

```text
MCP Client / AI Agent → Company Investigator MCP → structured investigation
                      → MCP Client / AI Agent → analysis
```

## Features

- **Company intelligence** — official registry data (CNPJ, razão social, nome
  fantasia, status) via BrasilAPI.
- **Corporate relationships** — discovers other companies a partner is
  associated with, and expands the network to a configurable depth (0–2).
- **People intelligence** — partners, administrators and LinkedIn key people
  (CEO, founders, directors and other leadership roles).
- **News and public sources** — public mentions of the company, each with title,
  URL, source and confidence.
- **LinkedIn / social profiles** — company page and key people on LinkedIn, plus
  Instagram, Facebook, YouTube, X/Twitter and TikTok.
- **Public proceedings** — public mentions of judicial processes, with official
  confirmation by process number where possible.
- **PEP identification** — checks partners against the official Politically
  Exposed Person registry, distinguishing a confirmed match from a homonym.
- **Relationship graph** — companies and people connected by typed, sourced
  edges (`socio_de`, `relacionada_por_socio`), without duplicating entities.
- **Large investigations without blowing the client's context** — the result is
  handed over as a small index plus paginated sections. Nothing is truncated.

## Installation

Pick one; all of them run the same Python server over stdio.

| Method | Command | Requires |
|---|---|---|
| **uvx** (recommended) | `uvx company-investigator-mcp` | [uv](https://docs.astral.sh/uv/getting-started/installation/) — downloads Python 3.14 automatically if missing |
| **npx** | `npx -y company-investigator-mcp` | Node.js 18+ **and** uv |
| **pip** | `pip install company-investigator-mcp`, then `company-investigator-mcp` | Python 3.14+ |

```bash
company-investigator-mcp --version   # prints 1.0.0
```

The older `company-investigator` command is kept as an alias.

**About the npm package:** it is only a launcher, with no server code. It finds
`uvx` and runs `uvx company-investigator-mcp@<its own version>`, so npm `1.0.0`
always runs exactly PyPI `1.0.0` — never `@latest`. Pin it the usual way
(`npx -y company-investigator-mcp@1.0.0`) to lock a version. If your MCP client
cannot find `uvx` (desktop apps often start with a minimal `PATH`), the launcher
also looks in uv's default install directories; you can set `UVX_PATH` to the
`uvx` executable explicitly.

### Browser (only for `buscar_informacoes_publicas`)

Installing the package does **not** download a browser — no large downloads or
side effects at install time. The `buscar_informacoes_publicas` tool uses
browser automation (Playwright) and needs Chromium, installed once:

```bash
uvx --from company-investigator-mcp playwright install chromium   # uvx / npx users
playwright install chromium                                       # pip (same environment)
uv run playwright install chromium                                # from a git clone
```

On Linux, add `--with-deps` if system libraries are missing. Every other tool
works without it; if Chromium is missing, this tool returns an error with exactly
the commands above. No restart is needed after installing.

### From source

```bash
git clone https://github.com/CalebePrates/company-investigator-mcp.git
cd company-investigator-mcp
uv sync
uv run company-investigator-mcp
```

## Configuration

No environment variable is required to start the server — `ping`,
`buscar_empresa` and `buscar_informacoes_publicas` never depend on them. Without a
key, the parts of `investigar_empresa` that need it (search discovery, official
process confirmation, PEP checks) return an empty result with an explanation in
`limitacoes` instead of failing.

| Variable | Enables | Where to get it |
|---|---|---|
| `SEARCH_API_KEY` (+ `SEARCH_PROVIDER=serper`) | News, social profiles, LinkedIn, corporate network discovery, name search | Free tier at [serper.dev](https://serper.dev) — 2,500 queries, no card |
| `DATAJUD_API_KEY` | Official confirmation of a judicial process by its number (CNJ) | Public shared key published at the [DataJud wiki](https://datajud-wiki.cnj.jus.br/api-publica/acesso/) — no personal signup needed |
| `PORTAL_TRANSPARENCIA_API_KEY` | Official PEP (Politically Exposed Person) verification | Free email signup at [Portal da Transparência](https://www.portaldatransparencia.gov.br/api-de-dados/cadastrar-email) |

[`.env.example`](https://github.com/CalebePrates/company-investigator-mcp/blob/main/.env.example) lists them. The server does not auto-load `.env`
files: pass the variables through your MCP client's `env` block (below) or export
them in the shell that launches the server.

## MCP client configuration

### Claude Desktop / generic `mcpServers` JSON

Most clients (Claude Desktop's `claude_desktop_config.json`, Cursor, Windsurf,
…) accept this shape. With **uvx**:

```json
{
  "mcpServers": {
    "company-investigator": {
      "command": "uvx",
      "args": ["company-investigator-mcp"],
      "env": {
        "SEARCH_PROVIDER": "serper",
        "SEARCH_API_KEY": "your-serper-key",
        "DATAJUD_API_KEY": "the-public-datajud-key",
        "PORTAL_TRANSPARENCIA_API_KEY": "your-cgu-key"
      }
    }
  }
}
```

With **npx**, replace the command:

```jsonc
"command": "npx",
"args": ["-y", "company-investigator-mcp"]
```

With **pip**, use `"command": "company-investigator-mcp"` (or its absolute path
inside your virtualenv) and no `args`. All `env` entries are optional.

If the client reports that `uvx` was not found, use its absolute path
(`which uvx` / `where uvx`) as `command`.

### Claude Code

```bash
claude mcp add company-investigator \
  -e SEARCH_PROVIDER=serper -e SEARCH_API_KEY=your-serper-key \
  -- uvx company-investigator-mcp
```

or add the JSON above to `.mcp.json` at your project root. Reload/reconnect the
MCP servers after changing the configuration or the variables.

### Windows + WSL

If the server runs inside WSL while the client runs on Windows:

```json
{
  "mcpServers": {
    "company-investigator": {
      "command": "wsl.exe",
      "args": ["-e", "bash", "-lc", "uvx company-investigator-mcp"]
    }
  }
}
```

`bash -lc` is a non-interactive login shell: export the API keys in `~/.profile`,
not `~/.bashrc` — Ubuntu's default `~/.bashrc` returns early for non-interactive
shells, so anything exported there is silently ignored.

## Tools

| Tool | Purpose |
|---|---|
| `ping` | Health check |
| `buscar_empresa(cnpj)` | Official registry data for one CNPJ |
| `buscar_informacoes_publicas(url)` | Title and visible text of a public web page (needs Chromium) |
| `investigar_empresa(identificador, profundidade=1)` | Full investigation; returns an `investigation_id` and an index |
| `obter_indice_investigacao(investigation_id)` | The index again (also for any related company's id) |
| `obter_secao_investigacao(investigation_id, secao, pagina=1, tamanho_pagina=20)` | One page (max 50 items) of a section |
| Resource `investigation://{investigation_id}/{secao}{?pagina,tamanho_pagina}` | Same as the two tools above, as an MCP Resource (`index` returns the index) |

Every tool self-describes its input schema, so the client discovers them via
`tools/list`. Invalid input (bad CNPJ check digits, malformed URL, unknown
section, page out of range, unknown or expired `investigation_id`) returns a
readable tool error.

### Examples

`ping`:

```jsonc
// input
{}
// output
{ "status": "ok", "message": "MCP funcionando" }
```

`buscar_empresa` — accepts the CNPJ with or without punctuation:

```jsonc
// input
{ "cnpj": "19.131.243/0001-97" }
// output
{
  "cnpj": "19131243000197",
  "razao_social": "OPEN KNOWLEDGE BRASIL",
  "nome_fantasia": "REDE PELO CONHECIMENTO LIVRE",
  "situacao": "ATIVA"
}
```

`buscar_informacoes_publicas`:

```jsonc
// input
{ "url": "https://example.com/" }
// output
{ "url": "https://example.com/", "titulo": "Example Domain", "texto": "Example Domain This domain is for use in ..." }
```

`investigar_empresa` — a CNPJ or a company name; `profundidade` is how many levels
of the corporate network to expand (default 1, max 2). An ambiguous name returns
`candidatos` instead of guessing. The answer is a small **index** (field names
exact, values illustrative):

```jsonc
// input
{ "identificador": "19.131.243/0001-97", "profundidade": 1 }
// output
{
  "investigation_id": "3f9c0d…",
  "identificador_usado": "19.131.243/0001-97",
  "empresa": { "cnpj": "...", "razao_social": "...", "situacao": "ATIVA" },
  "processos_status": { "status": "realizada", "motivo": null },
  "secoes": [
    { "nome": "socios", "tipo": "lista", "total_itens": 4 },
    { "nome": "noticias", "tipo": "lista", "total_itens": 45 },
    { "nome": "empresas_relacionadas", "tipo": "lista", "total_itens": 2 }
  ]
}
```

`obter_secao_investigacao` — read the content page by page:

```jsonc
// input
{ "investigation_id": "3f9c0d…", "secao": "noticias", "pagina": 1, "tamanho_pagina": 20 }
// output
{
  "secao": "noticias", "pagina": 1, "tamanho_pagina": 20,
  "total_itens": 45, "total_paginas": 3,
  "itens": [
    { "titulo": "...", "url": "https://...", "fonte": "...", "resumo": "...",
      "consultado_em": "...", "data_publicacao": null, "confianca": "media" }
  ]
}
```

### Reading a large investigation

A real investigation with a corporate network can run past 100,000 characters —
more than a single tool response should carry. So collection and delivery are
separate: the server keeps the complete result in memory and the client pulls it
in pages. Paging through every section listed in the index returns 100% of what
was collected.

Sections: `empresa`, `candidatos`, `socios`, `pessoas_chave`, `linkedin`,
`redes_sociais`, `noticias`, `contatos`, `processos_confirmados`,
`processos_referencias`, `processos_status`, `movimentos_processuais`, `fontes`,
`empresas_relacionadas`, `pessoas_relacionadas`, `relacionamentos`,
`possiveis_relacoes_familiares`, `peps`, `limitacoes`.

- **Related companies are references, not nested copies.** Each item of
  `empresas_relacionadas` holds the relationship (`origem_socio`, `fonte`,
  `confianca`) plus that company's own `investigation_id`; walk it recursively
  with the same tools. A company reached through several partners appears once,
  with one `socio_de` edge per partner.
- **A process's movements** (an old lawsuit can have thousands) live in
  `movimentos_processuais`, each item pointing back to its `numero_processo`;
  `processos_confirmados` only carries `total_movimentos`.
- **Memory only, no database.** The store lives in the server process, is capped
  at 500 records (the least recently used whole investigation tree is discarded
  first) and disappears when the server restarts. An unknown or expired
  `investigation_id` gets a clear error; just run `investigar_empresa` again.

## Sources and evidence

Every item preserves, when available: **source** (BrasilAPI, Serper, DataJud,
Portal da Transparência, LinkedIn via search), **URL**, **discovery date**
(`consultado_em`), **publication date**, **confidence** (`alta` / `media` /
`baixa` — how strong the match is, never a claim of certainty) and, for possible
family relationships, the **evidence** itself (a shared surname token, or the
snippet that mentioned a relationship explicitly).

Judicial proceedings separate `processos_confirmados` (official DataJud data,
retrieved by process number) from `processos_referencias` (a public mention, not
confirmed). No official, public, CAPTCHA-free source allows searching processes by
party (CNPJ/CPF/name), and DataJud never discloses parties — so confirming a
process number is not the same as confirming who is involved in it.

## Limitations and responsible use

This project:

- uses only publicly available information;
- never accesses private data;
- never bypasses CAPTCHA, anti-bot mechanisms, authentication, paywalls or rate
  limits;
- never treats a matching name as proof of identity;
- never treats a matching surname as proof of a family relationship — it is only
  ever a *possible* relationship, with low confidence unless a public source
  mentions an explicit kinship term;
- never interprets appearing in a judicial process as guilt or wrongdoing;
- treats PEP matches with explicit caution: a name match alone never becomes a
  confirmed PEP — that requires the visible digits of the partner's masked CPF to
  match the official record; otherwise the result is a possible homonym;
- never fabricates a fact when a source cannot verify it — it reports the
  limitation instead (`limitacoes`).

Known limitations: search-based discovery depends on what the search provider
indexes, so the corporate network and news coverage are not exhaustive; free API
tiers have quotas; data is only as current as each public source.

You are responsible for using the results lawfully, including under Brazil's
LGPD (Lei Geral de Proteção de Dados) and each source's terms of use. Results are
leads to verify, not conclusions.

## Architecture

Clean Architecture with an explicit Ports & Adapters boundary:

```text
MCP Client
    ↓
MCP Tools        (interface/mcp_server/tools — validate input, call a use case, shape output)
    ↓
Use Cases        (application/use_cases — orchestrate a single MCP-level operation)
    ↓
Services         (application/services — identification, partner/company/news/social/
                  LinkedIn/process/PEP/family-relationship search, investigation storage)
    ↓
Ports            (domain/ports — small ABCs: one capability each)
    ↓
Adapters         (infrastructure — concrete implementations of a port)
    ↓
External Sources (BrasilAPI, Serper, DataJud, Portal da Transparência, Playwright)
```

The dependency rule always points inward: `domain` depends on nothing external
(not even Pydantic); `application` depends only on `domain` abstractions;
`infrastructure` and `interface` depend on `domain`. Every external capability
sits behind a small port, so swapping Serper for another search provider means
writing one new adapter class. See [`CLAUDE.md`](https://github.com/CalebePrates/company-investigator-mcp/blob/main/CLAUDE.md) for the full
rationale and how each tool's flow works end to end.

```text
src/company_investigator/
├── domain/             # entities, value objects (Cnpj), ports
├── application/        # use cases and services
├── infrastructure/     # BrasilAPI, Playwright, Serper, DataJud, Portal da Transparência,
│                       # in-memory investigation store
└── interface/mcp_server/
    ├── server.py       # composition root
    ├── tools/          # the six MCP tools
    └── resources/      # investigation://{investigation_id}/{secao}
npm/                    # npx launcher (Node, no dependencies, no server logic)
```

## Development

```bash
uv sync
uv run pytest                 # test suite (no network, no browser, no paid API)
uv run ruff check .           # lint
uv run ruff format .          # format
(cd npm && npm test)          # npm launcher tests
uv build                      # sdist + wheel in dist/
```

Every behavior is written test-first. `tests/unit` covers domain and application
logic with fakes for every port; `tests/integration` exercises the real
`MCPServer` composition, including one test that launches the server as a child
process and talks to it over stdio with the official MCP client. CI runs all of
this on every push and pull request.

Release process and versioning policy: [RELEASING.md](https://github.com/CalebePrates/company-investigator-mcp/blob/main/RELEASING.md). Changes:
[CHANGELOG.md](https://github.com/CalebePrates/company-investigator-mcp/blob/main/CHANGELOG.md).

## Non-goals

- **Persistence** (database, cache, history). The only state is the in-memory
  investigation store, which lives and dies with the server process.
- **An LLM inside the server.** Analysis is the MCP client's / AI agent's job.

## License

[MIT](https://github.com/CalebePrates/company-investigator-mcp/blob/main/LICENSE) © Calebe Prates
