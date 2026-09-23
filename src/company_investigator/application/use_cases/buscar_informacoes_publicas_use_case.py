from company_investigator.domain.entities.public_page_info import PublicPageInfo
from company_investigator.domain.ports.browser import BrowserPort


class BuscarInformacoesPublicasUseCase:
    def __init__(self, browser: BrowserPort) -> None:
        self._browser = browser

    async def execute(self, url: str) -> PublicPageInfo:
        return await self._browser.fetch_page(url)
