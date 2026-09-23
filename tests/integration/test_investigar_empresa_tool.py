import json
from datetime import UTC, datetime

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import DadosOficiaisProcesso, Movimento
from company_investigator.domain.entities.search_result import SearchResult
from company_investigator.domain.entities.socio import Socio
from company_investigator.domain.ports.company_repository import CompanyRepositoryPort
from company_investigator.domain.ports.pep_lookup import PEPLookupPort, RegistroPEPBruto
from company_investigator.domain.ports.process_lookup import ProcessNumberLookupPort
from company_investigator.domain.ports.search_provider import SearchProviderPort
from company_investigator.domain.value_objects.cnpj import Cnpj
from company_investigator.infrastructure.search.unconfigured_search_provider import (
    UnconfiguredSearchProvider,
)
from company_investigator.interface.mcp_server.server import build_server

# limite conservador para uma unica resposta de Tool (bem abaixo do que clientes MCP aceitam)
_LIMITE_RESPOSTA_CHARS = 60_000

_EMPRESA_EXEMPLO = Company(
    cnpj="11444777000161",
    razao_social="Empresa Exemplo LTDA",
    nome_fantasia="Empresa Exemplo",
    situacao="ATIVA",
    socios=[Socio(nome="Joana Silva", qualificacao="Socia-Administradora")],
)


class FakeCompanyRepository(CompanyRepositoryPort):
    def __init__(self, companies: dict[str, Company] | None = None) -> None:
        self._companies = companies or {}

    async def find_by_cnpj(self, cnpj: Cnpj) -> Company | None:
        return self._companies.get(cnpj.value)


class FakeSearchProvider(SearchProviderPort):
    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self._results = results or []

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        return self._results


def _server(companies: dict[str, Company], search_results: list[SearchResult] | None = None):
    return build_server(
        company_repository=FakeCompanyRepository(companies),
        search_provider=FakeSearchProvider(search_results),
    )


async def _secao(server, investigation_id: str, secao: str, **kwargs) -> dict:
    result = await server.call_tool(
        "obter_secao_investigacao",
        {"investigation_id": investigation_id, "secao": secao, **kwargs},
    )
    assert result.is_error is False
    return result.structured_content


@pytest.mark.asyncio
async def test_tool_is_registered_on_the_server() -> None:
    server = _server({})

    tools = await server.list_tools()

    assert any(tool.name == "investigar_empresa" for tool in tools)


@pytest.mark.asyncio
async def test_tool_documents_the_identificador_parameter() -> None:
    server = _server({})

    tools = await server.list_tools()
    tool = next(tool for tool in tools if tool.name == "investigar_empresa")

    assert "identificador" in tool.input_schema["properties"]


@pytest.mark.asyncio
async def test_tool_returns_an_index_not_the_full_investigation() -> None:
    server = _server({"11444777000161": _EMPRESA_EXEMPLO})

    result = await server.call_tool("investigar_empresa", {"identificador": "11.444.777/0001-61"})

    assert result.is_error is False
    content = result.structured_content
    assert "investigation_id" in content
    assert content["empresa"]["cnpj"] == "11444777000161"
    assert content["processos_status"]["status"] == "nao_confirmada"
    nomes_secoes = {s["nome"] for s in content["secoes"]}
    assert "socios" in nomes_secoes
    assert "noticias" in nomes_secoes
    # a secao em si nao vem inline no indice - so a contagem
    socios_resumo = next(s for s in content["secoes"] if s["nome"] == "socios")
    assert socios_resumo["total_itens"] == 1


@pytest.mark.asyncio
async def test_socios_section_can_be_retrieved_in_full() -> None:
    server = _server({"11444777000161": _EMPRESA_EXEMPLO})
    indice = (
        await server.call_tool("investigar_empresa", {"identificador": "11.444.777/0001-61"})
    ).structured_content

    pagina = await _secao(server, indice["investigation_id"], "socios")

    assert pagina["itens"] == [
        {"nome": "Joana Silva", "qualificacao": "Socia-Administradora", "documento": None}
    ]
    assert pagina["total_itens"] == 1
    assert pagina["total_paginas"] == 1


