# Company Investigator MCP

MCP server for public company intelligence, corporate relationships
and evidence-based investigation.

![Python](https://img.shields.io/badge/python-3.14%2B-blue)
![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-6E56CF)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)
![License](https://img.shields.io/badge/license-not%20defined-lightgrey)

An [MCP](https://modelcontextprotocol.io) server that lets an LLM client (Claude,
or any other MCP-compatible client) look up a Brazilian company by CNPJ or name,
walk its corporate network, and pull together public evidence — official
registry data, corporate relationships, news, social/LinkedIn profiles, public
judicial proceedings and Politically Exposed Person (PEP) checks — into one
structured, source-attributed result.

## Installation

```bash
git clone git@github.com:CalebePrates/company-investigator-mcp.git
cd company-investigator-mcp
uv sync
```

Requires Python 3.14+ and [`uv`](https://docs.astral.sh/uv/). Playwright also needs
its browser binary installed once:

```bash
uv run playwright install chromium
```

## Configuration

`.env.example` lists the variables the server reads. Use it as a checklist for
the keys you want to set (the real `.env` is git-ignored, so keys never get
committed):

```dotenv
# .env.example
SEARCH_PROVIDER=serper
SEARCH_API_KEY=
DATAJUD_API_KEY=
PORTAL_TRANSPARENCIA_API_KEY=
```

None of these are required to start the server — `ping` and `buscar_empresa` never
depend on them. Without a key, the parts of `investigar_empresa` that need it
(search discovery, official process confirmation, PEP checks) simply return an
empty result with an explanation instead of failing.

| Variable | Enables | Where to get it |
|---|---|---|
| `SEARCH_API_KEY` (+ `SEARCH_PROVIDER=serper`) | News, social profiles, LinkedIn, corporate network discovery | Free tier at [serper.dev](https://serper.dev) — 2,500 queries, no card |
| `DATAJUD_API_KEY` | Official confirmation of a judicial process by its number (CNJ) | Public shared key published at the [DataJud wiki](https://datajud-wiki.cnj.jus.br/api-publica/acesso/) — no personal signup needed |
| `PORTAL_TRANSPARENCIA_API_KEY` | Official PEP (Politically Exposed Person) verification | Free email signup at [Portal da Transparência](https://www.portaldatransparencia.gov.br/api-de-dados/cadastrar-email) |

This project does not auto-load `.env` files — export the variables in the shell
that actually launches the server (e.g. `export SEARCH_API_KEY=...`, or
`set -a; source .env; set +a` if you keep them in a local `.env`). If that shell is a WSL login shell invoked
non-interactively (as in the `.mcp.json` example below), put the exports in
`~/.profile`, not `~/.bashrc` — Ubuntu's default `~/.bashrc` returns early for
non-interactive shells, so anything exported there is silently ignored.

### Adding it to Claude Code

Register the server in `.mcp.json` at your project root:

```json
{
  "mcpServers": {
    "company-investigator": {
      "command": "wsl.exe",
      "args": ["-e", "bash", "-lc", "cd /path/to/company-investigator-mcp && uv run company-investigator"]
    }
  }
}
```

(This example targets Windows+WSL, matching how this project is developed. On
Linux/macOS, drop the `wsl.exe`/`bash -lc` wrapper and run
`cd /path/to/company-investigator-mcp && uv run company-investigator` directly as
the `command`. `/path/to/company-investigator-mcp` is just the folder you cloned
into — the installed Python package inside it is `company_investigator`.)
Reload Claude Code after editing `.mcp.json` or changing environment variables the
server reads.

## What is Company Investigator MCP?

Looking up a company usually means checking half a dozen disconnected sources by
hand — a registry lookup, a news search, a LinkedIn search, maybe a court records
site — and manually piecing together who actually runs it and what else they're
involved in. This project turns that into one MCP tool call with a single
underlying idea:

```text
Company/CNPJ
      ↓
Partners
      ↓
Related companies
      ↓
Related people
      ↓
News / LinkedIn / public profiles
      ↓
Public proceedings
      ↓
PEP
      ↓
Relationship graph
      ↓
Structured investigation (read in pages by the client)
```

The server **collects and structures** the evidence; it does not interpret it.
Deciding what to dig into, cross-checking sources and writing the final analysis
is the job of the MCP client / AI agent (Claude, a local Qwen, …):

```text
MCP Client / AI Agent → Company Investigator MCP → structured investigation
                      → MCP Client / AI Agent → analysis
```

There is deliberately no LLM inside this server (see [Roadmap](#roadmap)).

## Features

- **Company intelligence** — official registry data (CNPJ, razão social, nome
  fantasia, status, address) via BrasilAPI.
- **Corporate relationships** — discovers other companies a partner is
  associated with, and expands the network to a configurable depth.
- **People intelligence** — partners, administrators and LinkedIn key people
  (CEO, founders, directors and other leadership roles) for every company found.
- **News and public sources** — public mentions of the company via a search
  provider, each with title, URL, source and confidence.
- **LinkedIn / social profiles** — company page and key people on LinkedIn, plus
  Instagram, Facebook, YouTube, X/Twitter and TikTok.
- **Public proceedings** — public mentions of judicial processes, with official
  confirmation by process number where possible (never a direct party search on
  the official source — see [Sources and Evidence](#sources-and-evidence)).
- **PEP identification** — checks partners against the official Politically
  Exposed Person registry, distinguishing a confirmed match from a same-name
  coincidence.
- **Relationship graph** — companies and people connected by typed, sourced
  edges (`socio_de`, `relacionada_por_socio`), without duplicating entities.
- **Large investigations without blowing the client's context** — the full result
  is kept in the server's memory and handed over as a small index plus paginated
  sections (see [Reading a large investigation](#reading-a-large-investigation)).
  Nothing is truncated: paging through every section returns 100% of what was
  collected.

## Example

```text
Tool: buscar_empresa
Input: { "cnpj": "19.131.243/0001-97" }
```

```json
{
  "cnpj": "19131243000197",
  "razao_social": "OPEN KNOWLEDGE BRASIL",
  "nome_fantasia": "REDE PELO CONHECIMENTO LIVRE",
  "situacao": "ATIVA"
}
```

`investigar_empresa` runs the whole investigation, but answers with a small
**index** — an `investigation_id` plus how many items each section holds
(abbreviated; field names are exact, values illustrative):

```text
Tool: investigar_empresa
Input: { "identificador": "<CNPJ or company name>", "profundidade": 1 }
```

```json
{
  "investigation_id": "3f9c0d…",
  "identificador_usado": "<the identifier you passed>",
  "empresa": { "cnpj": "...", "razao_social": "...", "situacao": "ATIVA" },
  "processos_status": { "status": "realizada", "motivo": null },
  "secoes": [
    { "nome": "socios", "tipo": "lista", "total_itens": 4 },
    { "nome": "noticias", "tipo": "lista", "total_itens": 20 },
    { "nome": "empresas_relacionadas", "tipo": "lista", "total_itens": 2 }
  ]
}
```

The content itself is read section by section (see the next section).

## Reading a large investigation

A real investigation with a corporate network can run past 100,000 characters —
more than a single tool response should carry. So collection and delivery are
separate: the server keeps the complete result in memory and the client pulls it
in pages.

| Access | What it returns |
|---|---|
| Tool `obter_indice_investigacao(investigation_id)` | The index again (also works for any related company's own id) |
| Tool `obter_secao_investigacao(investigation_id, secao, pagina=1, tamanho_pagina=20)` | One page (max 50 items) of a section |
| Resource `investigation://{investigation_id}/{secao}{?pagina,tamanho_pagina}` | The same, as an MCP Resource (`index` returns the index) |

Both are exposed because not every MCP client wires up Resources; they share the
same code path and return identical pages.

```json
{
  "secao": "noticias", "pagina": 1, "tamanho_pagina": 20,
  "total_itens": 45, "total_paginas": 3,
  "itens": [ { "titulo": "...", "url": "https://...", "fonte": "serper",
               "consultado_em": "...", "confianca": "media" } ]
}
```

Sections: `empresa`, `candidatos`, `socios`, `pessoas_chave`, `linkedin`,
`redes_sociais`, `noticias`, `contatos`, `processos_confirmados`,
`processos_referencias`, `processos_status`, `movimentos_processuais`, `fontes`,
`empresas_relacionadas`, `pessoas_relacionadas`, `relacionamentos`,
`possiveis_relacoes_familiares`, `peps`, `limitacoes`.

- **Related companies are references, not nested copies.** Each item of
  `empresas_relacionadas` holds the relationship (`origem_socio`, `fonte`,
  `confianca`) plus that company's own `investigation_id`; walk it recursively
  with the same tools. A company reached through several paths appears once.
- **Nothing is dropped.** No `[:N]` truncation anywhere; every page keeps its
  source, URL, discovery date and confidence.
- **A process's movements** (an old lawsuit can have thousands) live in
  `movimentos_processuais`, each item pointing back to its `numero_processo`;
  `processos_confirmados` only carries `total_movimentos`.
- **Memory only, no database.** The store lives in the server process, is capped
  (oldest whole investigation tree is discarded first) and disappears when the
  server restarts. An unknown or expired `investigation_id` gets a clear error;
  just run `investigar_empresa` again.

## Investigation Graph

Companies and people are nodes; how they connect is an explicit, typed,
sourced edge — never an assumption:

```text
Company A
└── Partner X
    ├── socio_de ────────► Company B  (found via public search, confirmed via BrasilAPI)
    │                        └── relacionada_por_socio ─► Company A
    └── socio_de ────────► Company C
                             └── relacionada_por_socio ─► Company A
```

The same company reached through two different partners still appears **once**
in `empresas_relacionadas` — with two separate `socio_de` edges pointing to it —
never as two duplicate entities.

## Architecture

Clean Architecture with an explicit Ports & Adapters boundary:

```text
MCP Client
    ↓
MCP Tools        (interface/mcp_server/tools — validate input, call a use case, shape output)
    ↓
Use Cases        (application/use_cases — orchestrate a single MCP-level operation)
    ↓
Services         (application/services — focused sub-orchestrators: identification,
                  partner/company/news/social/LinkedIn/process/PEP/family-relationship search)
    ↓
Ports            (domain/ports — small ABCs: one capability each)
    ↓
Adapters         (infrastructure — concrete implementations of a port)
    ↓
External Sources (BrasilAPI, Serper, DataJud, Portal da Transparência, Playwright)
```

The dependency rule always points inward: `domain` depends on nothing external
(not even Pydantic); `application` depends only on `domain` abstractions;
`infrastructure` and `interface` depend on `domain` but never on each other.
Every external capability sits behind a small port (Interface Segregation:
`ProcessNumberLookupPort` only has `find_by_number` — there is deliberately no
`find_by_cnpj` on it, because no CAPTCHA-free official source offers that).
This is what makes it possible to swap Serper for another search provider by
writing one new adapter class — no use case or service changes. The same applies
to the in-memory investigation store: it sits behind `InvestigationStorePort`.

TDD drives every behavior: a failing test is written first (`tests/unit` with
fakes for every port, `tests/integration` exercising the real `MCPServer`
composition), then the minimum code to pass it, then refactor with the suite
green.

## Why MCP?

An LLM client needs to know what a tool does, what it takes and what it
returns, without custom integration code per client. MCP standardizes exactly
that: each tool here (`ping`, `buscar_empresa`, `buscar_informacoes_publicas`,
`investigar_empresa`, `obter_indice_investigacao`, `obter_secao_investigacao`)
self-describes its schema, so any MCP-compatible client can discover and call
it directly — nothing in it is specific to one client. A plain REST API or a one-off scraper script
would need bespoke glue for every consumer; an MCP server needs it once.

## Sources and Evidence

Every piece of information returned preserves, when available:

- **source** — which system produced it (BrasilAPI, Serper, DataJud, Portal da
  Transparência, LinkedIn via search).
- **URL** — a link back to where it was found.
- **discovery date** (`consultado_em`) — when this server queried it.
- **publication date**, when the source provides one.
- **confidence** (`alta` / `media` / `baixa`) — how strong the match is, never a
  claim of certainty.
- **evidence** — for possible family relationships, the actual signal (a shared
  surname token, or the snippet that mentioned a relationship explicitly).

Judicial proceedings specifically separate the `processos_confirmados` section
(official DataJud data, retrieved by process number) from `processos_referencias`
(a public mention, not yet confirmed) — because the official source never
discloses parties, confirming a process number is not the same as confirming
who is involved in it.

## Limitations and responsible use

This project:

- uses only publicly available information;
- never accesses private data;
- never bypasses CAPTCHA, authentication, paywalls or rate limits;
- never treats a matching name as proof of identity;
- never treats a matching surname as proof of a family relationship;
- never interprets appearing in a judicial process as guilt or wrongdoing;
- treats PEP matches and homonyms with explicit caution (a name match alone
  never becomes a confirmed PEP result);
- never fabricates a fact when a source cannot verify it — it reports the
  limitation instead.

## Development

```bash
uv run pytest          # run the test suite
uv run ruff check .    # lint
uv run ruff format .   # format
```

Tests are split into `tests/unit` (domain and application logic, isolated with
fakes for every port — no network, no browser) and `tests/integration`
(the real `MCPServer` composition, calling tools and reading resources in
process, with external sources swapped for fakes via `build_server()`'s optional
parameters). One integration test goes further: it launches the server as a real
child process and talks to it over stdio with the official MCP client, the same
path a desktop client uses.

## Project structure

```text
src/company_investigator/
├── domain/
│   ├── entities/        # Company, Socio, investigation.py (the full result model)
│   ├── value_objects/    # Cnpj (normalization + check-digit validation)
│   └── ports/             # HealthCheckerPort, CompanyRepositoryPort, BrowserPort,
│                           # SearchProviderPort, ProcessNumberLookupPort, PEPLookupPort,
│                           # InvestigationStorePort
├── application/
│   ├── use_cases/        # PingUseCase, BuscarEmpresaUseCase,
│   │                       # BuscarInformacoesPublicasUseCase, InvestigarEmpresaUseCase
│   └── services/          # CompanyIdentificationService, PartnerSearchService,
│                           # NewsSearchService, SocialMediaSearchService,
│                           # LinkedInSearchService, ProcessSearchService,
│                           # RelatedCompaniesService, RelatedPeopleService,
│                           # FamilyRelationshipService, PEPService,
│                           # InvestigationStorageService (index + paginated sections)
├── infrastructure/       # BrasilApiCompanyRepository, PlaywrightBrowser,
│                          # SerperSearchAdapter, DataJudProcessAdapter,
│                          # PortalTransparenciaPEPAdapter, InMemoryInvestigationStore
└── interface/mcp_server/
    ├── server.py          # composition root
    ├── tools/             # ping, buscar_empresa, buscar_informacoes_publicas,
    │                       # investigar_empresa, obter_indice_investigacao,
    │                       # obter_secao_investigacao
    └── resources/         # investigation://{investigation_id}/{secao}
```

See [`CLAUDE.md`](CLAUDE.md) for the full architectural rationale and how each
tool's flow works end to end.

## Roadmap

The project is feature-complete for its intended scope; nothing new is planned.
Two things are deliberate non-goals:

- **Persistence** (database, cache, history). The only state is the in-memory
  investigation store, which lives and dies with the server process.
- **An LLM inside the server.** Analysis is the MCP client's / AI agent's job:
  it chooses which tools to call, which sections to read in full, cross-checks
  the evidence and writes the conclusion. The server's job is to hand it complete,
  source-attributed data — every section retrievable, nothing summarized away.

## License

No license has been chosen for this project yet.
