import pytest

from company_investigator.application.services.pep_service import PEPService
from company_investigator.domain.entities.investigation import StatusPEP
from company_investigator.domain.entities.socio import Socio
from company_investigator.domain.ports.pep_lookup import (
    PEPLookupError,
    PEPLookupPort,
    RegistroPEPBruto,
)

_SOCIO_COM_DOCUMENTO = Socio(nome="Fulano de Tal", qualificacao="Socio", documento="***112108**")
_SOCIO_SEM_DOCUMENTO = Socio(nome="Fulano de Tal", qualificacao="Socio", documento=None)


class FakePEPLookup(PEPLookupPort):
    def __init__(self, registros: list[RegistroPEPBruto] | None = None, error=None) -> None:
        self._registros = registros or []
        self._error = error

    async def search(self, nome: str, cpf: str | None = None) -> list[RegistroPEPBruto]:
        if self._error is not None:
            raise self._error
        return self._registros


@pytest.mark.asyncio
async def test_confirms_pep_when_masked_cpf_matches() -> None:
    lookup = FakePEPLookup(
        [
            RegistroPEPBruto(
                cpf="***112108**",
                nome="Fulano de Tal",
                funcao="Ministro",
                orgao="Ministerio Exemplo",
                data_inicio="01/01/2020",
                data_fim=None,
                data_fim_carencia=None,
            )
        ]
    )
    service = PEPService(pep_lookup=lookup)

    registro = await service.check(_SOCIO_COM_DOCUMENTO)

    assert registro.status == StatusPEP.PEP_CONFIRMADA
    assert registro.funcao == "Ministro"


@pytest.mark.asyncio
async def test_possible_homonym_when_name_matches_but_no_document_to_compare() -> None:
    lookup = FakePEPLookup(
        [
            RegistroPEPBruto(
                cpf="***999999**",
                nome="Fulano de Tal",
                funcao="Ministro",
                orgao="Ministerio Exemplo",
                data_inicio="01/01/2020",
                data_fim=None,
                data_fim_carencia=None,
            )
        ]
    )
    service = PEPService(pep_lookup=lookup)

    registro = await service.check(_SOCIO_SEM_DOCUMENTO)

    assert registro.status == StatusPEP.POSSIVEL_HOMONIMO


@pytest.mark.asyncio
async def test_possible_homonym_when_masked_cpf_does_not_match() -> None:
    lookup = FakePEPLookup(
        [
            RegistroPEPBruto(
                cpf="***999999**",
                nome="Fulano de Tal",
                funcao="Ministro",
                orgao="Ministerio Exemplo",
                data_inicio=None,
                data_fim=None,
                data_fim_carencia=None,
            )
        ]
    )
    service = PEPService(pep_lookup=lookup)

    registro = await service.check(_SOCIO_COM_DOCUMENTO)

    assert registro.status == StatusPEP.POSSIVEL_HOMONIMO


@pytest.mark.asyncio
async def test_not_identified_when_no_results() -> None:
    service = PEPService(pep_lookup=FakePEPLookup([]))

    registro = await service.check(_SOCIO_COM_DOCUMENTO)

    assert registro.status == StatusPEP.NAO_IDENTIFICADA


@pytest.mark.asyncio
async def test_could_not_verify_when_lookup_fails() -> None:
    service = PEPService(pep_lookup=FakePEPLookup(error=PEPLookupError("falha")))

    registro = await service.check(_SOCIO_COM_DOCUMENTO)

    assert registro.status == StatusPEP.NAO_FOI_POSSIVEL_VERIFICAR


@pytest.mark.asyncio
async def test_could_not_verify_when_lookup_not_configured() -> None:
    service = PEPService(pep_lookup=None)

    registro = await service.check(_SOCIO_COM_DOCUMENTO)

    assert registro.status == StatusPEP.NAO_FOI_POSSIVEL_VERIFICAR
