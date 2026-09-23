import pytest

from company_investigator.application.exceptions import CompanyNotFoundError
from company_investigator.application.services.company_identification_service import (
    CompanyIdentificationResult,
)
from company_investigator.application.services.related_companies_service import (
    EmpresaRelacionadaEncontrada,
)
from company_investigator.application.services.related_people_service import RelatedPeopleService
from company_investigator.application.use_cases.investigar_empresa_use_case import (
    InvestigarEmpresaUseCase,
)
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import (
    ConfidenceLevel,
    ConsultaProcessual,
    ConsultaProcessualStatus,
    LinkedInResultado,
    Noticia,
    PerfilRedeSocial,
    PossivelRelacaoFamiliar,
    RegistroPEP,
    StatusPEP,
)
from company_investigator.domain.entities.socio import Socio
from company_investigator.domain.ports.search_provider import SearchProviderError

_EMPRESA_A = Company(
    cnpj="11444777000161",
    razao_social="Empresa A LTDA",
    nome_fantasia="Empresa A",
    situacao="ATIVA",
    socios=[Socio(nome="Socio A", qualificacao="Socio-Administrador")],
)
_EMPRESA_B = Company(
    cnpj="11222333000181",
    razao_social="Empresa B LTDA",
    nome_fantasia="Empresa B",
    situacao="ATIVA",
    socios=[Socio(nome="Socio A", qualificacao="Socio")],
)
_SEM_PROCESSOS = ConsultaProcessual(
    confirmados=[], referencias=[], status=ConsultaProcessualStatus(status="nao_confirmada")
)


class FakeIdentificationService:
    def __init__(self, result: CompanyIdentificationResult) -> None:
        self._result = result

    async def identify(self, identificador: str) -> CompanyIdentificationResult:
        return self._result


class FakePartnerService:
    async def search(self, company: Company) -> list[Socio]:
        return company.socios


class FakeNewsService:
    async def search(self, company: Company) -> list[Noticia]:
        return []


class FakeSocialMediaService:
    async def search(self, company: Company) -> list[PerfilRedeSocial]:
        return []


class FakeLinkedInService:
    async def search(self, company: Company) -> LinkedInResultado:
        return LinkedInResultado(empresa=None, pessoas_chave=[])


class FakeProcessService:
    async def search(self, company: Company, pessoas: list[str]) -> ConsultaProcessual:
        return _SEM_PROCESSOS


