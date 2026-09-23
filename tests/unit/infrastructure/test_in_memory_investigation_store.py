from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import (
    ConsultaProcessual,
    ConsultaProcessualStatus,
    EmpresaInvestigada,
    LinkedInResultado,
)
from company_investigator.infrastructure.investigation.in_memory_investigation_store import (
    InMemoryInvestigationStore,
)

_SEM_PROCESSOS = ConsultaProcessual(
    confirmados=[], referencias=[], status=ConsultaProcessualStatus(status="nao_confirmada")
)


def _investigacao(identificador: str) -> EmpresaInvestigada:
    empresa = Company(
        cnpj=identificador,
        razao_social=f"Empresa {identificador}",
        nome_fantasia="",
        situacao="ATIVA",
    )
    return EmpresaInvestigada(
        identificador_usado=identificador,
        empresa=empresa,
        candidatos=[],
        socios=[],
        pessoas_chave=[],
        linkedin=LinkedInResultado(empresa=None, pessoas_chave=[]),
        redes_sociais=[],
        noticias=[],
        contatos=[],
        processos=_SEM_PROCESSOS,
        fontes=[],
    )


def test_save_returns_a_usable_id_and_get_retrieves_it() -> None:
    store = InMemoryInvestigationStore()
    investigacao = _investigacao("A")

    investigation_id = store.save(investigacao)

    assert store.get(investigation_id) == investigacao


def test_get_returns_none_for_an_unknown_id() -> None:
    store = InMemoryInvestigationStore()

    assert store.get("does-not-exist") is None


def test_two_saved_investigations_stay_isolated() -> None:
    store = InMemoryInvestigationStore()
    id_a = store.save(_investigacao("A"))
    id_b = store.save(_investigacao("B"))

    assert store.get(id_a).identificador_usado == "A"
    assert store.get(id_b).identificador_usado == "B"
    assert id_a != id_b


def test_saving_twice_returns_different_ids() -> None:
    store = InMemoryInvestigationStore()
    investigacao = _investigacao("A")

    id_1 = store.save(investigacao)
    id_2 = store.save(investigacao)

    assert id_1 != id_2


def test_bounded_capacity_evicts_the_oldest_entry() -> None:
    store = InMemoryInvestigationStore(max_entries=2)

    id_1 = store.save(_investigacao("A"))
    id_2 = store.save(_investigacao("B"))
    id_3 = store.save(_investigacao("C"))

    assert store.get(id_1) is None
    assert store.get(id_2) is not None
    assert store.get(id_3) is not None


def test_related_ids_are_stored_and_returned_with_the_investigation() -> None:
    store = InMemoryInvestigationStore()
    child_id = store.save(_investigacao("child"))

    parent_id = store.save(_investigacao("parent"), related_ids=[child_id])

    assert store.get_related_ids(parent_id) == [child_id]
    assert store.get_related_ids(child_id) == []


def test_get_related_ids_is_empty_for_an_unknown_id() -> None:
    store = InMemoryInvestigationStore()

    assert store.get_related_ids("does-not-exist") == []


def test_eviction_removes_a_whole_tree_never_a_single_node() -> None:
    store = InMemoryInvestigationStore(max_entries=3)
    child_id = store.save(_investigacao("child"))
    parent_id = store.save(_investigacao("parent"), related_ids=[child_id])
    alone_id = store.save(_investigacao("alone"))

    newest_id = store.save(_investigacao("newest"))  # 4 entries > 3: oldest TREE goes

    assert store.get(parent_id) is None
    assert store.get(child_id) is None
    assert store.get(alone_id) is not None
    assert store.get(newest_id) is not None


def test_reading_any_node_protects_its_whole_tree_from_eviction() -> None:
    store = InMemoryInvestigationStore(max_entries=3)
    child_id = store.save(_investigacao("child"))
    parent_id = store.save(_investigacao("parent"), related_ids=[child_id])
    alone_id = store.save(_investigacao("alone"))

    store.get(child_id)  # the tree of `parent` is now the most recently used
    store.save(_investigacao("newest"))

    assert store.get(alone_id) is None
    assert store.get(parent_id) is not None
    assert store.get(child_id) is not None


def test_the_tree_just_saved_is_never_evicted_even_if_it_alone_exceeds_capacity() -> None:
    store = InMemoryInvestigationStore(max_entries=1)
    child_id = store.save(_investigacao("child"))
    parent_id = store.save(_investigacao("parent"), related_ids=[child_id])

    assert store.get(parent_id) is not None
    assert store.get(child_id) is not None
