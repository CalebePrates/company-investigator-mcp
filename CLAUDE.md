# Company Investigator MCP

Projeto de aprendizado: construir um servidor MCP (Model Context Protocol) próprio,
do básico até um projeto pessoal em produção, usando Clean Architecture + SOLID e TDD.
Hoje é um servidor de inteligência pública sobre empresas: dados cadastrais, rede
societária, notícias, redes sociais, processos judiciais públicos e PEP.

**Nota sobre nomes:** o rename técnico foi concluído — pacote Python
(`src/company_investigator/`), nome em `pyproject.toml` (`company-investigator`,
normalizado pelo `uv_build` para `company_investigator` por convenção, sem precisar de
`[tool.uv.build-backend] module-name`), comando CLI (`uv run company-investigator`) e a
chave do servidor em `.mcp.json` (`company-investigator`) usam todos o novo nome. A
única coisa que **não** foi renomeada é a pasta raiz do repositório no disco
(`.../pessoal/mcp-project/`) — isso é o nome da pasta clonada localmente, não algo
pedido no rename, e trocá-lo exigiria mover o próprio diretório do projeto.

Sem persistência: não há banco de dados, cache persistente ou histórico neste
projeto (decisão explícita — ver "Fontes externas" abaixo para como cada tool lida
com a ausência de configuração em vez de guardar estado).

## Stack

- Python 3.14
- MCP Python SDK (`mcp`) — pacote `mcp.server.mcpserver.MCPServer` (equivalente ao antigo `FastMCP` na v1 do SDK)
- Pydantic — validação/modelagem de dados
- httpx — cliente HTTP assíncrono
- Playwright — automação de browser / scraping dinâmico
- BeautifulSoup4 + lxml — parsing de HTML
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
uv run company-investigator  # inicia o servidor MCP (stdio)
```

## Arquitetura

Clean Architecture em camadas, com regra de dependência sempre apontando para dentro
(infraestrutura e interface dependem do domínio; o domínio não depende de nada externo,
nem de bibliotecas de terceiros como Pydantic ou httpx).

```
src/company_investigator/
├── domain/
│   ├── entities/        # Company, Socio, PublicPageInfo, SearchResult,
│   │                     # investigation.py (todo o modelo de investigação: Noticia,
│   │                     # PerfilRedeSocial, PessoaChave, ReferenciaProcessual,
│   │                     # DadosOficiaisProcesso, ProcessoConfirmado, ConsultaProcessual,
│   │                     # Relacionamento, EmpresaRelacionada, PessoaRelacionada,
│   │                     # PossivelRelacaoFamiliar, StatusPEP, RegistroPEP, EmpresaInvestigada)
│   ├── value_objects/    # Cnpj (normalização + validação de dígitos verificadores)
│   └── ports/            # abstrações (ABCs): HealthCheckerPort, CompanyRepositoryPort,
│                          # BrowserPort, SearchProviderPort, ProcessNumberLookupPort,
│                          # PEPLookupPort
├── application/
│   ├── use_cases/        # PingUseCase, BuscarEmpresaUseCase,
│   │                      # BuscarInformacoesPublicasUseCase, InvestigarEmpresaUseCase
│   └── services/         # orquestradores especializados usados pelo InvestigarEmpresaUseCase:
│                          # CompanyDataService, CompanyIdentificationService,
│                          # PartnerSearchService, NewsSearchService,
│                          # SocialMediaSearchService, LinkedInSearchService,
│                          # ProcessSearchService, RelatedCompaniesService,
│                          # RelatedPeopleService, FamilyRelationshipService, PEPService
├── infrastructure/       # implementações concretas dos ports:
│   ├── health/            # SimpleHealthChecker
│   ├── company/http/      # BrasilApiCompanyRepository (BrasilAPI, CNPJ público)
│   ├── browser/           # PlaywrightBrowser + html_page_parser (bs4/lxml)
│   ├── search/            # SerperSearchAdapter + UnconfiguredSearchProvider
│   ├── process/           # DataJudProcessAdapter (API Pública do DataJud/CNJ)
│   └── pep/               # PortalTransparenciaPEPAdapter (API de Dados da CGU)
└── interface/
    └── mcp_server/
        ├── server.py      # composition root: monta o MCPServer e injeta dependências
        └── tools/         # cada tool MCP é um adapter fino: valida entrada (Pydantic),
                            # chama um use case, formata a saída (Pydantic) — nenhuma
                            # regra de negócio mora aqui
