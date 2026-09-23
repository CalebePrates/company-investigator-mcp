from datetime import UTC, datetime

import pytest

from company_investigator.application.exceptions import InvestigationNotFoundError
from company_investigator.application.services.investigation_storage_service import (
    SECTION_NAMES,
    InvestigationStorageService,
)
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import (
    ConfidenceLevel,
    ConsultaProcessual,
    ConsultaProcessualStatus,
    DadosOficiaisProcesso,
    EmpresaInvestigada,
    EmpresaRelacionada,
    LinkedInResultado,
    Movimento,
    Noticia,
    ProcessoConfirmado,
    ReferenciaProcessual,
)
from company_investigator.domain.entities.socio import Socio
from company_investigator.infrastructure.investigation.in_memory_investigation_store import (
    InMemoryInvestigationStore,
)

_SEM_PROCESSOS = ConsultaProcessual(
    confirmados=[], referencias=[], status=ConsultaProcessualStatus(status="nao_confirmada")
)


def _empresa(cnpj: str, nome: str) -> Company:
    return Company(cnpj=cnpj, razao_social=nome, nome_fantasia=nome, situacao="ATIVA")


def _noticias(n: int, cnpj: str) -> list[Noticia]:
    return [
        Noticia(
            titulo=f"Noticia {i}",
            url=f"https://n.exemplo/{cnpj}/{i}",
            fonte="serper",
            resumo="...",
            consultado_em=datetime.now(UTC),
        )
        for i in range(n)
    ]


def _investigacao_simples(cnpj: str = "11444777000161", noticias: int = 0) -> EmpresaInvestigada:
    return EmpresaInvestigada(
        identificador_usado=cnpj,
        empresa=_empresa(cnpj, "Empresa A"),
        candidatos=[],
        socios=[Socio(nome="Socio A", qualificacao="Socio-Administrador")],
        pessoas_chave=[],
        linkedin=LinkedInResultado(empresa=None, pessoas_chave=[]),
        redes_sociais=[],
        noticias=_noticias(noticias, cnpj),
        contatos=[],
        processos=_SEM_PROCESSOS,
        fontes=[f"https://n.exemplo/{cnpj}/{i}" for i in range(noticias)],
    )


def _investigacao_com_relacionada() -> EmpresaInvestigada:
    relacionada_investigacao = _investigacao_simples(cnpj="11222333000181", noticias=2)
    relacionada = EmpresaRelacionada(
        empresa=_empresa("11222333000181", "Empresa B"),
        origem_socio="Socio A",
        participacao="atual",
        fonte="serper",
        confianca=ConfidenceLevel.MEDIA,
        investigacao=relacionada_investigacao,
    )
    principal = _investigacao_simples(cnpj="11444777000161", noticias=3)
    return EmpresaInvestigada(
        identificador_usado=principal.identificador_usado,
        empresa=principal.empresa,
        candidatos=[],
        socios=principal.socios,
        pessoas_chave=[],
        linkedin=LinkedInResultado(empresa=None, pessoas_chave=[]),
        redes_sociais=[],
        noticias=principal.noticias,
        contatos=[],
        processos=_SEM_PROCESSOS,
        fontes=principal.fontes,
        empresas_relacionadas=[relacionada],
    )


def _service() -> InvestigationStorageService:
    return InvestigationStorageService(store=InMemoryInvestigationStore())


def test_small_investigation_round_trips_through_index_and_sections() -> None:
    service = _service()
    investigacao = _investigacao_simples(noticias=1)

    indice = service.store(investigacao)

    assert indice.empresa == investigacao.empresa
    pagina = service.get_section(indice.investigation_id, "noticias")
    assert pagina.itens == investigacao.noticias


def test_index_does_not_inline_large_list_sections() -> None:
    service = _service()
    investigacao = _investigacao_simples(noticias=500)

    indice = service.store(investigacao)

    secao_noticias = next(s for s in indice.secoes if s.nome == "noticias")
    assert secao_noticias.total_itens == 500
    # o indice em si nao deve carregar os 500 itens - so a contagem
    import json

    from company_investigator.application.services.investigation_storage_service import (
        SecaoResumo,
    )

    assert all(isinstance(s, SecaoResumo) for s in indice.secoes)
    assert json.dumps([s.__dict__ for s in indice.secoes]).count("Noticia ") == 0


def test_no_data_is_lost_across_all_pages_of_a_section() -> None:
    service = _service()
    investigacao = _investigacao_simples(noticias=45)

    indice = service.store(investigacao)

    coletadas: list[Noticia] = []
    pagina_num = 1
    while True:
        pagina = service.get_section(
            indice.investigation_id, "noticias", pagina=pagina_num, tamanho_pagina=20
        )
        coletadas.extend(pagina.itens)
        if pagina_num >= pagina.total_paginas:
            break
        pagina_num += 1

    assert coletadas == investigacao.noticias
    assert len(coletadas) == 45