class FakeRelatedCompaniesService:
    def __init__(
        self,
        by_socio: dict[str, list[EmpresaRelacionadaEncontrada]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._by_socio = by_socio or {}
        self._error = error
        self.chamadas: list[list[str]] = []

    async def find_related(self, socios: list[Socio], excluir_cnpj: str | None = None):
        self.chamadas.append([s.nome for s in socios])
        if self._error is not None:
            raise self._error
        encontradas = []
        for socio in socios:
            encontradas.extend(self._by_socio.get(socio.nome, []))
        return [e for e in encontradas if e.empresa.cnpj != excluir_cnpj]


class FakeFamilyRelationshipService:
    def __init__(self, resultado: list[PossivelRelacaoFamiliar] | None = None) -> None:
        self._resultado = resultado or []

    async def find_possible_relations(self, pessoas: list[str]) -> list[PossivelRelacaoFamiliar]:
        return self._resultado


class FakePEPService:
    async def check(self, socio: Socio) -> RegistroPEP:
        return RegistroPEP(
            pessoa=socio.nome,
            status=StatusPEP.NAO_IDENTIFICADA,
            funcao=None,
            orgao=None,
            data_inicio=None,
            data_fim=None,
            data_fim_carencia=None,
            fonte="Portal da Transparencia (CGU)",
            confianca=ConfidenceLevel.BAIXA,
        )


def _use_case(
    empresa: Company,
    related_companies: FakeRelatedCompaniesService | None = None,
    family: FakeFamilyRelationshipService | None = None,
    pep: FakePEPService | None = None,
) -> InvestigarEmpresaUseCase:
    return InvestigarEmpresaUseCase(
        identification_service=FakeIdentificationService(
            CompanyIdentificationResult(empresa=empresa, candidatos=[])
        ),
        partner_service=FakePartnerService(),
        news_service=FakeNewsService(),
        social_media_service=FakeSocialMediaService(),
        linkedin_service=FakeLinkedInService(),
        process_service=FakeProcessService(),
        related_companies_service=related_companies or FakeRelatedCompaniesService(),
        related_people_service=RelatedPeopleService(),
        family_relationship_service=family or FakeFamilyRelationshipService(),
        pep_service=pep or FakePEPService(),
    )


@pytest.mark.asyncio
async def test_raises_when_no_company_is_identified() -> None:
    use_case = InvestigarEmpresaUseCase(
        identification_service=FakeIdentificationService(
            CompanyIdentificationResult(empresa=None, candidatos=[])
        ),
        partner_service=FakePartnerService(),
        news_service=FakeNewsService(),
        social_media_service=FakeSocialMediaService(),
        linkedin_service=FakeLinkedInService(),
        process_service=FakeProcessService(),
        related_companies_service=FakeRelatedCompaniesService(),
        related_people_service=RelatedPeopleService(),
        family_relationship_service=FakeFamilyRelationshipService(),
        pep_service=FakePEPService(),
    )

    with pytest.raises(CompanyNotFoundError):
        await use_case.execute("Empresa Que Nao Existe")


@pytest.mark.asyncio
async def test_depth_zero_does_not_expand_the_network() -> None:
    related = FakeRelatedCompaniesService(
        {
            "Socio A": [
                EmpresaRelacionadaEncontrada(
                    empresa=_EMPRESA_B,
                    origem_socio="Socio A",
                    participacao="atual",
                    fonte="serper",
                    confianca=ConfidenceLevel.MEDIA,
                )
            ]
        }
    )
    use_case = _use_case(_EMPRESA_A, related_companies=related)

    resultado = await use_case.execute("11.444.777/0001-61", depth=0)

    assert resultado.empresas_relacionadas == []
    assert related.chamadas == []


@pytest.mark.asyncio
async def test_depth_one_expands_once_but_not_further() -> None:
    related = FakeRelatedCompaniesService(
        {
            "Socio A": [
                EmpresaRelacionadaEncontrada(
                    empresa=_EMPRESA_B,
                    origem_socio="Socio A",
                    participacao="atual",
                    fonte="serper",
                    confianca=ConfidenceLevel.MEDIA,
                )
            ]
        }
    )
    use_case = _use_case(_EMPRESA_A, related_companies=related)

    resultado = await use_case.execute("11.444.777/0001-61", depth=1)

    assert len(resultado.empresas_relacionadas) == 1
    relacionada = resultado.empresas_relacionadas[0]
    assert relacionada.empresa == _EMPRESA_B
    assert relacionada.investigacao.empresas_relacionadas == []
    # find_related foi chamado para a empresa principal e nao de novo para a B
    assert len(related.chamadas) == 1


@pytest.mark.asyncio
async def test_cycle_is_not_followed_back_to_the_original_company() -> None:
    related = FakeRelatedCompaniesService(
        {
            "Socio A": [
                EmpresaRelacionadaEncontrada(
                    empresa=_EMPRESA_B,
                    origem_socio="Socio A",
                    participacao="atual",
                    fonte="serper",
                    confianca=ConfidenceLevel.MEDIA,
                ),
                EmpresaRelacionadaEncontrada(
                    empresa=_EMPRESA_A,
                    origem_socio="Socio A",
                    participacao="atual",
                    fonte="serper",
                    confianca=ConfidenceLevel.MEDIA,
                ),
            ]
        }
    )
    use_case = _use_case(_EMPRESA_A, related_companies=related)

    resultado = await use_case.execute("11.444.777/0001-61", depth=1)

    cnpjs_relacionados = {r.empresa.cnpj for r in resultado.empresas_relacionadas}
    assert cnpjs_relacionados == {"11222333000181"}


@pytest.mark.asyncio
async def test_shared_related_company_appears_once_with_two_relationships() -> None:
    empresa_com_dois_socios = Company(
        cnpj="11444777000161",
        razao_social="Empresa A LTDA",
        nome_fantasia="Empresa A",
        situacao="ATIVA",
        socios=[
            Socio(nome="Socio A", qualificacao="Socio"),
            Socio(nome="Socio B", qualificacao="Socio"),
        ],
    )
    encontrada_b = EmpresaRelacionadaEncontrada(
        empresa=_EMPRESA_B,
        origem_socio="Socio A",
        participacao="atual",
        fonte="serper",
        confianca=ConfidenceLevel.MEDIA,
    )
    related = FakeRelatedCompaniesService(
        {
            "Socio A": [encontrada_b],
            "Socio B": [
                EmpresaRelacionadaEncontrada(
                    empresa=_EMPRESA_B,
                    origem_socio="Socio B",
                    participacao="atual",
                    fonte="serper",
                    confianca=ConfidenceLevel.MEDIA,
                )
            ],
        }
    )
    use_case = _use_case(empresa_com_dois_socios, related_companies=related)

    resultado = await use_case.execute("11.444.777/0001-61", depth=1)

    assert len(resultado.empresas_relacionadas) == 1
    socio_de_edges = [r for r in resultado.relacionamentos if r.tipo_relacionamento == "socio_de"]
    assert {e.origem for e in socio_de_edges} == {"Socio A", "Socio B"}


@pytest.mark.asyncio
async def test_pep_check_runs_for_each_partner() -> None:
    class RecordingPEPService:
        def __init__(self) -> None:
            self.consultados: list[str] = []

        async def check(self, socio: Socio) -> RegistroPEP:
            self.consultados.append(socio.nome)
            return RegistroPEP(
                pessoa=socio.nome,
                status=StatusPEP.NAO_IDENTIFICADA,
                funcao=None,
                orgao=None,
                data_inicio=None,
                data_fim=None,
                data_fim_carencia=None,
                fonte="Portal da Transparencia (CGU)",
                confianca=ConfidenceLevel.BAIXA,
            )

    pep_service = RecordingPEPService()
    use_case = _use_case(_EMPRESA_A, pep=pep_service)

    resultado = await use_case.execute("11.444.777/0001-61", depth=0)

    assert pep_service.consultados == ["Socio A"]
    assert len(resultado.peps) == 1


@pytest.mark.asyncio
async def test_includes_possible_family_relations() -> None:
    empresa_com_dois_socios = Company(
        cnpj="11444777000161",
        razao_social="Empresa A LTDA",
        nome_fantasia="Empresa A",
        situacao="ATIVA",
        socios=[
            Socio(nome="Socio A", qualificacao="Socio"),
            Socio(nome="Outra Pessoa A", qualificacao="Socio"),
        ],
    )
    relacao = PossivelRelacaoFamiliar(
        tipo="similaridade_de_sobrenome",
        pessoas=["Socio A", "Outra Pessoa A"],
        evidencias=["sobrenome em comum: 'A'"],
        confianca=ConfidenceLevel.BAIXA,
    )
    use_case = _use_case(empresa_com_dois_socios, family=FakeFamilyRelationshipService([relacao]))

    resultado = await use_case.execute("11.444.777/0001-61", depth=0)

    assert resultado.possiveis_relacoes_familiares == [relacao]


@pytest.mark.asyncio
async def test_related_companies_failure_is_recorded_without_failing_investigation() -> None:
    use_case = _use_case(
        _EMPRESA_A,
        related_companies=FakeRelatedCompaniesService(error=SearchProviderError("falha")),
    )

    resultado = await use_case.execute("11.444.777/0001-61", depth=1)

    assert resultado.empresas_relacionadas == []
    assert any("empresas relacionadas" in nota.lower() for nota in resultado.limitacoes)
