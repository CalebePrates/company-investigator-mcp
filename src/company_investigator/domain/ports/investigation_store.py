from abc import ABC, abstractmethod
from collections.abc import Sequence

from company_investigator.domain.entities.investigation import EmpresaInvestigada


class InvestigationStorePort(ABC):
    """Guarda investigacoes completas na memoria do processo do servidor, pelo
    tempo de vida da sessao MCP - nunca em banco de dados ou outra persistencia
    permanente. Existe para separar a COLETA (InvestigarEmpresaUseCase, que
    continua produzindo a EmpresaInvestigada inteira, sem perda) da EXPOSICAO
    (que precisa entregar isso em pedacos menores que um cliente MCP aceite).

    Uma investigacao com empresas relacionadas e guardada como uma ARVORE de
    registros: cada empresa relacionada e uma investigacao propria, ligada a
    quem a originou por `related_ids`. Uma arvore vive e morre inteira."""

    @abstractmethod
    def save(self, investigation: EmpresaInvestigada, related_ids: Sequence[str] = ()) -> str:
        """Guarda a investigacao e devolve um novo investigation_id (UUID).
        `related_ids` sao os ids (ja guardados) das sub-investigacoes das
        `empresas_relacionadas`, na mesma ordem em que aparecem nela."""
        ...

    @abstractmethod
    def get(self, investigation_id: str) -> EmpresaInvestigada | None:
        """Devolve a investigacao completa e original, ou None se o id nao existir
        (ou tiver sido descartado por limite de capacidade)."""
        ...

    @abstractmethod
    def get_related_ids(self, investigation_id: str) -> list[str]:
        """Devolve os ids das sub-investigacoes guardadas junto com esta (lista
        vazia se nao tiver nenhuma ou se o id nao existir)."""
        ...
