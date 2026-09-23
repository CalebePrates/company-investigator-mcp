from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from company_investigator.domain.entities.public_page_info import PublicPageInfo
from company_investigator.domain.ports.browser import BrowserError, BrowserPort
from company_investigator.infrastructure.browser.html_page_parser import extract_title_and_text

_DEFAULT_TIMEOUT_MS = 15_000


class PlaywrightBrowser(BrowserPort):
    """Abre paginas com Playwright (Chromium headless) e extrai titulo/texto com
    BeautifulSoup/lxml. E a unica classe do projeto que conhece o Playwright."""

    def __init__(self, timeout_ms: int = _DEFAULT_TIMEOUT_MS) -> None:
        self._timeout_ms = timeout_ms

    async def fetch_page(self, url: str) -> PublicPageInfo:
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch()
                try:
                    page = await browser.new_page()
                    await page.goto(url, timeout=self._timeout_ms, wait_until="load")
                    html = await page.content()
                finally:
                    await browser.close()
        except PlaywrightTimeoutError as exc:
            raise BrowserError(f"Tempo limite excedido ao carregar {url}.") from exc
        except PlaywrightError as exc:
            raise BrowserError(f"Falha ao navegar ate {url}.") from exc

        titulo, texto = extract_title_and_text(html)
        return PublicPageInfo(url=url, titulo=titulo, texto=texto)
