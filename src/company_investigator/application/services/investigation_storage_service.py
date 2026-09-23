import math
from dataclasses import dataclass, field
from typing import Any

from company_investigator.application.exceptions import InvestigationNotFoundError
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import (
    ConfidenceLevel,
    ConsultaProcessualStatus,
    EmpresaInvestigada,
)
from company_investigator.domain.ports.investigation_store import InvestigationStorePort

_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 50


@dataclass(frozen=True)
class SecaoResumo:
    nome: str
    tipo: str  # "objeto" | "lista"
    total_itens: int


@dataclass(frozen=True)
class IndiceInvestigacao:
    """O que `investigar_empresa` devolve diretamente: pequeno o bastante para
    caber numa unica resposta de Tool, nao importa o tamanho da investigacao
    completa guardada por tras. Nenhum item de lista e inlined aqui - so
    contagens; os objetos pequenos (empresa, status de processos) vem inteiros
    porque sao baratos."""

    investigation_id: str
    identificador_usado: str
    empresa: Company | None
    processos_status: ConsultaProcessualStatus
    secoes: list[SecaoResumo]


@dataclass(frozen=True)
class EmpresaRelacionadaResumo:
    """Como uma empresa relacionada aparece na secao 'empresas_relacionadas':
    o resumo da relacao, mais uma REFERENCIA (investigation_id) para a
    sub-investigacao completa dela - nunca a sub-investigacao inlined. E isso
    que evita a explosao recursiva de tamanho."""

    empresa: Company
    origem_socio: str
    participacao: str
    fonte: str
    confianca: ConfidenceLevel
    investigation_id: str


@dataclass(frozen=True)
class PaginaSecao:
    secao: str
    pagina: int
    tamanho_pagina: int
    total_itens: int
    total_paginas: int
    itens: list[Any] = field(default_factory=list)