```

### Como os princípios SOLID aparecem aqui

- **SRP** — cada classe tem um único motivo para mudar: `HealthStatus` só modela o dado,
  `PingUseCase` só orquestra, `SimpleHealthChecker` só sabe checar saúde. O mesmo padrão
  se repete em cada tool: `ProcessSearchService` só sabe descobrir/confirmar processos,
  `PEPService` só decide o status de PEP a partir de um registro bruto.
- **OCP** — novas fontes podem ser adicionadas criando uma nova implementação de um port,
  sem alterar quem o usa (ex.: trocar `SerperSearchAdapter` por outro `SearchProviderPort`
  não muda nenhum service).
- **LSP** — qualquer implementação de um port (real ou fake em teste) pode substituir
  outra sem quebrar quem depende dele.
- **ISP** — os ports ficam pequenos e focados. Exemplo deliberado: `ProcessNumberLookupPort`
  só tem `find_by_number` — não existe (nem deveria existir) um `find_by_cnpj` nele, porque
  nenhuma fonte oficial e sem CAPTCHA disponível hoje permite buscar processos por parte
  (ver "Investigação de empresa" abaixo). Uma futura fonte com essa capacidade ganharia
  seu próprio port pequeno, em vez de inflar este.
- **DIP** — `application` depende só das abstrações em `domain.ports`, nunca de uma
  implementação concreta. A composição real acontece só no composition root
  (`interface/mcp_server/server.py`), incluindo os overrides opcionais usados pelos
  testes de integração (`company_repository=`, `browser=`, `search_provider=`,
  `process_number_lookup=`, `pep_lookup=`).

Ao adicionar uma nova feature, siga o mesmo padrão: entidade/valor em `domain`,
port se houver uma dependência externa, orquestração em `application` (use case ou
service), implementação em `infrastructure`, e um adapter fino em
`interface/mcp_server/tools` que apenas traduz entrada/saída da tool MCP.

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
  os ports (nunca dependências reais como banco, rede ou browser). Para HTTP, os testes de
  `infrastructure` usam `httpx.MockTransport` (nunca mocks internos da lib) para validar o
  adapter real contra respostas simuladas.
- `tests/integration/` — testam a composição real (`build_server()` + chamada da tool MCP
  via `MCPServer.call_tool`), injetando fakes pelos parâmetros opcionais de `build_server()`
  para nunca depender de rede, navegador ou cota de API paga.
- Testes assíncronos usam `pytest-asyncio` (modo `auto`, configurado em `pyproject.toml`
  — não é necessário decorar com `@pytest.mark.asyncio`, mas os testes atuais o fazem
  explicitamente por clareza).

## Tools disponíveis

### `ping`

Tool mínima para validar a instalação. Retorna sempre
`{"status": "ok", "message": "MCP funcionando"}`.
Fluxo: `ping_tool.py` → `PingUseCase` → `HealthCheckerPort` → `SimpleHealthChecker`.

### `buscar_empresa(cnpj)`

Recebe um CNPJ (com ou sem pontuação), normaliza e valida (incluindo os dígitos
verificadores — ver `domain/value_objects/cnpj.py`), e retorna dados cadastrais reais
via BrasilAPI: razão social, nome fantasia, situação cadastral, endereço e sócios (QSA).
Fluxo: `buscar_empresa_tool.py` → `BuscarEmpresaUseCase` → `CompanyRepositoryPort` →
`BrasilApiCompanyRepository`.

### `buscar_informacoes_publicas(url)`

Abre uma URL pública com Playwright (headless), extrai título e texto visível com
BeautifulSoup/lxml. Fluxo: `buscar_informacoes_publicas_tool.py` →
`BuscarInformacoesPublicasUseCase` → `BrowserPort` → `PlaywrightBrowser`.

### `investigar_empresa(identificador, profundidade=1)`

A tool mais complexa do projeto: recebe um CNPJ ou nome de empresa e monta um dossiê
público combinando várias fontes. Ver a seção dedicada abaixo.

## Investigação de empresa (`investigar_empresa`)

`InvestigarEmpresaUseCase` orquestra, para a empresa identificada:

1. **Identificação** (`CompanyIdentificationService`): CNPJ vai direto à BrasilAPI; nome é
   pesquisado via `SearchProviderPort` para achar CNPJs candidatos, que são confirmados na
   BrasilAPI antes de virarem uma correspondência real. Nome ambíguo → retorna `candidatos`
   em vez de adivinhar.
2. **Sócios, LinkedIn, notícias, redes sociais** — services dedicados, cada um só falando
   com o `SearchProviderPort` (hoje: Serper, real wrapper do Google Search — ver
   `infrastructure/search/serper_search_adapter.py`).
3. **Processos judiciais** (`ProcessSearchService`): não existe fonte oficial, pública e
   sem CAPTCHA para buscar processos por CNPJ/CPF/nome de parte (todas as consultas
   públicas por parte nos tribunais — PJe, e-SAJ — exigem CAPTCHA; o Jus.br exige login
   gov.br; a API Pública do DataJud não indexa partes, por desenho). Por isso o fluxo é:
   `SearchProviderPort` descobre **referências** (menções públicas, possivelmente com um
   número de processo no texto) → `ProcessNumberLookupPort`
   (`DataJudProcessAdapter`) confirma por **número** contra a fonte oficial (CNJ). O
   resultado sempre separa `ConsultaProcessual.confirmados` (dados oficiais do DataJud)
   de `ConsultaProcessual.referencias` (menção pública, não confirmada) — a confiança da
   associação sempre vem da referência de origem, nunca do DataJud, que não expõe partes.
4. **Rede societária** (`RelatedCompaniesService` + `RelatedPeopleService`): para cada
   sócio, descobre outras empresas via `SearchProviderPort` + confirmação na BrasilAPI (não
   existe API gratuita de "empresas por sócio" sem baixar toda a base da Receita Federal).
   Expande até `profundidade` níveis (padrão 1, máximo 2), reutilizando recursivamente o
   próprio `InvestigarEmpresaUseCase._investigate` para cada empresa relacionada. Um
   conjunto `visited` (CNPJs) é propagado por toda a recursão para nunca repetir uma
   empresa nem entrar em ciclo. Empresa compartilhada por dois sócios aparece **uma vez**
   em `empresas_relacionadas`, com uma aresta `Relacionamento` por sócio.
5. **Possíveis relações familiares** (`FamilyRelationshipService`): sobrenome em comum
   (comparando todos os tokens do nome, não só o último — nomes brasileiros empilham
   sobrenomes) nunca vira uma afirmação de parentesco, só `PossivelRelacaoFamiliar` com
   confiança baixa. Só sobe de confiança quando uma fonte pública menciona um termo de
   parentesco explícito perto dos dois nomes — e mesmo assim continua sendo uma
   possibilidade, com a fonte preservada para checagem.
6. **PEP** (`PEPService` + `PortalTransparenciaPEPAdapter`): verifica cada sócio no
   cadastro oficial de Pessoas Expostas Politicamente (API de Dados do Portal da
   Transparência/CGU). Um nome batendo sozinho nunca vira `PEP_CONFIRMADA` — isso exige
   que os dígitos visíveis do CPF mascarado do sócio (já veio da BrasilAPI) batam com os
   do registro oficial; caso contrário fica `POSSIVEL_HOMONIMO`.

Qualquer falha de uma fonte (timeout, erro HTTP, chave ausente) não derruba a
investigação inteira — fica registrada em `limitacoes` (ou, para processos, no próprio
`ConsultaProcessual.status`/`motivo`) e as demais seções continuam disponíveis.

## Fontes externas e variáveis de ambiente

Nenhuma chave é obrigatória para o servidor subir — `ping` e `buscar_empresa` nunca
dependem delas; sem elas, as partes de `investigar_empresa` que dependem de busca/PEP/
processos ficam com resultado vazio + motivo explicado, em vez de falhar.

| Variável | Fonte | Onde conseguir |
|---|---|---|
| `SEARCH_API_KEY` (+ `SEARCH_PROVIDER=serper`) | Serper.dev (wrapper do Google Search) | Cadastro gratuito em serper.dev/api-key (2.500 buscas grátis, sem cartão) |
| `DATAJUD_API_KEY` | API Pública do DataJud (CNJ) | Chave **pública compartilhada**, publicada em datajud-wiki.cnj.jus.br/api-publica/acesso — não precisa de cadastro pessoal |
| `PORTAL_TRANSPARENCIA_API_KEY` | API de Dados do Portal da Transparência (CGU) | Cadastro gratuito por e-mail em portaldatransparencia.gov.br/api-de-dados/cadastrar-email |

**Importante (específico deste projeto):** o servidor é lançado via `.mcp.json` como
`wsl.exe -e bash -lc "... uv run company-investigator"`. Esse `bash -lc` é um shell de login
**não-interativo**, e o `~/.bashrc` padrão do Ubuntu tem uma guarda que sai fora antes de
rodar qualquer `export` quando o shell não é interativo — variáveis exportadas lá **não**
chegam ao processo do servidor. Configure as variáveis em `~/.profile` (sem essa guarda),
não em `~/.bashrc`, e recarregue o Claude Code / reconecte os servidores MCP depois.

## Conectando ao Claude Code

O arquivo `.mcp.json` na raiz já registra este servidor (nome `company-investigator`),
invocando-o via WSL (`wsl.exe -e bash -lc "cd ... && uv run company-investigator"`). Após
editar `.mcp.json` ou
alterar variáveis de ambiente usadas pelo servidor (ver seção acima), é necessário
reiniciar/recarregar o Claude Code para as mudanças valerem na conversa.