def test_first_and_last_page_work() -> None:
    service = _service()
    investigacao = _investigacao_simples(noticias=45)
    indice = service.store(investigacao)

    primeira = service.get_section(indice.investigation_id, "noticias", pagina=1, tamanho_pagina=20)
    ultima = service.get_section(indice.investigation_id, "noticias", pagina=3, tamanho_pagina=20)

    assert len(primeira.itens) == 20
    assert primeira.itens[0] == investigacao.noticias[0]
    assert len(ultima.itens) == 5
    assert ultima.itens[-1] == investigacao.noticias[-1]
    assert ultima.total_paginas == 3


def test_pages_do_not_duplicate_items() -> None:
    service = _service()
    investigacao = _investigacao_simples(noticias=45)
    indice = service.store(investigacao)

    pagina1 = service.get_section(indice.investigation_id, "noticias", pagina=1, tamanho_pagina=20)
    pagina2 = service.get_section(indice.investigation_id, "noticias", pagina=2, tamanho_pagina=20)
    pagina3 = service.get_section(indice.investigation_id, "noticias", pagina=3, tamanho_pagina=20)

    urls = [n.url for n in (*pagina1.itens, *pagina2.itens, *pagina3.itens)]
    assert len(urls) == len(set(urls))


def test_all_sections_are_retrievable() -> None:
    service = _service()
    investigacao = _investigacao_com_relacionada()
    indice = service.store(investigacao)

    for secao in [s.nome for s in indice.secoes]:
        pagina = service.get_section(indice.investigation_id, secao)
        assert pagina.secao == secao


def test_related_company_is_referenced_by_id_not_inlined() -> None:
    service = _service()
    investigacao = _investigacao_com_relacionada()
    indice = service.store(investigacao)

    pagina = service.get_section(indice.investigation_id, "empresas_relacionadas")
    assert len(pagina.itens) == 1
    resumo = pagina.itens[0]
    assert resumo.empresa.cnpj == "11222333000181"
    assert resumo.investigation_id != indice.investigation_id


def test_full_investigation_can_be_traversed_including_nested_related_companies() -> None:
    service = _service()
    investigacao = _investigacao_com_relacionada()
    indice = service.store(investigacao)

    relacionadas = service.get_section(indice.investigation_id, "empresas_relacionadas").itens
    nested_id = relacionadas[0].investigation_id

    nested_index = service.get_index(nested_id)
    nested_noticias = service.get_section(nested_id, "noticias").itens

    assert nested_index.empresa.cnpj == "11222333000181"
    assert len(nested_noticias) == 2


def test_entities_keep_their_source_and_url_fields() -> None:
    service = _service()
    investigacao = _investigacao_simples(noticias=3)
    indice = service.store(investigacao)

    pagina = service.get_section(indice.investigation_id, "noticias")
    for noticia in pagina.itens:
        assert noticia.fonte == "serper"
        assert noticia.url.startswith("https://n.exemplo/")


def test_different_investigations_do_not_mix_data() -> None:
    service = _service()
    indice_a = service.store(_investigacao_simples(cnpj="11444777000161", noticias=2))
    indice_b = service.store(_investigacao_simples(cnpj="11222333000181", noticias=5))

    noticias_a = service.get_section(indice_a.investigation_id, "noticias").itens
    noticias_b = service.get_section(indice_b.investigation_id, "noticias").itens

    assert len(noticias_a) == 2
    assert len(noticias_b) == 5
    assert {n.url for n in noticias_a}.isdisjoint({n.url for n in noticias_b})


def test_get_index_raises_for_unknown_investigation_id() -> None:
    service = _service()

    with pytest.raises(InvestigationNotFoundError):
        service.get_index("does-not-exist")


def test_get_section_raises_for_unknown_investigation_id() -> None:
    service = _service()

    with pytest.raises(InvestigationNotFoundError):
        service.get_section("does-not-exist", "noticias")


def test_get_section_raises_for_unknown_section_name() -> None:
    service = _service()
    indice = service.store(_investigacao_simples())

    with pytest.raises(ValueError):
        service.get_section(indice.investigation_id, "secao_que_nao_existe")


def test_object_sections_are_returned_as_a_single_item_page() -> None:
    service = _service()
    indice = service.store(_investigacao_simples())

    pagina = service.get_section(indice.investigation_id, "empresa")

    assert pagina.total_paginas == 1
    assert len(pagina.itens) == 1
    assert pagina.itens[0].cnpj == "11444777000161"


def test_service_keeps_no_state_of_its_own_a_second_service_sees_the_same_tree() -> None:
    store = InMemoryInvestigationStore()
    indice = InvestigationStorageService(store=store).store(_investigacao_com_relacionada())

    outro_servico = InvestigationStorageService(store=store)
    relacionadas = outro_servico.get_section(indice.investigation_id, "empresas_relacionadas")

    assert [r.empresa.cnpj for r in relacionadas.itens] == ["11222333000181"]
    assert outro_servico.get_index(relacionadas.itens[0].investigation_id).empresa is not None


