import inspect

import pytest

from company_investigator.application.use_cases import (
    buscar_informacoes_publicas_use_case as module,
)
from company_investigator.application.use_cases.buscar_informacoes_publicas_use_case import (
    BuscarInformacoesPublicasUseCase,
)
from company_investigator.domain.entities.public_page_info import PublicPageInfo
from company_investigator.domain.ports.browser import BrowserError, BrowserPort


class FakeBrowser(BrowserPort):
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
async def test_execute_returns_whatever_the_browser_reports() -> None:
    expected = PublicPageInfo(url="https://example.com/", titulo="Example", texto="conteudo")
    use_case = BuscarInformacoesPublicasUseCase(browser=FakeBrowser(result=expected))

    result = await use_case.execute("https://example.com/")

    assert result == expected


@pytest.mark.asyncio
async def test_execute_propagates_navigation_errors() -> None:
    use_case = BuscarInformacoesPublicasUseCase(
        browser=FakeBrowser(error=BrowserError("falha ao navegar"))
    )

    with pytest.raises(BrowserError):
        await use_case.execute("https://exemplo-invalido.test")


@pytest.mark.asyncio
async def test_execute_propagates_timeout_errors() -> None:
    use_case = BuscarInformacoesPublicasUseCase(
        browser=FakeBrowser(error=BrowserError("tempo limite excedido"))
    )

    with pytest.raises(BrowserError):
        await use_case.execute("https://exemplo-lento.test")


def test_use_case_module_has_no_playwright_reference() -> None:
    source = inspect.getsource(module)

    assert "playwright" not in source.lower()