@pytest.mark.asyncio
async def test_obter_indice_investigacao_re_fetches_the_index() -> None:
    server = _server({"11444777000161": _EMPRESA_EXEMPLO})
    indice = (
        await server.call_tool("investigar_empresa", {"identificador": "11.444.777/0001-61"})
    ).structured_content

    result = await server.call_tool(
        "obter_indice_investigacao", {"investigation_id": indice["investigation_id"]}
    )

    assert result.is_error is False
    assert result.structured_content["investigation_id"] == indice["investigation_id"]


@pytest.mark.asyncio
async def test_obter_secao_investigacao_raises_for_unknown_investigation_id() -> None:
    server = _server({})

    with pytest.raises(ToolError):
        await server.call_tool(
            "obter_secao_investigacao",
            {"investigation_id": "does-not-exist", "secao": "socios"},
        )


@pytest.mark.asyncio
async def test_obter_secao_investigacao_raises_for_unknown_section() -> None:
    server = _server({"11444777000161": _EMPRESA_EXEMPLO})
    indice = (
        await server.call_tool("investigar_empresa", {"identificador": "11.444.777/0001-61"})
    ).structured_content

    with pytest.raises(ToolError):
        await server.call_tool(
            "obter_secao_investigacao",
            {"investigation_id": indice["investigation_id"], "secao": "nao_existe"},
        )


@pytest.mark.asyncio
async def test_tool_rejects_empty_identificador() -> None:
    server = _server({})

    with pytest.raises(ToolError):
        await server.call_tool("investigar_empresa", {"identificador": ""})


@pytest.mark.asyncio
async def test_tool_raises_when_company_is_not_found() -> None:
    server = _server({})

    with pytest.raises(ToolError):
        await server.call_tool("investigar_empresa", {"identificador": "11.444.777/0001-61"})


@pytest.mark.asyncio
async def test_tool_returns_candidates_for_an_ambiguous_name() -> None:
    outra = Company(
        cnpj="11222333000181",
        razao_social="Empresa Exemplo Sul",
        nome_fantasia="Sul",
        situacao="ATIVA",
    )
    results = [
        SearchResult(
            title="Empresa Exemplo - CNPJ 11.444.777/0001-61",
            url="https://x.exemplo/1",
            snippet="11.444.777/0001-61",
            source="serper",
        ),
        SearchResult(
            title="Empresa Exemplo Sul - CNPJ 11.222.333/0001-81",
            url="https://x.exemplo/2",
            snippet="11.222.333/0001-81",
            source="serper",
        ),
    ]
    server = _server(
        {"11444777000161": _EMPRESA_EXEMPLO, "11222333000181": outra}, search_results=results
    )

    result = await server.call_tool("investigar_empresa", {"identificador": "Empresa Exemplo"})

    assert result.is_error is False
    content = result.structured_content
    assert content["empresa"] is None
    candidatos_resumo = next(s for s in content["secoes"] if s["nome"] == "candidatos")
    assert candidatos_resumo["total_itens"] == 2

    pagina = await _secao(server, content["investigation_id"], "candidatos")
    assert len(pagina["itens"]) == 2

    limitacoes_resumo = next(s for s in content["secoes"] if s["nome"] == "limitacoes")
    assert limitacoes_resumo["total_itens"] >= 1


@pytest.mark.asyncio
async def test_tool_still_succeeds_with_limitations_when_search_provider_is_not_configured() -> (
    None
):
    # CNPJ direto nao depende do SearchProvider para identificar a empresa; as
    # buscas de noticias/redes sociais/LinkedIn/processos falham de forma isolada
    # e ficam registradas em 'limitacoes', sem derrubar a investigacao inteira.
    # SearchProvider explicitamente "nao configurado" aqui, para nao depender de
    # SEARCH_API_KEY estar (ou nao) definida no ambiente de quem roda os testes.
    server = build_server(
        company_repository=FakeCompanyRepository({"11444777000161": _EMPRESA_EXEMPLO}),
        search_provider=UnconfiguredSearchProvider(),
    )

    result = await server.call_tool("investigar_empresa", {"identificador": "11.444.777/0001-61"})

    assert result.is_error is False
    content = result.structured_content
    assert content["empresa"]["cnpj"] == "11444777000161"
    noticias_resumo = next(s for s in content["secoes"] if s["nome"] == "noticias")
    assert noticias_resumo["total_itens"] == 0
    limitacoes_resumo = next(s for s in content["secoes"] if s["nome"] == "limitacoes")
    assert limitacoes_resumo["total_itens"] >= 1


