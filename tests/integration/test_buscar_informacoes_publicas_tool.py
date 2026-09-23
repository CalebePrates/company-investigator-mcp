import pytest
from mcp.server.mcpserver.exceptions import ToolError

from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.public_page_info import PublicPageInfo
from company_investigator.domain.ports.browser import BrowserError, BrowserPort
from company_investigator.domain.ports.company_repository import CompanyRepositoryPort
from company_investigator.domain.value_objects.cnpj import Cnpj
from company_investigator.interface.mcp_server.server import build_server


class FakeBrowser(BrowserPort):
    """Substitui o PlaywrightBrowser real nestes testes, sem abrir um navegador."""

    def __init__(
        self, result: PublicPageInfo | None = None, error: BrowserError | None = None
    ) -> None:
        self._result = result
        self._error = error

    async def fetch_page(self, url: str) -> PublicPageInfo:
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


@pytest.mark.asyncio
async def test_tool_is_registered_on_the_server() -> None:
    server = build_server(browser=FakeBrowser())

    tools = await server.list_tools()

    assert any(tool.name == "buscar_informacoes_publicas" for tool in tools)


@pytest.mark.asyncio
async def test_tool_documents_the_url_parameter() -> None:
    server = build_server(browser=FakeBrowser())

    tools = await server.list_tools()
    tool = next(tool for tool in tools if tool.name == "buscar_informacoes_publicas")

    assert "url" in tool.input_schema["properties"]


@pytest.mark.asyncio
async def test_tool_returns_structured_page_info() -> None:
    page_info = PublicPageInfo(
        url="https://example.com/", titulo="Example Domain", texto="conteudo da pagina"
    )
    server = build_server(browser=FakeBrowser(result=page_info))

    result = await server.call_tool("buscar_informacoes_publicas", {"url": "https://example.com/"})

    assert result.is_error is False
    assert result.structured_content == {
        "url": "https://example.com/",
        "titulo": "Example Domain",
        "texto": "conteudo da pagina",
    }


@pytest.mark.asyncio
async def test_tool_returns_null_titulo_when_page_has_no_title() -> None:
    page_info = PublicPageInfo(url="https://example.com/", titulo=None, texto="conteudo")
    server = build_server(browser=FakeBrowser(result=page_info))

    result = await server.call_tool("buscar_informacoes_publicas", {"url": "https://example.com/"})

    assert result.is_error is False
    assert result.structured_content["titulo"] is None


@pytest.mark.asyncio
async def test_tool_rejects_invalid_url() -> None:
    server = build_server(browser=FakeBrowser())

    with pytest.raises(ToolError):
        await server.call_tool("buscar_informacoes_publicas", {"url": "nao-e-uma-url"})


@pytest.mark.asyncio
async def test_tool_rejects_empty_url() -> None:
    server = build_server(browser=FakeBrowser())

    with pytest.raises(ToolError):
        await server.call_tool("buscar_informacoes_publicas", {"url": ""})


@pytest.mark.asyncio
async def test_tool_raises_on_navigation_error() -> None:
    server = build_server(browser=FakeBrowser(error=BrowserError("falha ao navegar")))

    with pytest.raises(ToolError):
        await server.call_tool(
            "buscar_informacoes_publicas", {"url": "https://exemplo-invalido.test"}
        )


@pytest.mark.asyncio
async def test_tool_raises_on_timeout() -> None:
    server = build_server(browser=FakeBrowser(error=BrowserError("tempo limite excedido")))

    with pytest.raises(ToolError):
        await server.call_tool("buscar_informacoes_publicas", {"url": "https://exemplo-lento.test"})


class _FakeCompanyRepository(CompanyRepositoryPort):
    async def find_by_cnpj(self, cnpj: Cnpj) -> Company | None:
        return None


@pytest.mark.asyncio
async def test_ping_and_buscar_empresa_keep_working_alongside_the_new_tool() -> None:
    server = build_server(browser=FakeBrowser(), company_repository=_FakeCompanyRepository())

    ping_result = await server.call_tool("ping", {})
    assert ping_result.is_error is False

    with pytest.raises(ToolError):
        await server.call_tool("buscar_empresa", {"cnpj": "11.444.777/0001-61"})
