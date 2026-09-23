import asyncio
from typing import Protocol

from company_investigator.application.exceptions import CompanyNotFoundError
from company_investigator.application.services.company_identification_service import (
    CompanyIdentificationResult,
    CompanyIdentificationService,
)
from company_investigator.application.services.related_companies_service import (
    EmpresaRelacionadaEncontrada,
)
from company_investigator.application.services.related_people_service import RelatedPeopleService
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import (
    ConsultaProcessual,
    ConsultaProcessualStatus,
    EmpresaInvestigada,
    EmpresaRelacionada,
    LinkedInResultado,
    Noticia,
    PerfilRedeSocial,
    PossivelRelacaoFamiliar,
    RegistroPEP,
    Relacionamento,
)
from company_investigator.domain.entities.socio import Socio
from company_investigator.domain.ports.search_provider import SearchProviderError

_SEM_CONSULTA_PROCESSUAL = ConsultaProcessual(
    confirmados=[],
    referencias=[],
    status=ConsultaProcessualStatus(
        status="nao_confirmada",
        motivo="Empresa nao identificada; consulta processual nao realizada.",
    ),
)


class _PartnerService(Protocol):
    async def search(self, company: Company) -> list[Socio]: ...


class _NewsService(Protocol):
    async def search(self, company: Company) -> list[Noticia]: ...


class _SocialMediaService(Protocol):
    async def search(self, company: Company) -> list[PerfilRedeSocial]: ...


class _LinkedInService(Protocol):
    async def search(self, company: Company) -> LinkedInResultado: ...


class _ProcessService(Protocol):
    async def search(self, company: Company, pessoas: list[str]) -> ConsultaProcessual: ...


class _RelatedCompaniesService(Protocol):
    async def find_related(
        self, socios: list[Socio], excluir_cnpj: str | None = None
    ) -> list[EmpresaRelacionadaEncontrada]: ...


class _FamilyRelationshipService(Protocol):
    async def find_possible_relations(
        self, pessoas: list[str]
    ) -> list[PossivelRelacaoFamiliar]: ...


class _PEPService(Protocol):
    async def check(self, socio: Socio) -> RegistroPEP: ...