class FakeProcessNumberLookup(ProcessNumberLookupPort):
    def __init__(self, dados: dict[str, DadosOficiaisProcesso] | None = None) -> None:
        self._dados = dados or {}

    async def find_by_number(self, numero_processo: str) -> DadosOficiaisProcesso | None:
        return self._dados.get(numero_processo)


@pytest.mark.asyncio
async def test_tool_confirms_a_process_via_datajud_when_a_number_is_found() -> None:
    resultado_busca = [
        SearchResult(
            title="Empresa Exemplo - processo 0001234-56.2020.8.26.0100",
            url="https://noticia.exemplo/1",
            snippet="processo judicial envolvendo Empresa Exemplo",
            source="serper",
        )
    ]
    dados_oficiais = DadosOficiaisProcesso(
        numero_processo="00012345620208260100",
        tribunal="TJSP",
        grau="G1",
        orgao_julgador="1a Vara Civel",
        classe="Procedimento Comum Civel",
        assuntos=["Rescisao"],
        movimentos=[],
        data_ajuizamento="2020-05-20T10:00:00Z",
        sistema="PJe",
        fonte="DataJud (CNJ)",
        consultado_em=datetime.now(UTC),
    )
    server = build_server(
        company_repository=FakeCompanyRepository({"11444777000161": _EMPRESA_EXEMPLO}),
        search_provider=FakeSearchProvider(resultado_busca),
        process_number_lookup=FakeProcessNumberLookup(
            {"0001234-56.2020.8.26.0100": dados_oficiais}
        ),
    )

    result = await server.call_tool("investigar_empresa", {"identificador": "11.444.777/0001-61"})

    assert result.is_error is False
    content = result.structured_content
    assert content["processos_status"]["status"] == "realizada"

    pagina = await _secao(server, content["investigation_id"], "processos_confirmados")
    assert len(pagina["itens"]) == 1
    confirmado = pagina["itens"][0]
    assert confirmado["dados"]["numero_processo"] == "00012345620208260100"
    assert confirmado["dados"]["tribunal"] == "TJSP"
    assert confirmado["relacionado_a"] == "Empresa Exemplo"


@pytest.mark.asyncio
async def test_tool_expands_related_companies_by_default() -> None:
    empresa_principal = Company(
        cnpj="11444777000161",
        razao_social="Empresa A LTDA",
        nome_fantasia="Empresa A",
        situacao="ATIVA",
        socios=[Socio(nome="Socio A", qualificacao="Socio-Administrador")],
    )
    empresa_relacionada = Company(
        cnpj="11222333000181",
        razao_social="Empresa B LTDA",
        nome_fantasia="Empresa B",
        situacao="ATIVA",
    )
    resultado_busca = [
        SearchResult(
            title="Socio A - CNPJ 11.222.333/0001-81",
            url="https://x.exemplo/1",
            snippet="Socio A e socio da Empresa B, CNPJ 11.222.333/0001-81",
            source="serper",
        )
    ]
    server = build_server(
        company_repository=FakeCompanyRepository(
            {"11444777000161": empresa_principal, "11222333000181": empresa_relacionada}
        ),
        search_provider=FakeSearchProvider(resultado_busca),
    )

    result = await server.call_tool("investigar_empresa", {"identificador": "11.444.777/0001-61"})

    assert result.is_error is False
    content = result.structured_content
    relacionadas_resumo = next(s for s in content["secoes"] if s["nome"] == "empresas_relacionadas")
    assert relacionadas_resumo["total_itens"] == 1

    pagina_relacionadas = await _secao(server, content["investigation_id"], "empresas_relacionadas")
    relacionada = pagina_relacionadas["itens"][0]
    assert relacionada["empresa"]["cnpj"] == "11222333000181"
    assert relacionada["investigation_id"] != content["investigation_id"]

    # a sub-investigacao da empresa relacionada e acessivel pelo proprio id,
    # e ela nao expandiu mais um nivel de rede (profundidade padrao 1)
    sub_indice = (
        await server.call_tool(
            "obter_indice_investigacao", {"investigation_id": relacionada["investigation_id"]}
        )
    ).structured_content
    sub_relacionadas = next(s for s in sub_indice["secoes"] if s["nome"] == "empresas_relacionadas")
    assert sub_relacionadas["total_itens"] == 0

    pagina_relacionamentos = await _secao(server, content["investigation_id"], "relacionamentos")
    assert any(r["tipo_relacionamento"] == "socio_de" for r in pagina_relacionamentos["itens"])


