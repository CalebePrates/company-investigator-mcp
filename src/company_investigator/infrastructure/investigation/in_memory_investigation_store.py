import uuid
from collections import OrderedDict

from company_investigator.domain.entities.investigation import EmpresaInvestigada
from company_investigator.domain.ports.investigation_store import InvestigationStorePort

_DEFAULT_MAX_ENTRIES = 200


class InMemoryInvestigationStore(InvestigationStorePort):
    """Guarda investigacoes na memoria deste processo, pelo tempo de vida da
    sessao MCP - nunca em disco ou banco de dados. Limitado a `max_entries`
    (descartando a mais antiga) para nao crescer sem limite numa sessao longa;
    isso e uma protecao operacional, nao uma forma de descartar dados de uma
    investigacao que ainda esta em uso."""

    def __init__(self, max_entries: int = _DEFAULT_MAX_ENTRIES) -> None:
        self._max_entries = max_entries
        self._entries: OrderedDict[str, EmpresaInvestigada] = OrderedDict()

    def save(self, investigation: EmpresaInvestigada) -> str:
        investigation_id = uuid.uuid4().hex
        self._entries[investigation_id] = investigation
        if len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
        return investigation_id

    def get(self, investigation_id: str) -> EmpresaInvestigada | None:
        return self._entries.get(investigation_id)
