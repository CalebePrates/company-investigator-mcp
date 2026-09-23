# mcp-project

Projeto de aprendizado: construir um servidor MCP (Model Context Protocol) próprio,
do básico até um projeto pessoal em produção, usando Clean Architecture + SOLID e TDD.

## Stack

- Python 3.14
- MCP Python SDK (`mcp`) — pacote `mcp.server.mcpserver.MCPServer` (equivalente ao antigo `FastMCP` na v1 do SDK)
- Pydantic — validação/modelagem de dados
- httpx — cliente HTTP assíncrono
- Playwright — automação de browser / scraping dinâmico
- BeautifulSoup4 + lxml — parsing de HTML
- SQLAlchemy + PostgreSQL (driver `psycopg`) — persistência
- pytest + pytest-asyncio — testes
- Ruff — lint e formatação
- uv — gerenciador de pacotes/ambiente/execução

## Gerenciamento do projeto

Tudo passa pelo `uv`, executado dentro do WSL (Ubuntu):

```bash
uv sync                 # instala/atualiza dependências
uv add <pacote>          # adiciona dependência de runtime
uv add --dev <pacote>     # adiciona dependência de desenvolvimento
uv run pytest             # roda a suíte de testes
uv run ruff check .       # lint
uv run ruff format .      # formatação
uv run mcp-project        # inicia o servidor MCP (stdio)
```

## Arquitetura

Clean Architecture em camadas, com regra de dependência sempre apontando para dentro
(infraestrutura e interface dependem do domínio; o domínio não depende de nada externo).

```
src/mcp_project/
├── domain/            # regras de negócio puras, sem dependências externas
│   ├── entities/       # objetos de valor / entidades (ex.: HealthStatus)
│   └── ports/           # interfaces (ABCs) que a camada de aplicação usa (DIP)
├── application/        # casos de uso, orquestram regras de domínio via ports
│   └── use_cases/
├── infrastructure/      # implementações concretas dos ports (DB, HTTP, scraping...)
└── interface/           # adapta o mundo externo (MCP) para os casos de uso
    └── mcp_server/
        ├── server.py     # composition root: monta o MCPServer e injeta dependências
        └── tools/         # cada tool MCP é um adapter fino que chama um use case
```

### Como os princípios SOLID aparecem aqui

- **SRP** — cada classe tem um único motivo para mudar: `HealthStatus` só modela o dado,
  `PingUseCase` só orquestra, `SimpleHealthChecker` só sabe checar saúde.
- **OCP** — novas verificações de saúde (ex.: checar banco, checar API externa) podem
  ser adicionadas criando uma nova implementação de `HealthCheckerPort`, sem alterar
  `PingUseCase`.
- **LSP** — qualquer implementação de `HealthCheckerPort` (real ou fake em teste) pode
  substituir outra sem quebrar `PingUseCase`.
- **ISP** — os ports ficam pequenos e focados (um método cada), evitando interfaces
  "gordas" que forçam implementações a depender de métodos que não usam.
- **DIP** — `application` depende da abstração `domain.ports.HealthCheckerPort`, nunca
  de uma implementação concreta. A composição real acontece só no composition root
  (`interface/mcp_server/server.py`).

Ao adicionar uma nova feature, siga o mesmo padrão: entidade/valor em `domain`,
port se houver uma dependência externa, caso de uso em `application`, implementação em
`infrastructure`, e um adapter fino em `interface/mcp_server/tools` que apenas traduz
entrada/saída da tool MCP para o caso de uso.

## TDD

Todo comportamento novo nasce de um teste que falha primeiro:

1. **Red** — escreva o teste (unitário em `tests/unit`, de integração em `tests/integration`)
   descrevendo o comportamento esperado. Rode `uv run pytest` e confirme que falha.
2. **Green** — escreva o mínimo de código em `domain`/`application`/`infrastructure`/`interface`
   para o teste passar.
3. **Refactor** — limpe a implementação mantendo os testes verdes, sempre respeitando
   as camadas (nada em `domain` deve importar `application`, `infrastructure` ou `interface`).

Convenções de teste:

- `tests/unit/` — testam `domain` e `application` isoladamente, usando fakes/stubs para
  os ports (nunca dependências reais como banco, rede ou browser).
- `tests/integration/` — testam a composição real (ex.: `build_server()` + chamada da
  tool MCP via `MCPServer.call_tool`).
- Testes assíncronos usam `pytest-asyncio` (modo `auto`, configurado em `pyproject.toml`
  — não é necessário decorar com `@pytest.mark.asyncio`, mas os testes atuais o fazem
  explicitamente por clareza).

## Tool de exemplo: `ping`

Tool mínima para validar a instalação. Retorna sempre:

```json
{
  "status": "ok",
  "message": "MCP funcionando"
}
```

Fluxo: `interface/mcp_server/tools/ping_tool.py` (adapter MCP) → `application/use_cases/ping_use_case.py`
(caso de uso) → `domain/ports/health_checker.py` (abstração) → `infrastructure/health/simple_health_checker.py`
(implementação real usada em produção).

## Conectando ao Claude Code

O arquivo `.mcp.json` na raiz já registra este servidor (nome `mcp-project`), invocando-o
via WSL (`wsl.exe -e bash -lc "cd ... && uv run mcp-project"`). Após editar `.mcp.json`,
é necessário reiniciar/recarregar o Claude Code para a tool `ping` ficar disponível na
conversa.
