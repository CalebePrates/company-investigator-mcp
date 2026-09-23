from datetime import UTC, datetime

from company_investigator.application.services.related_people_service import RelatedPeopleService
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import (
    ConfidenceLevel,
    ConsultaProcessual,
    ConsultaProcessualStatus,
    EmpresaInvestigada,
    EmpresaRelacionada,
    LinkedInResultado,
    PessoaChave,
)
from company_investigator.domain.entities.socio import Socio

_SEM_PROCESSOS = ConsultaProcessual(
    confirmados=[], referencias=[], status=ConsultaProcessualStatus(status="nao_confirmada")
)
_EMPRESA_B = Company(
    cnpj="11444777000161",
    razao_social="Empresa B LTDA",
    nome_fantasia="Empresa B",
    situacao="ATIVA",
)


def _relacionada(socios: list[Socio], pessoas_chave: list[PessoaChave]) -> EmpresaRelacionada:
    investigacao = EmpresaInvestigada(
        identificador_usado="11444777000161",
        empresa=_EMPRESA_B,
        candidatos=[],
        socios=socios,
        pessoas_chave=pessoas_chave,
        linkedin=LinkedInResultado(empresa=None, pessoas_chave=pessoas_chave),
        redes_sociais=[],
        noticias=[],
        contatos=[],
        processos=_SEM_PROCESSOS,
        fontes=[],
    )
    return EmpresaRelacionada(
        empresa=_EMPRESA_B,
        origem_socio="Socio A",
        participacao="atual",
        fonte="serper",
        confianca=ConfidenceLevel.MEDIA,
        investigacao=investigacao,
    )


def test_collects_partners_from_related_companies() -> None:
    relacionada = _relacionada([Socio(nome="Fulano", qualificacao="Socio")], [])
    service = RelatedPeopleService()

    pessoas = service.collect([relacionada])

    assert len(pessoas) == 1
    assert pessoas[0].nome == "Fulano"
    assert pessoas[0].empresa_relacionada == "Empresa B"


def test_collects_key_people_from_related_companies() -> None:
    pessoa_chave = PessoaChave(
        nome="Ciclana",
        cargo="CEO",
        empresa_relacionada="Empresa B",
        url_linkedin="https://linkedin.com/in/ciclana",
        tipo_cargo="CEO",
        confianca=ConfidenceLevel.MEDIA,
        fontes=["https://linkedin.com/in/ciclana"],
        consultado_em=datetime.now(UTC),
    )
    relacionada = _relacionada([], [pessoa_chave])
    service = RelatedPeopleService()

    pessoas = service.collect([relacionada])

    assert any(p.nome == "Ciclana" and p.papel == "CEO" for p in pessoas)


def test_deduplicates_the_same_person_in_the_same_company() -> None:
    relacionada = _relacionada([Socio(nome="Fulano", qualificacao="Socio")], [])
    service = RelatedPeopleService()

    pessoas = service.collect([relacionada, relacionada])

    assert len(pessoas) == 1