@pytest.mark.asyncio
async def test_tool_does_not_expand_network_when_profundidade_is_zero() -> None:
    empresa_principal = Company(
        cnpj="11444777000161",
        razao_social="Empresa A LTDA",
        nome_fantasia="Empresa A",
        situacao="ATIVA",
        socios=[Socio(nome="Socio A", qualificacao="Socio-Administrador")],
    )
    resultado_busca = [
        SearchResult(
            title="Socio A - CNPJ 11.222.333/0001-81",
            url="https://x.exemplo/1",
            snippet="Socio A e socio da Empresa B, CNPJ 11.222.333/0001-81",
            source="serper",
        )
    ]
    server = build_server(
        company_repository=FakeCompanyRepository({"11444777000161": empresa_principal}),
        search_provider=FakeSearchProvider(resultado_busca),
    )

    result = await server.call_tool(
        "investigar_empresa", {"identificador": "11.444.777/0001-61", "profundidade": 0}
    )

    assert result.is_error is False
    relacionadas_resumo = next(
        s for s in result.structured_content["secoes"] if s["nome"] == "empresas_relacionadas"
    )
    assert relacionadas_resumo["total_itens"] == 0


@pytest.mark.asyncio
async def test_tool_rejects_profundidade_above_the_maximum() -> None:
    server = _server({"11444777000161": _EMPRESA_EXEMPLO})

    with pytest.raises(ToolError):
        await server.call_tool(
            "investigar_empresa", {"identificador": "11.444.777/0001-61", "profundidade": 5}
        )


class FakePEPLookup(PEPLookupPort):
    def __init__(self, registros: dict[str, list[RegistroPEPBruto]] | None = None) -> None:
        self._registros = registros or {}

    async def search(self, nome: str, cpf: str | None = None) -> list[RegistroPEPBruto]:
        return self._registros.get(nome, [])


@pytest.mark.asyncio
async def test_tool_confirms_pep_when_document_matches() -> None:
    empresa = Company(
        cnpj="11444777000161",
        razao_social="Empresa A LTDA",
        nome_fantasia="Empresa A",
        situacao="ATIVA",
        socios=[Socio(nome="Socio A", qualificacao="Socio", documento="***112108**")],
    )
    pep_lookup = FakePEPLookup(
        {
            "Socio A": [
                RegistroPEPBruto(
                    cpf="***112108**",
                    nome="Socio A",
                    funcao="Ministro",
                    orgao="Ministerio Exemplo",
                    data_inicio="01/01/2020",
                    data_fim=None,
                    data_fim_carencia=None,
                )
            ]
        }
    )
    server = build_server(
        company_repository=FakeCompanyRepository({"11444777000161": empresa}),
        search_provider=FakeSearchProvider([]),
        pep_lookup=pep_lookup,
    )

    result = await server.call_tool("investigar_empresa", {"identificador": "11.444.777/0001-61"})

    assert result.is_error is False
    pagina = await _secao(server, result.structured_content["investigation_id"], "peps")
    peps = pagina["itens"]
    assert len(peps) == 1
    assert peps[0]["status"] == "PEP_CONFIRMADA"
    assert peps[0]["funcao"] == "Ministro"


