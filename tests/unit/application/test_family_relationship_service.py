import pytest

from company_investigator.application.services.family_relationship_service import (
    FamilyRelationshipService,
)
from company_investigator.domain.entities.investigation import ConfidenceLevel
from company_investigator.domain.entities.search_result import SearchResult
from company_investigator.domain.ports.search_provider import SearchProviderPort


class FakeSearchProvider(SearchProviderPort):
    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self._results = results or []
        self.queries: list[str] = []

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        self.queries.append(query)
        return self._results


@pytest.mark.asyncio
async def test_common_surname_yields_low_confidence_similarity_only() -> None:
    service = FamilyRelationshipService(search_provider=FakeSearchProvider([]))

    relacoes = await service.find_possible_relations(["Joana Silva", "Carlos Silva"])

    assert len(relacoes) == 1
    assert relacoes[0].tipo == "similaridade_de_sobrenome"
    assert relacoes[0].confianca == ConfidenceLevel.BAIXA
    assert set(relacoes[0].pessoas) == {"Joana Silva", "Carlos Silva"}


@pytest.mark.asyncio
async def test_compound_surname_shared_in_the_middle_of_the_name_is_detected() -> None:
    # Nomes brasileiros empilham sobrenomes; o sobrenome compartilhado nem sempre
    # e o ultimo token de ambos os nomes.
    service = FamilyRelationshipService(search_provider=FakeSearchProvider([]))

    relacoes = await service.find_possible_relations(
        ["Guilherme Medeiros Ribeiro", "Priscila Medeiros Ribeiro Pimenta"]
    )

    assert len(relacoes) == 1
    assert relacoes[0].tipo == "similaridade_de_sobrenome"


@pytest.mark.asyncio
async def test_different_surnames_yield_no_relation() -> None:
    service = FamilyRelationshipService(search_provider=FakeSearchProvider([]))

    relacoes = await service.find_possible_relations(["Joana Silva", "Carlos Souza"])

    assert relacoes == []


@pytest.mark.asyncio
async def test_explicitly_declared_family_relation_found_in_source() -> None:
    resultado = SearchResult(
        title="Joana Silva e sua irma Carla Silva",
        url="https://noticia.exemplo/1",
        snippet="Joana Silva, irmã de Carla Silva, assumiu a diretoria...",
        source="serper",
    )
    service = FamilyRelationshipService(search_provider=FakeSearchProvider([resultado]))

    relacoes = await service.find_possible_relations(["Joana Silva", "Carla Silva"])

    declarada = next(r for r in relacoes if r.tipo == "relacao_familiar_publicamente_declarada")
    assert declarada.fonte == "serper"
    assert declarada.confianca in (ConfidenceLevel.MEDIA, ConfidenceLevel.ALTA)
    assert "https://noticia.exemplo/1" in declarada.evidencias


@pytest.mark.asyncio
async def test_never_asserts_sibling_relationship_from_surname_alone() -> None:
    service = FamilyRelationshipService(search_provider=FakeSearchProvider([]))

    relacoes = await service.find_possible_relations(["Joana Silva", "Carlos Silva"])

    for relacao in relacoes:
        assert "irma" not in relacao.tipo
        assert "irmã" not in relacao.tipo
        if relacao.tipo == "similaridade_de_sobrenome":
            assert relacao.confianca == ConfidenceLevel.BAIXA


@pytest.mark.asyncio
async def test_single_person_yields_no_relations() -> None:
    service = FamilyRelationshipService(search_provider=FakeSearchProvider([]))

    relacoes = await service.find_possible_relations(["Joana Silva"])

    assert relacoes == []