class InvestigarEmpresaUseCase:
    """Orquestra a investigacao completa de uma empresa: identifica a empresa (por
    CNPJ ou nome), levanta socios/LinkedIn/noticias/redes sociais/processos/PEP, e
    entao expande a rede societaria (outras empresas dos socios) ate `depth` niveis,
    reutilizando esta mesma orquestracao recursivamente para cada empresa
    relacionada. Um conjunto `visited` (CNPJs) e propagado por toda a recursao para
    nunca investigar a mesma empresa duas vezes nem entrar em ciclo. A falha de uma
    fonte nao derruba a investigacao inteira: fica registrada em `limitacoes`."""

    def __init__(
        self,
        identification_service: CompanyIdentificationService,
        partner_service: _PartnerService,
        news_service: _NewsService,
        social_media_service: _SocialMediaService,
        linkedin_service: _LinkedInService,
        process_service: _ProcessService,
        related_companies_service: _RelatedCompaniesService,
        related_people_service: RelatedPeopleService,
        family_relationship_service: _FamilyRelationshipService,
        pep_service: _PEPService,
    ) -> None:
        self._identification_service = identification_service
        self._partner_service = partner_service
        self._news_service = news_service
        self._social_media_service = social_media_service
        self._linkedin_service = linkedin_service
        self._process_service = process_service
        self._related_companies_service = related_companies_service
        self._related_people_service = related_people_service
        self._family_relationship_service = family_relationship_service
        self._pep_service = pep_service

    async def execute(self, identificador: str, depth: int = 1) -> EmpresaInvestigada:
        identification = await self._identification_service.identify(identificador)

        if identification.empresa is None and not identification.candidatos:
            raise CompanyNotFoundError(f"Nenhuma empresa encontrada para '{identificador}'.")

        if identification.empresa is None:
            return self._ambiguous_result(identificador, identification)

        visited = {identification.empresa.cnpj}
        return await self._investigate(identificador, identification.empresa, depth, visited)

    def _ambiguous_result(
        self, identificador: str, identification: CompanyIdentificationResult
    ) -> EmpresaInvestigada:
        return EmpresaInvestigada(
            identificador_usado=identificador,
            empresa=None,
            candidatos=identification.candidatos,
            socios=[],
            pessoas_chave=[],
            linkedin=LinkedInResultado(empresa=None, pessoas_chave=[]),
            redes_sociais=[],
            noticias=[],
            contatos=[],
            processos=_SEM_CONSULTA_PROCESSUAL,
            fontes=[],
            limitacoes=[
                f"{len(identification.candidatos)} empresas correspondem a '{identificador}'; "
                "refine a busca com o CNPJ ou a razao social completa para desambiguar."
            ],
        )

    async def _investigate(
        self, identificador: str, company: Company, depth: int, visited: set[str]
    ) -> EmpresaInvestigada:
        limitacoes: list[str] = []

        # Socios e pessoas-chave (LinkedIn) precisam vir antes da consulta
        # processual (pesquisa processos tambem por essas pessoas) e da expansao
        # de rede (que parte dos socios).
        socios_raw, linkedin_raw = await asyncio.gather(
            self._partner_service.search(company),
            self._linkedin_service.search(company),
            return_exceptions=True,
        )
        socios = _resolve(socios_raw, [], "socios", limitacoes)
        linkedin = _resolve(
            linkedin_raw, LinkedInResultado(empresa=None, pessoas_chave=[]), "LinkedIn", limitacoes
        )

        pessoas_da_empresa = [s.nome for s in socios] + [p.nome for p in linkedin.pessoas_chave]

        noticias_raw, redes_sociais_raw, processos, peps = await asyncio.gather(
            self._news_service.search(company),
            self._social_media_service.search(company),
            self._process_service.search(company, pessoas_da_empresa),
            self._check_peps(socios, limitacoes),
            return_exceptions=True,
        )

        noticias = _resolve(noticias_raw, [], "noticias", limitacoes)
        redes_sociais = _resolve(redes_sociais_raw, [], "redes sociais", limitacoes)
        if isinstance(processos, BaseException):
            # ProcessSearchService trata seus proprios erros e nao deveria chegar
            # aqui, mas mantemos o fallback por seguranca/consistencia com as demais.
            processos = _resolve(
                processos, _SEM_CONSULTA_PROCESSUAL, "processos judiciais", limitacoes
            )
        if isinstance(peps, BaseException):
            peps = _resolve(peps, [], "verificacao de PEP", limitacoes)

        empresas_relacionadas, relacionamentos = await self._expand_network(
            company, socios, depth, visited, limitacoes
        )
        pessoas_relacionadas = self._related_people_service.collect(empresas_relacionadas)

        todas_pessoas = list(
            dict.fromkeys(pessoas_da_empresa + [p.nome for p in pessoas_relacionadas])
        )
        possiveis_relacoes = await self._check_family_relations(todas_pessoas, limitacoes)

        redes_sociais_completas = list(redes_sociais)
        if linkedin.empresa is not None:
            redes_sociais_completas.append(linkedin.empresa)

        fontes = _collect_fontes(
            noticias, redes_sociais_completas, linkedin, processos, empresas_relacionadas
        )

        return EmpresaInvestigada(
            identificador_usado=identificador,
            empresa=company,
            candidatos=[],
            socios=socios,
            pessoas_chave=linkedin.pessoas_chave,
            linkedin=linkedin,
            redes_sociais=redes_sociais_completas,
            noticias=noticias,
            contatos=[],
            processos=processos,
            fontes=fontes,
            empresas_relacionadas=empresas_relacionadas,
            pessoas_relacionadas=pessoas_relacionadas,
            relacionamentos=relacionamentos,
            possiveis_relacoes_familiares=possiveis_relacoes,
            peps=peps,
            limitacoes=limitacoes,
        )

    async def _check_peps(self, socios: list[Socio], limitacoes: list[str]) -> list[RegistroPEP]:
        if not socios:
            return []
        resultados = await asyncio.gather(*(self._pep_service.check(s) for s in socios))
        return resultados

    async def _check_family_relations(
        self, pessoas: list[str], limitacoes: list[str]
    ) -> list[PossivelRelacaoFamiliar]:
        if len(pessoas) < 2:
            return []
        try:
            return await self._family_relationship_service.find_possible_relations(pessoas)
        except SearchProviderError as exc:
            limitacoes.append(f"Falha ao verificar possiveis relacoes familiares: {exc}")
            return []

    async def _expand_network(
        self,
        company: Company,
        socios: list[Socio],
        depth: int,
        visited: set[str],
        limitacoes: list[str],
    ) -> tuple[list[EmpresaRelacionada], list[Relacionamento]]:
        if depth <= 0 or not socios:
            return [], []

        try:
            encontradas = await self._related_companies_service.find_related(
                socios, excluir_cnpj=company.cnpj
            )
        except SearchProviderError as exc:
            limitacoes.append(f"Falha ao buscar empresas relacionadas: {exc}")
            return [], []

        # Usa razao_social (sempre unica por CNPJ) para identificar empresas nas
        # arestas do grafo - nome_fantasia pode colidir entre empresas distintas.
        nome_empresa_atual = company.razao_social
        relacionamentos: list[Relacionamento] = []
        novas_por_cnpj: dict[str, EmpresaRelacionadaEncontrada] = {}

        for encontrada in encontradas:
            nome_empresa_encontrada = encontrada.empresa.razao_social
            relacionamentos.append(
                Relacionamento(
                    origem=encontrada.origem_socio,
                    destino=nome_empresa_encontrada,
                    tipo_relacionamento="socio_de",
                    fonte=encontrada.fonte,
                    confianca=encontrada.confianca,
                )
            )
            if encontrada.empresa.cnpj in visited or encontrada.empresa.cnpj in novas_por_cnpj:
                continue
            novas_por_cnpj[encontrada.empresa.cnpj] = encontrada

        empresas_relacionadas: list[EmpresaRelacionada] = []
        for cnpj, encontrada in novas_por_cnpj.items():
            visited.add(cnpj)
            sub_investigacao = await self._investigate(cnpj, encontrada.empresa, depth - 1, visited)
            empresas_relacionadas.append(
                EmpresaRelacionada(
                    empresa=encontrada.empresa,
                    origem_socio=encontrada.origem_socio,
                    participacao=encontrada.participacao,
                    fonte=encontrada.fonte,
                    confianca=encontrada.confianca,
                    investigacao=sub_investigacao,
                )
            )
            relacionamentos.append(
                Relacionamento(
                    origem=encontrada.empresa.razao_social,
                    destino=nome_empresa_atual,
                    tipo_relacionamento="relacionada_por_socio",
                    fonte=encontrada.fonte,
                    confianca=encontrada.confianca,
                )
            )

        return empresas_relacionadas, relacionamentos


def _resolve(value: object, default: object, label: str, limitacoes: list[str]) -> object:
    if isinstance(value, BaseException):
        limitacoes.append(f"Falha ao buscar {label}: {value}")
        return default
    return value


def _collect_fontes(
    noticias: list[Noticia],
    redes_sociais: list[PerfilRedeSocial],
    linkedin: LinkedInResultado,
    processos: ConsultaProcessual,
    empresas_relacionadas: list[EmpresaRelacionada],
) -> list[str]:
    urls = {n.url for n in noticias}
    urls.update(r.url for r in redes_sociais)
    urls.update(p.url_linkedin for p in linkedin.pessoas_chave)
    urls.update(r.url for r in processos.referencias)
    for relacionada in empresas_relacionadas:
        urls.update(relacionada.investigacao.fontes)
    return sorted(urls)
