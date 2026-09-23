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
