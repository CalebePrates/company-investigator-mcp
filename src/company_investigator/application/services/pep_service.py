from company_investigator.domain.entities.investigation import (
    ConfidenceLevel,
    RegistroPEP,
    StatusPEP,
)
from company_investigator.domain.entities.socio import Socio
from company_investigator.domain.ports.pep_lookup import (
    PEPLookupError,
    PEPLookupPort,
    RegistroPEPBruto,
)

_FONTE = "Portal da Transparencia (CGU)"


class PEPService:
    """Verifica se um socio consta no cadastro oficial de Pessoas Expostas
    Politicamente. Uma correspondencia de nome sozinha NUNCA vira PEP_CONFIRMADA -
    isso exige que os digitos visiveis do CPF mascarado do socio (vindo da
    BrasilAPI) batam com os do registro oficial retornado."""

    def __init__(self, pep_lookup: PEPLookupPort | None) -> None:
        self._pep_lookup = pep_lookup

    async def check(self, socio: Socio) -> RegistroPEP:
        if self._pep_lookup is None:
            return self._resultado(socio, StatusPEP.NAO_FOI_POSSIVEL_VERIFICAR, None)

        try:
            registros = await self._pep_lookup.search(socio.nome, cpf=socio.documento)
        except PEPLookupError:
            return self._resultado(socio, StatusPEP.NAO_FOI_POSSIVEL_VERIFICAR, None)

        if not registros:
            return self._resultado(socio, StatusPEP.NAO_IDENTIFICADA, None)

        confirmado = self._encontrar_por_documento(socio, registros)
        if confirmado is not None:
            return self._resultado(socio, StatusPEP.PEP_CONFIRMADA, confirmado)

        return self._resultado(socio, StatusPEP.POSSIVEL_HOMONIMO, registros[0])

    def _encontrar_por_documento(
        self, socio: Socio, registros: list[RegistroPEPBruto]
    ) -> RegistroPEPBruto | None:
        if not socio.documento:
            return None
        for registro in registros:
            if registro.cpf and _masked_cpf_matches(socio.documento, registro.cpf):
                return registro
        return None

    def _resultado(
        self, socio: Socio, status: StatusPEP, registro: RegistroPEPBruto | None
    ) -> RegistroPEP:
        confianca = (
            ConfidenceLevel.ALTA if status == StatusPEP.PEP_CONFIRMADA else ConfidenceLevel.BAIXA
        )
        return RegistroPEP(
            pessoa=socio.nome,
            status=status,
            funcao=registro.funcao if registro else None,
            orgao=registro.orgao if registro else None,
            data_inicio=registro.data_inicio if registro else None,
            data_fim=registro.data_fim if registro else None,
            data_fim_carencia=registro.data_fim_carencia if registro else None,
            fonte=_FONTE,
            confianca=confianca,
        )


def _masked_cpf_matches(a: str, b: str) -> bool:
    """Compara dois CPFs mascarados posicao a posicao: exige que todo digito
    visivel em ambos coincida, e que exista pelo menos um digito comparavel
    (evita 'combinar' dois CPFs totalmente mascarados)."""
    if len(a) != len(b):
        return False

    comparable = False
    for char_a, char_b in zip(a, b, strict=True):
        if char_a.isdigit() and char_b.isdigit():
            comparable = True
            if char_a != char_b:
                return False
    return comparable