def test_evicting_a_tree_makes_root_and_children_equally_not_found() -> None:
    service = InvestigationStorageService(store=InMemoryInvestigationStore(max_entries=2))
    raiz = service.store(_investigacao_com_relacionada())
    filho_id = (
        service.get_section(raiz.investigation_id, "empresas_relacionadas")
        .itens[0]
        .investigation_id
    )

    service.store(_investigacao_simples(cnpj="11555666000122"))  # empurra a arvore antiga

    with pytest.raises(InvestigationNotFoundError):
        service.get_index(raiz.investigation_id)
    with pytest.raises(InvestigationNotFoundError):
        service.get_index(filho_id)


def _processo_com_movimentos(numero: str, total: int) -> ProcessoConfirmado:
    dados = DadosOficiaisProcesso(
        numero_processo=numero,
        tribunal="TJSP",
        grau="G1",
        orgao_julgador=None,
        classe="Procedimento Comum Civel",
        assuntos=["Rescisao"],
        movimentos=[
            Movimento(nome=f"Movimento {i}", data="2020-05-20T10:00:00Z") for i in range(total)
        ],
        data_ajuizamento=None,
        sistema="PJe",
        fonte="DataJud (CNJ)",
        consultado_em=datetime.now(UTC),
    )
    origem = ReferenciaProcessual(
        titulo="ref",
        url=f"https://ref.exemplo/{numero}",
        fonte="serper",
        resumo="...",
        consultado_em=datetime.now(UTC),
        relacionado_a="Empresa A",
        tipo_relacionado="empresa",
        numero_processo_detectado=numero,
    )
    return ProcessoConfirmado(
        dados=dados,
        relacionado_a="Empresa A",
        tipo_relacionado="empresa",
        confianca=ConfidenceLevel.BAIXA,
        origem=origem,
    )


def _investigacao_com_processos(processos: list[ProcessoConfirmado]) -> EmpresaInvestigada:
    base = _investigacao_simples()
    return EmpresaInvestigada(
        identificador_usado=base.identificador_usado,
        empresa=base.empresa,
        candidatos=[],
        socios=[],
        pessoas_chave=[],
        linkedin=base.linkedin,
        redes_sociais=[],
        noticias=[],
        contatos=[],
        processos=ConsultaProcessual(
            confirmados=processos,
            referencias=[],
            status=ConsultaProcessualStatus(status="realizada"),
        ),
        fontes=[],
    )


def test_process_movements_are_a_flat_paginated_section_that_loses_nothing() -> None:
    service = _service()
    processos = [
        _processo_com_movimentos("00000000000000000001", 1200),
        _processo_com_movimentos("00000000000000000002", 3),
    ]
    indice = service.store(_investigacao_com_processos(processos))

    resumo = next(s for s in indice.secoes if s.nome == "movimentos_processuais")
    assert resumo.total_itens == 1203

    coletados: list = []
    pagina_num = 1
    while True:
        pagina = service.get_section(
            indice.investigation_id, "movimentos_processuais", pagina_num, tamanho_pagina=50
        )
        assert len(pagina.itens) <= 50
        coletados.extend(pagina.itens)
        if pagina_num >= pagina.total_paginas:
            break
        pagina_num += 1

    assert len(coletados) == 1203
    assert [m.numero_processo for m in coletados[:1200]] == ["00000000000000000001"] * 1200
    assert [m.numero_processo for m in coletados[1200:]] == ["00000000000000000002"] * 3
    assert coletados[0].nome == "Movimento 0"
    assert coletados[0].data == "2020-05-20T10:00:00Z"


def test_section_names_are_the_single_source_of_truth_for_the_index_and_get_section() -> None:
    service = _service()
    indice = service.store(_investigacao_com_relacionada())

    for nome in SECTION_NAMES:
        assert service.get_section(indice.investigation_id, nome).secao == nome
    # toda secao anunciada no indice e aceita por get_section
    assert {s.nome for s in indice.secoes} <= set(SECTION_NAMES)
    # (processos_status e um objeto pequeno que ja vem inteiro no indice)
    assert set(SECTION_NAMES) - {s.nome for s in indice.secoes} == {"empresa", "processos_status"}


def test_page_beyond_the_last_returns_empty_items_but_correct_totals() -> None:
    service = _service()
    indice = service.store(_investigacao_simples(noticias=45))

    pagina = service.get_section(indice.investigation_id, "noticias", pagina=99, tamanho_pagina=20)

    assert pagina.itens == []
    assert pagina.total_itens == 45
    assert pagina.total_paginas == 3


def test_empty_section_is_one_empty_page() -> None:
    service = _service()
    indice = service.store(_investigacao_simples(noticias=0))

    pagina = service.get_section(indice.investigation_id, "noticias")

    assert pagina.itens == []
    assert pagina.total_itens == 0
    assert pagina.total_paginas == 1


def test_unknown_section_error_lists_the_valid_sections() -> None:
    service = _service()
    indice = service.store(_investigacao_simples())

    with pytest.raises(ValueError, match="Secoes validas:.*noticias.*movimentos_processuais"):
        service.get_section(indice.investigation_id, "Noticias")
