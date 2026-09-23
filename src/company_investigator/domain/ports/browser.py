from abc import ABC, abstractmethod

from company_investigator.domain.entities.public_page_info import PublicPageInfo


class BrowserError(Exception):
    """Falha de infraestrutura ao navegar ate uma URL (timeout, navegacao invalida etc.)."""


class BrowserPort(ABC):
    @abstractmethod
    async def fetch_page(self, url: str) -> PublicPageInfo: ...
