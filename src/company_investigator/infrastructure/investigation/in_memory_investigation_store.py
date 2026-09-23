import uuid
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass

from company_investigator.domain.entities.investigation import EmpresaInvestigada
from company_investigator.domain.ports.investigation_store import InvestigationStorePort

_DEFAULT_MAX_ENTRIES = 500


@dataclass(frozen=True)
class _Entry:
    investigation: EmpresaInvestigada
    related_ids: tuple[str, ...]


class InMemoryInvestigationStore(InvestigationStorePort):
    """Armazenamento em memoria, limitado, isolado por instancia (uma por
    servidor). O limite conta REGISTROS, e o descarte e sempre de uma arvore
    inteira (a raiz menos recentemente usada e todas as suas sub-investigacoes),
    nunca de um no solto - assim um id vivo nunca aponta para filhos que sumiram.
    Ler qualquer no conta como usar a arvore toda, e a arvore recem-guardada nunca
    e descartada, mesmo que sozinha exceda o limite."""

    def __init__(self, max_entries: int = _DEFAULT_MAX_ENTRIES) -> None:
        self._max_entries = max_entries
        self._entries: dict[str, _Entry] = {}
        self._parents: dict[str, str] = {}
        self._roots: OrderedDict[str, None] = OrderedDict()

    def save(self, investigation: EmpresaInvestigada, related_ids: Sequence[str] = ()) -> str:
        investigation_id = uuid.uuid4().hex
        self._entries[investigation_id] = _Entry(investigation, tuple(related_ids))
        for child_id in related_ids:
            self._parents[child_id] = investigation_id
            self._roots.pop(child_id, None)
        self._roots[investigation_id] = None
        self._evict_while_over_capacity()
        return investigation_id

    def get(self, investigation_id: str) -> EmpresaInvestigada | None:
        entry = self._entries.get(investigation_id)
        if entry is None:
            return None
        self._roots.move_to_end(self._root_of(investigation_id))
        return entry.investigation

    def get_related_ids(self, investigation_id: str) -> list[str]:
        entry = self._entries.get(investigation_id)
        return list(entry.related_ids) if entry else []

    def _root_of(self, investigation_id: str) -> str:
        while investigation_id in self._parents:
            investigation_id = self._parents[investigation_id]
        return investigation_id

    def _evict_while_over_capacity(self) -> None:
        while len(self._entries) > self._max_entries and len(self._roots) > 1:
            oldest_root, _ = self._roots.popitem(last=False)
            self._remove_tree(oldest_root)

    def _remove_tree(self, root_id: str) -> None:
        pending = [root_id]
        while pending:
            current = pending.pop()
            entry = self._entries.pop(current, None)
            self._parents.pop(current, None)
            if entry:
                pending.extend(entry.related_ids)