@pytest.mark.asyncio
async def test_ping_buscar_empresa_and_buscar_informacoes_publicas_keep_working() -> None:
    from company_investigator.domain.entities.public_page_info import PublicPageInfo
    from company_investigator.domain.ports.browser import BrowserPort

    class FakeBrowser(BrowserPort):
        async def fetch_page(self, url: str) -> PublicPageInfo:
            return PublicPageInfo(url=url, titulo="T", texto="texto")

    server = build_server(
        company_repository=FakeCompanyRepository({"11444777000161": _EMPRESA_EXEMPLO}),
        browser=FakeBrowser(),
        search_provider=FakeSearchProvider([]),
    )

    ping_result = await server.call_tool("ping", {})
    assert ping_result.is_error is False

    empresa_result = await server.call_tool("buscar_empresa", {"cnpj": "11444777000161"})
    assert empresa_result.is_error is False

    pagina_result = await server.call_tool(
        "buscar_informacoes_publicas", {"url": "https://example.com/"}
    )
    assert pagina_result.is_error is False


@pytest.mark.asyncio
async def test_process_with_thousands_of_movements_never_produces_a_giant_response() -> None:
    resultado_busca = [
        SearchResult(
            title="Empresa Exemplo - processo 0001234-56.2020.8.26.0100",
            url="https://noticia.exemplo/1",
            snippet="processo judicial envolvendo Empresa Exemplo",
            source="serper",
        )
    ]
    dados_oficiais = DadosOficiaisProcesso(
        numero_processo="00012345620208260100",
        tribunal="TJSP",
        grau="G1",
        orgao_julgador="1a Vara Civel",
        classe="Procedimento Comum Civel",
        assuntos=["Rescisao"],
        movimentos=[
            Movimento(nome=f"Movimento processual numero {i}", data="2020-05-20T10:00:00Z")
            for i in range(1200)
        ],
        data_ajuizamento="2020-05-20T10:00:00Z",
        sistema="PJe",
        fonte="DataJud (CNJ)",
        consultado_em=datetime.now(UTC),
    )
    server = build_server(
        company_repository=FakeCompanyRepository({"11444777000161": _EMPRESA_EXEMPLO}),
        search_provider=FakeSearchProvider(resultado_busca),
        process_number_lookup=FakeProcessNumberLookup(
            {"0001234-56.2020.8.26.0100": dados_oficiais}
        ),
    )
    indice = (
        await server.call_tool("investigar_empresa", {"identificador": "11.444.777/0001-61"})
    ).structured_content
    investigation_id = indice["investigation_id"]

    movimentos_resumo = next(s for s in indice["secoes"] if s["nome"] == "movimentos_processuais")
    assert movimentos_resumo["total_itens"] == 1200

    processos = await _secao(server, investigation_id, "processos_confirmados")
    dados = processos["itens"][0]["dados"]
    assert dados["total_movimentos"] == 1200
    assert "movimentos" not in dados
    assert len(json.dumps(processos)) < _LIMITE_RESPOSTA_CHARS

    coletados: list[dict] = []
    pagina_num = 1
    while True:
        pagina = await _secao(
            server,
            investigation_id,
            "movimentos_processuais",
            pagina=pagina_num,
            tamanho_pagina=50,
        )
        assert len(json.dumps(pagina)) < _LIMITE_RESPOSTA_CHARS
        coletados.extend(pagina["itens"])
        if pagina_num >= pagina["total_paginas"]:
            break
        pagina_num += 1

    assert len(coletados) == 1200
    assert {m["numero_processo"] for m in coletados} == {"00012345620208260100"}
    assert coletados[0] == {
        "numero_processo": "00012345620208260100",
        "nome": "Movimento processual numero 0",
        "data": "2020-05-20T10:00:00Z",
    }
    assert coletados[-1]["nome"] == "Movimento processual numero 1199"