class InvestigationStorageService:
    """Guarda uma EmpresaInvestigada (e, recursivamente, todas as suas empresas
    relacionadas) no InvestigationStorePort, e da acesso a ela em pedacos: um
    indice pequeno por investigacao, e paginas por secao. Nenhum dado e
    descartado - tudo que a investigacao coletou continua acessivel, so nao
    tudo de uma vez na mesma resposta."""

    def __init__(self, store: InvestigationStorePort) -> None:
        self._store = store
        self._related_summaries: dict[str, list[EmpresaRelacionadaResumo]] = {}

    def store(self, investigation: EmpresaInvestigada) -> IndiceInvestigacao:
        investigation_id = self._store_recursively(investigation)
        return self._build_index(investigation_id, investigation)

    def get_index(self, investigation_id: str) -> IndiceInvestigacao:
        investigation = self._require(investigation_id)
        return self._build_index(investigation_id, investigation)

    def get_section(
        self,
        investigation_id: str,
        secao: str,
        pagina: int = 1,
        tamanho_pagina: int = _DEFAULT_PAGE_SIZE,
    ) -> PaginaSecao:
        tamanho_pagina = max(1, min(tamanho_pagina, _MAX_PAGE_SIZE))
        pagina = max(1, pagina)

        if secao == "empresas_relacionadas":
            investigation = self._require(investigation_id)
            itens = self._related_summaries.get(investigation_id, [])
            return _paginate(secao, itens, pagina, tamanho_pagina)

        investigation = self._require(investigation_id)

        if secao == "empresa":
            return _paginate(
                secao,
                [investigation.empresa] if investigation.empresa else [],
                pagina,
                tamanho_pagina,
            )
        if secao == "linkedin":
            return _paginate(secao, [investigation.linkedin], pagina, tamanho_pagina)
        if secao == "processos_status":
            return _paginate(secao, [investigation.processos.status], pagina, tamanho_pagina)
        if secao == "processos_confirmados":
            return _paginate(secao, investigation.processos.confirmados, pagina, tamanho_pagina)
        if secao == "processos_referencias":
            return _paginate(secao, investigation.processos.referencias, pagina, tamanho_pagina)

        campo = _LIST_FIELDS.get(secao)
        if campo is not None:
            return _paginate(secao, campo(investigation), pagina, tamanho_pagina)

        raise ValueError(f"Secao desconhecida: {secao!r}")

    def _require(self, investigation_id: str) -> EmpresaInvestigada:
        investigation = self._store.get(investigation_id)
        if investigation is None:
            raise InvestigationNotFoundError(
                f"Nenhuma investigacao encontrada para o id '{investigation_id}'."
            )
        return investigation

    def _store_recursively(self, investigation: EmpresaInvestigada) -> str:
        resumos: list[EmpresaRelacionadaResumo] = []
        for relacionada in investigation.empresas_relacionadas:
            child_id = self._store_recursively(relacionada.investigacao)
            resumos.append(
                EmpresaRelacionadaResumo(
                    empresa=relacionada.empresa,
                    origem_socio=relacionada.origem_socio,
                    participacao=relacionada.participacao,
                    fonte=relacionada.fonte,
                    confianca=relacionada.confianca,
                    investigation_id=child_id,
                )
            )

        investigation_id = self._store.save(investigation)
        self._related_summaries[investigation_id] = resumos
        return investigation_id

    def _build_index(
        self, investigation_id: str, investigation: EmpresaInvestigada
    ) -> IndiceInvestigacao:
        relacionadas_count = len(self._related_summaries.get(investigation_id, []))
        secoes = [
            SecaoResumo("candidatos", "lista", len(investigation.candidatos)),
            SecaoResumo("socios", "lista", len(investigation.socios)),
            SecaoResumo("pessoas_chave", "lista", len(investigation.pessoas_chave)),
            SecaoResumo("linkedin", "objeto", 1),
            SecaoResumo("redes_sociais", "lista", len(investigation.redes_sociais)),
            SecaoResumo("noticias", "lista", len(investigation.noticias)),
            SecaoResumo("contatos", "lista", len(investigation.contatos)),
            SecaoResumo("processos_confirmados", "lista", len(investigation.processos.confirmados)),
            SecaoResumo("processos_referencias", "lista", len(investigation.processos.referencias)),
            SecaoResumo("fontes", "lista", len(investigation.fontes)),
            SecaoResumo("empresas_relacionadas", "lista", relacionadas_count),
            SecaoResumo("pessoas_relacionadas", "lista", len(investigation.pessoas_relacionadas)),
            SecaoResumo("relacionamentos", "lista", len(investigation.relacionamentos)),
            SecaoResumo(
                "possiveis_relacoes_familiares",
                "lista",
                len(investigation.possiveis_relacoes_familiares),
            ),
            SecaoResumo("peps", "lista", len(investigation.peps)),
            SecaoResumo("limitacoes", "lista", len(investigation.limitacoes)),
        ]
        return IndiceInvestigacao(
            investigation_id=investigation_id,
            identificador_usado=investigation.identificador_usado,
            empresa=investigation.empresa,
            processos_status=investigation.processos.status,
            secoes=secoes,
        )


_LIST_FIELDS: dict[str, Any] = {
    "candidatos": lambda inv: inv.candidatos,
    "socios": lambda inv: inv.socios,
    "pessoas_chave": lambda inv: inv.pessoas_chave,
    "redes_sociais": lambda inv: inv.redes_sociais,
    "noticias": lambda inv: inv.noticias,
    "contatos": lambda inv: inv.contatos,
    "fontes": lambda inv: inv.fontes,
    "pessoas_relacionadas": lambda inv: inv.pessoas_relacionadas,
    "relacionamentos": lambda inv: inv.relacionamentos,
    "possiveis_relacoes_familiares": lambda inv: inv.possiveis_relacoes_familiares,
    "peps": lambda inv: inv.peps,
    "limitacoes": lambda inv: inv.limitacoes,
}


def _paginate(secao: str, itens: list[Any], pagina: int, tamanho_pagina: int) -> PaginaSecao:
    total_itens = len(itens)
    total_paginas = max(1, math.ceil(total_itens / tamanho_pagina))
    inicio = (pagina - 1) * tamanho_pagina
    fim = inicio + tamanho_pagina
    return PaginaSecao(
        secao=secao,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        total_itens=total_itens,
        total_paginas=total_paginas,
        itens=itens[inicio:fim],
    )
