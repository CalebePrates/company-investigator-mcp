import asyncio
from datetime import UTC, datetime

from company_investigator.application.services._confidence import classify_name_match
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import PerfilRedeSocial
from company_investigator.domain.ports.search_provider import SearchProviderPort

_PLATFORM_DOMAINS = {
    "Instagram": "instagram.com",
    "Facebook": "facebook.com",
    "YouTube": "youtube.com",
    "X/Twitter": "twitter.com",
    "TikTok": "tiktok.com",
}


class SocialMediaSearchService:
    """Pesquisa perfis publicos da empresa em Instagram, Facebook, YouTube, X/Twitter
    e TikTok via SearchProvider, usando o operador site: para restringir a busca a
    cada plataforma. O LinkedIn recebe tratamento proprio no LinkedInSearchService."""

    def __init__(self, search_provider: SearchProviderPort) -> None:
        self._search_provider = search_provider

    async def search(self, company: Company) -> list[PerfilRedeSocial]:
        tasks = [
            self._search_platform(nome, dominio, company)
            for nome, dominio in _PLATFORM_DOMAINS.items()
        ]
        perfis = await asyncio.gather(*tasks)
        return [perfil for perfil in perfis if perfil is not None]

    async def _search_platform(
        self, plataforma: str, dominio: str, company: Company
    ) -> PerfilRedeSocial | None:
        nome = company.nome_fantasia or company.razao_social
        results = await self._search_provider.search(f'site:{dominio} "{nome}"', max_results=3)
        if not results:
            return None

        melhor = results[0]
        return PerfilRedeSocial(
            plataforma=plataforma,
            nome_perfil=melhor.title,
            url=melhor.url,
            tipo="empresa",
            fonte=melhor.source,
            consultado_em=datetime.now(UTC),
            confianca=classify_name_match(nome, melhor.title, melhor.snippet),
        )
