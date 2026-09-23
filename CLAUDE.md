# Company Investigator MCP

Projeto de aprendizado: construir um servidor MCP (Model Context Protocol) próprio,
do básico até um projeto pessoal em produção, usando Clean Architecture + SOLID e TDD.
Hoje é um servidor de inteligência pública sobre empresas: dados cadastrais, rede
societária, notícias, redes sociais, processos judiciais públicos e PEP.

**Nota sobre nomes:** a distribuição publicada (PyPI e npm) se chama
`company-investigator-mcp`; o pacote importável continua `company_investigator`
(`src/company_investigator/`) — por isso o `pyproject.toml` declara
`[tool.uv.build-backend] module-name = "company_investigator"` (sem isso o `uv_build`
procuraria `company_investigator_mcp`). Comandos de console: `company-investigator-mcp`
(principal, é o que o `uvx` executa) e `company-investigator` (alias mantido). A chave
do servidor em `.mcp.json` é `company-investigator`. O
repositório GitHub também já existe com o nome novo:
[`CalebePrates/company-investigator-mcp`](https://github.com/CalebePrates/company-investigator-mcp).
A única coisa que **não** foi renomeada é a pasta de desenvolvimento local dentro do
WSL (`.../pessoal/mcp-project/`) — é só o nome da pasta neste ambiente específico;
alguém clonando o repositório do zero já recebe a pasta `company-investigator-mcp/`.

Sem persistência: não há banco de dados, cache persistente ou histórico neste
projeto (decisão explícita — ver "Fontes externas" abaixo para como cada tool lida
com a ausência de configuração em vez de guardar estado). A única exceção é um
armazenamento **em memória, só pelo tempo de vida do processo do servidor**, que
guarda o resultado de uma investigação para ser lido em partes (ver "Exposição em
partes" abaixo) — nada é gravado em disco.

## Papel do MCP vs. papel do agente cliente

Decisão de arquitetura (definitiva): **a análise fica com o cliente**, não com este
servidor.

```
MCP Client / AI Agent → Company Investigator MCP → investigação e dados estruturados
                      → MCP Client / AI Agent → análise
```

- **Este MCP** coleta informação pública, investiga empresas, descobre sócios,
  pessoas e empresas relacionadas, busca notícias/LinkedIn/redes sociais, consulta
  processos e PEP, preserva evidências/fontes/URLs/datas/confiança e disponibiliza
  tudo de forma estruturada, permitindo que o agente leia investigações grandes sem
  estourar o contexto.
- **O agente** (Claude, Qwen local etc.) decide quais tools usar, o que aprofundar,
  cruza as evidências, interpreta e produz a análise final.
- **Não existe** (e não deve ser criado) LLM interno, `LLMProvider`,
  `LLMAnalysisService` nem tool `analisar_empresa` neste projeto.

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
uv run company-investigator-mcp            # inicia o servidor MCP (stdio)
uv run company-investigator-mcp --version  # imprime a versão e sai
(cd npm && npm test)                       # testes do launcher npm (node:test)
```

## Distribuição (v1.0.0+)

- **PyPI** `company-investigator-mcp` → `uvx company-investigator-mcp` /
  `pip install company-investigator-mcp`.
- **npm** `company-investigator-mcp` (pasta `npm/`) → `npx company-investigator-mcp`.
  É **só um launcher** em Node puro, sem dependências: acha o `uvx` e executa
  `uvx company-investigator-mcp@<versão do package.json>`, herdando stdio/env e
  devolvendo o exit code. Nenhuma lógica do MCP mora lá, e nunca deve morar; o
  launcher nunca escreve no stdout (é do protocolo MCP).
- **Versão:** fonte única do lado Python é o `version` do `pyproject.toml`
  (`company_investigator/version.py` lê dos metadados instalados; `--version` e o
  `serverInfo.version` do MCP usam isso). O `npm/package.json` precisa ter o mesmo
  número — `tests/unit/test_release_consistency.py` garante. npm X.Y.Z sempre roda
  PyPI X.Y.Z (nunca `@latest`); publicar PyPI antes do npm. Passo a passo em
  `RELEASING.md`.
- **Chromium não é baixado na instalação** (decisão explícita: sem efeitos
  colaterais/downloads grandes). `PlaywrightBrowser` detecta o binário ausente e
  devolve um `BrowserError` com o comando exato para instalar.

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
│                          # PEPLookupPort, InvestigationStorePort
├── application/
│   ├── use_cases/        # PingUseCase, BuscarEmpresaUseCase,
│   │                      # BuscarInformacoesPublicasUseCase, InvestigarEmpresaUseCase
│   └── services/         # orquestradores especializados usados pelo InvestigarEmpresaUseCase:
│                          # CompanyDataService, CompanyIdentificationService,
│                          # PartnerSearchService, NewsSearchService,
│                          # SocialMediaSearchService, LinkedInSearchService,
│                          # ProcessSearchService, RelatedCompaniesService,
│                          # RelatedPeopleService, FamilyRelationshipService, PEPService;
│                          # e InvestigationStorageService (guarda a investigação e a
│                          # entrega em índice + seções paginadas)
├── infrastructure/       # implementações concretas dos ports:
│   ├── health/            # SimpleHealthChecker
│   ├── company/http/      # BrasilApiCompanyRepository (BrasilAPI, CNPJ público)
│   ├── browser/           # PlaywrightBrowser + html_page_parser (bs4/lxml)
│   ├── search/            # SerperSearchAdapter + UnconfiguredSearchProvider
│   ├── process/           # DataJudProcessAdapter (API Pública do DataJud/CNJ)
│   ├── pep/               # PortalTransparenciaPEPAdapter (API de Dados da CGU)
│   └── investigation/     # InMemoryInvestigationStore (memória do processo, limitada)
└── interface/
    └── mcp_server/
        ├── server.py      # composition root: monta o MCPServer e injeta dependências
        ├── tools/         # cada tool MCP é um adapter fino: valida entrada (Pydantic),
        │                   # chama um use case/service, formata a saída (Pydantic) —
        │                   # nenhuma regra de negócio mora aqui. Inclui
        │                   # investigation_retrieval_tool.py e os modelos de saída
        │                   # compartilhados em _investigation_output_models.py
        └── resources/     # investigation_resource.py (MCP Resource investigation://…)
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
  `process_number_lookup=`, `pep_lookup=`, `investigation_store=`).

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
  para nunca depender de rede, navegador ou cota de API paga. Exceção deliberada:
  `test_stdio_external_client.py` sobe o servidor real como processo filho e fala com ele
  por stdio com o cliente oficial do SDK (o mesmo caminho do `.mcp.json`), usando só
  caminhos que não tocam a rede.
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
via BrasilAPI: CNPJ, razão social, nome fantasia e situação cadastral (os sócios/QSA
aparecem na seção `socios` de `investigar_empresa`).
Fluxo: `buscar_empresa_tool.py` → `BuscarEmpresaUseCase` → `CompanyRepositoryPort` →
`BrasilApiCompanyRepository`.

### `buscar_informacoes_publicas(url)`

Abre uma URL pública com Playwright (headless), extrai título e texto visível com
BeautifulSoup/lxml. Fluxo: `buscar_informacoes_publicas_tool.py` →
`BuscarInformacoesPublicasUseCase` → `BrowserPort` → `PlaywrightBrowser`.

### `investigar_empresa(identificador, profundidade=1)`

A tool mais complexa do projeto: recebe um CNPJ ou nome de empresa e monta um dossiê
público combinando várias fontes. **Não devolve o dossiê inteiro**: devolve um
`investigation_id` + um índice pequeno (empresa, status de processos, contagem de itens
por seção); o conteúdo completo é lido com as tools abaixo. Ver as seções dedicadas.

### `obter_secao_investigacao(investigation_id, secao, pagina=1, tamanho_pagina=20)`

Devolve uma página (máx. 50 itens) de uma seção da investigação. Percorrendo todas as
páginas (`total_paginas`) de todas as seções listadas no índice, chega-se a 100% do que
foi coletado. Erros claros (`ToolError`) para id inexistente/expirado, seção inválida
(a mensagem lista as válidas) e paginação fora do intervalo.
Fluxo: `investigation_retrieval_tool.py` → `InvestigationStorageService` →
`InvestigationStorePort` → `InMemoryInvestigationStore`.

### `obter_indice_investigacao(investigation_id)`

Reconsulta o índice de uma investigação (ou de uma sub-investigação, usando o
`investigation_id` de um item de `empresas_relacionadas`).

### Resource `investigation://{investigation_id}/{secao}{?pagina,tamanho_pagina}`

Mesmo conteúdo das duas tools, como MCP Resource (`index` devolve o índice). Existe
para clientes que preferem Resources; as tools existem porque muitos clientes só
conectam `tools/list`+`tools/call` — daí a exposição dupla, sem lógica duplicada (ambos
chamam o mesmo `InvestigationStorageService`).

## Exposição em partes (por que `investigar_empresa` devolve um índice)

Uma investigação real com rede societária chegou a ~103.000 caracteres numa única
resposta e estourou o limite de tokens do cliente. Regras que resolvem isso sem perder
dado nenhum:

- **Coleta e exposição são separadas.** `InvestigarEmpresaUseCase` continua produzindo
  a `EmpresaInvestigada` completa; só a camada de interface a entrega em partes.
- **Grafo em vez de árvore aninhada.** Cada empresa relacionada é uma investigação
  própria, guardada com seu `investigation_id`. O item de `empresas_relacionadas`
  carrega o resumo da relação + esse id, nunca a sub-investigação embutida. Percorra
  recursivamente pelo id.
- **Nenhum item de lista viaja no índice** — só contagens. Nada é truncado (`[:N]`).
- **Movimentos processuais** (podem ser milhares por processo) ficam na seção própria
  `movimentos_processuais` (item = `numero_processo` + nome + data);
  `processos_confirmados[].dados` traz só `total_movimentos`. Não há duplicação.
- **Rastreabilidade preservada:** cada item mantém fonte, URL, `consultado_em`,
  confiança e origem/relacionamento — os modelos de saída são os mesmos de antes.
- **Armazenamento** (`InMemoryInvestigationStore`): memória do processo, limitada a 500
  registros, sem disco. O descarte é sempre de uma **árvore inteira** (a raiz menos
  recentemente usada com todas as suas sub-investigações; ler qualquer nó conta como
  usar a árvore; a árvore recém-guardada nunca é descartada). Um id descartado ou de
  outra sessão responde com erro claro — basta chamar `investigar_empresa` de novo.
  Reiniciar o servidor apaga tudo (por desenho: sem persistência).
- Seções válidas: `SECTION_NAMES` em `investigation_storage_service.py` é a fonte única
  (descrição das tools e testes derivam dela).

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
   empresa nem entrar em ciclo — todas as empresas irmãs encontradas num nível são
   reservadas em `visited` **antes** de recursar em qualquer uma (senão a sub-árvore de
   uma irmã investigaria outra irmã, que apareceria de novo depois; a ligação entre as
   duas continua registrada como `Relacionamento`). Empresa compartilhada por dois sócios aparece **uma vez**
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
`wsl.exe -e bash -lc "... uv run company-investigator"` (alias ainda válido). Esse `bash -lc` é um shell de login
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
