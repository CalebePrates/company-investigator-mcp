from abc import ABC, abstractmethod

from company_investigator.domain.entities.investigation import DadosOficiaisProcesso


class ProcessLookupError(Exception):
    """Falha de infraestrutura ao consultar uma fonte oficial de processos por
    numero (timeout, HTTP, autenticacao invalida, resposta inesperada, ou numero/
    tribunal fora do que a fonte consegue resolver)."""


class ProcessNumberLookupPort(ABC):
    """Capacidade de confirmar um processo a partir do seu numero oficial (padrao
    CNJ). Deliberadamente NAO inclui busca por CNPJ/CPF/nome: nenhuma fonte oficial,
    publica e sem CAPTCHA disponivel atualmente oferece essa capacidade (ver
    ProcessSearchService). Uma futura fonte com uma capacidade diferente teria seu
    proprio port pequeno, em vez de forcar esta interface a crescer (ISP)."""

    @abstractmethod
    async def find_by_number(self, numero_processo: str) -> DadosOficiaisProcesso | None: ...
