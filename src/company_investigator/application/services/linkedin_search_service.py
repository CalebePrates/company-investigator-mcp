import asyncio
from datetime import UTC, datetime

from company_investigator.application.services._confidence import classify_name_match
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import (
    ConfidenceLevel,
    LinkedInResultado,
    PerfilRedeSocial,
    PessoaChave,
)
from company_investigator.domain.ports.search_provider import SearchProviderPort

_PRIORITY_ROLES = ["CEO", "Founder", "Co-Founder", "Socio", "Diretor", "CFO", "COO", "CTO"]
_MAX_RESULTS_PER_ROLE = 3


class LinkedInSearchService:
    """Tratamento especial para o LinkedIn: pesquisa a pagina oficial da empresa e,
    para uma lista priorizada de cargos de lideranca, tenta encontrar pessoas-chave
    relacionadas a ela. Tudo via SearchProvider (operador site:linkedin.com/...),
    sem nenhum acesso direto/autenticado ao LinkedIn."""

    def __init__(self, search_provider: SearchProviderPort) -> None:
        self._search_provider = search_provider

    async def search(self, company: Company) -> LinkedInResultado:
        empresa_perfil = await self._search_company_page(company)
        pessoas_chave = await self._search_key_people(company)
        return LinkedInResultado(empresa=empresa_perfil, pessoas_chave=pessoas_chave)

    async def _search_company_page(self, company: Company) -> PerfilRedeSocial | None:
        nome = company.nome_fantasia or company.razao_social
        results = await self._search_provider.search(
            f'site:linkedin.com/company "{nome}"', max_results=3
        )
        if not results:
            return None

        melhor = results[0]
        return PerfilRedeSocial(
            plataforma="LinkedIn",
            nome_perfil=melhor.title,
            url=melhor.url,
            tipo="empresa",
            fonte=melhor.source,
            consultado_em=datetime.now(UTC),
            confianca=classify_name_match(nome, melhor.title, melhor.snippet),
        )

    async def _search_key_people(self, company: Company) -> list[PessoaChave]:
        nome = company.nome_fantasia or company.razao_social
        tasks = [self._search_role(nome, cargo) for cargo in _PRIORITY_ROLES]
        resultados_por_cargo = await asyncio.gather(*tasks)

        consultado_em = datetime.now(UTC)
        pessoas: dict[str, PessoaChave] = {}
        for cargo_pesquisado, results in zip(_PRIORITY_ROLES, resultados_por_cargo, strict=True):
            for result in results:
                if result.url in pessoas:
                    continue

                nome_pessoa, cargo_extraido = _parse_linkedin_title(result.title)
                confianca = classify_name_match(nome, result.title, result.snippet)
                if confianca == ConfidenceLevel.ALTA:
                    confianca = (
                        ConfidenceLevel.MEDIA
                    )  # sem confirmacao cruzada extra, nunca "alta" so pelo nome

                pessoas[result.url] = PessoaChave(
                    nome=nome_pessoa,
                    cargo=cargo_extraido or cargo_pesquisado,
                    empresa_relacionada=nome,
                    url_linkedin=result.url,
                    tipo_cargo=cargo_pesquisado,
                    confianca=confianca,
                    fontes=[result.url],
                    consultado_em=consultado_em,
                )

        return list(pessoas.values())

    async def _search_role(self, nome: str, cargo: str) -> list:
        query = f'site:linkedin.com/in "{nome}" "{cargo}"'
        return await self._search_provider.search(query, max_results=_MAX_RESULTS_PER_ROLE)


def _parse_linkedin_title(title: str) -> tuple[str, str | None]:
    """Titulos de resultados do LinkedIn tipicamente seguem o formato
    'Nome - Cargo - Empresa | LinkedIn'. Extrai nome/cargo de forma heuristica."""
    cleaned = title.replace("| LinkedIn", "").strip()
    partes = [p.strip() for p in cleaned.split(" - ") if p.strip()]
    nome_pessoa = partes[0] if partes else cleaned
    cargo = partes[1] if len(partes) > 1 else None
    return nome_pessoa, cargo
