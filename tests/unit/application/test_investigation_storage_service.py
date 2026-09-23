from datetime import UTC, datetime

import pytest

from company_investigator.application.exceptions import InvestigationNotFoundError
from company_investigator.application.services.investigation_storage_service import (
    InvestigationStorageService,
)
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import (
    ConfidenceLevel,
    ConsultaProcessual,
    ConsultaProcessualStatus,
    EmpresaInvestigada,
    EmpresaRelacionada,
    LinkedInResultado,
    Noticia,
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
