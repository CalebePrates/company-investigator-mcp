from abc import ABC, abstractmethod
from dataclasses import dataclass


class PEPLookupError(Exception):
    """Falha de infraestrutura ao consultar a fonte oficial de PEPs (timeout, HTTP,
    autenticacao invalida, ou resposta em formato inesperado)."""


@dataclass(frozen=True)
class RegistroPEPBruto:
    """Um registro cru, como a fonte oficial devolve (sem nenhuma decisao de
    confianca/homonimo - isso e responsabilidade do PEPService)."""

    cpf: str | None
    nome: str
    funcao: str | None
    orgao: str | None
    data_inicio: str | None
    data_fim: str | None
    data_fim_carencia: str | None


class PEPLookupPort(ABC):
    """Capacidade de consultar o cadastro oficial de Pessoas Expostas Politicamente
    por nome (e, quando disponivel, CPF)."""

    @abstractmethod
    async def search(self, nome: str, cpf: str | None = None) -> list[RegistroPEPBruto]: ...
