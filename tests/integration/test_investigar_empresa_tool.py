from datetime import UTC, datetime

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import DadosOficiaisProcesso
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
async def test_tool_returns_structured_investigation_for_a_cnpj() -> None:
    server = _server({"11444777000161": _EMPRESA_EXEMPLO})

    result = await server.call_tool("investigar_empresa", {"identificador": "11.444.777/0001-61"})

    assert result.is_error is False
    content = result.structured_content
    assert content["empresa"]["cnpj"] == "11444777000161"
    assert content["socios"] == [
        {"nome": "Joana Silva", "qualificacao": "Socia-Administradora", "documento": None}
    ]
    assert content["candidatos"] == []
    assert "linkedin" in content
    assert "pessoas_chave" in content["linkedin"]
    assert set(content["processos"].keys()) == {"confirmados", "referencias", "status", "motivo"}
    assert content["processos"]["status"] == "nao_confirmada"


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
    assert len(content["candidatos"]) == 2
    assert content["limitacoes"]


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
    assert content["noticias"] == []
    assert content["limitacoes"]


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
    processos = result.structured_content["processos"]
    assert processos["status"] == "realizada"
    assert len(processos["confirmados"]) == 1
    confirmado = processos["confirmados"][0]
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
    assert len(content["empresas_relacionadas"]) == 1
    relacionada = content["empresas_relacionadas"][0]
    assert relacionada["empresa"]["cnpj"] == "11222333000181"
    assert relacionada["investigacao"]["empresas_relacionadas"] == []
    assert any(r["tipo_relacionamento"] == "socio_de" for r in content["relacionamentos"])


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
    assert result.structured_content["empresas_relacionadas"] == []


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
    peps = result.structured_content["peps"]
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
