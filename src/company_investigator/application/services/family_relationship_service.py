from itertools import combinations

from company_investigator.domain.entities.investigation import (
    ConfidenceLevel,
    PossivelRelacaoFamiliar,
)
from company_investigator.domain.ports.search_provider import SearchProviderPort

_TERMOS_FAMILIA = (
    "irmão", "irma", "irmã", "filho", "filha", "pai de", "mãe de", "mae de",
    "cônjuge", "conjuge", "esposa", "marido", "casado com", "casada com",
)  # fmt: skip


class FamilyRelationshipService:
    """Procura possiveis relacoes familiares entre pessoas encontradas na
    investigacao, com cautela deliberada: sobrenome em comum NUNCA vira uma
    afirmacao de parentesco, so um sinal fraco (`similaridade_de_sobrenome`,
    confianca sempre baixa). So promovemos para
    `relacao_familiar_publicamente_declarada` quando uma fonte publica menciona
    um termo de parentesco explicito perto dos dois nomes."""

    def __init__(self, search_provider: SearchProviderPort) -> None:
        self._search_provider = search_provider

    async def find_possible_relations(self, pessoas: list[str]) -> list[PossivelRelacaoFamiliar]:
        relacoes: list[PossivelRelacaoFamiliar] = []

        for pessoa_a, pessoa_b in combinations(pessoas, 2):
            sobrenomes_comuns = _sobrenomes(pessoa_a) & _sobrenomes(pessoa_b)
            if not sobrenomes_comuns:
                continue

            relacoes.append(
                PossivelRelacaoFamiliar(
                    tipo="similaridade_de_sobrenome",
                    pessoas=[pessoa_a, pessoa_b],
                    evidencias=[f"sobrenome em comum: '{sorted(sobrenomes_comuns)[0]}'"],
                    confianca=ConfidenceLevel.BAIXA,
                )
            )

            declarada = await self._buscar_relacao_declarada(pessoa_a, pessoa_b)
            if declarada is not None:
                relacoes.append(declarada)

        return relacoes

    async def _buscar_relacao_declarada(
        self, pessoa_a: str, pessoa_b: str
    ) -> PossivelRelacaoFamiliar | None:
        results = await self._search_provider.search(f'"{pessoa_a}" "{pessoa_b}"', max_results=5)

        for result in results:
            texto = f"{result.title} {result.snippet}".lower()
            if any(termo in texto for termo in _TERMOS_FAMILIA):
                return PossivelRelacaoFamiliar(
                    tipo="relacao_familiar_publicamente_declarada",
                    pessoas=[pessoa_a, pessoa_b],
                    evidencias=[result.url],
                    confianca=ConfidenceLevel.MEDIA,
                    fonte=result.source,
                )
        return None


def _sobrenomes(nome_completo: str) -> set[str]:
    """Todos os tokens do nome exceto o primeiro (o primeiro nome), em minusculas.
    Nomes brasileiros costumam empilhar sobrenomes (materno + paterno); comparar
    o conjunto inteiro (nao so o ultimo token) capta sobrenomes compostos
    compartilhados que nao aparecem por ultimo em um dos dois nomes."""
    partes = [p.lower() for p in nome_completo.strip().split() if len(p) > 2]
    if len(partes) < 2:
        return set()
    return set(partes[1:])
