from abc import ABC, abstractmethod

from company_investigator.domain.entities.investigation import EmpresaInvestigada


class InvestigationStorePort(ABC):
    """Guarda investigacoes completas na memoria do processo do servidor, pelo
    tempo de vida da sessao MCP - nunca em banco de dados ou outra persistencia
    permanente. Existe para separar a COLETA (InvestigarEmpresaUseCase, que
    continua produzindo a EmpresaInvestigada inteira, sem perda) da EXPOSICAO
    (que precisa entregar isso em pedacos menores que um cliente MCP aceite)."""

    @abstractmethod
    def save(self, investigation: EmpresaInvestigada) -> str:
        """Guarda a investigacao e devolve um novo investigation_id (UUID)."""
        ...

    @abstractmethod
    def get(self, investigation_id: str) -> EmpresaInvestigada | None:
        """Devolve a investigacao completa e original, ou None se o id nao existir
        (ou tiver sido descartado por limite de capacidade)."""
        ...
