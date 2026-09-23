from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.socio import Socio


class ConfidenceLevel(StrEnum):
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


@dataclass(frozen=True)
class Noticia:
    titulo: str
    url: str
    fonte: str
    resumo: str
    consultado_em: datetime
    data_publicacao: str | None = None
    confianca: ConfidenceLevel = ConfidenceLevel.MEDIA


@dataclass(frozen=True)
class PerfilRedeSocial:
    plataforma: str
    nome_perfil: str
    url: str
    tipo: str
    fonte: str
    consultado_em: datetime
    nome_pessoa: str | None = None
    confianca: ConfidenceLevel = ConfidenceLevel.BAIXA


@dataclass(frozen=True)
class PessoaChave:
    nome: str
    cargo: str
    empresa_relacionada: str
    url_linkedin: str
    tipo_cargo: str
    confianca: ConfidenceLevel
    fontes: list[str]
    consultado_em: datetime


@dataclass(frozen=True)
class ReferenciaProcessual:
    """Uma mencao publica a um possivel processo, encontrada por busca generica
    (SearchProvider). Isto NAO e uma confirmacao de que o processo existe ou de
    que pertence de fato a empresa/pessoa pesquisada - e so uma pista."""

    titulo: str
    url: str
    fonte: str
    resumo: str
    consultado_em: datetime
    relacionado_a: str
    tipo_relacionado: str  # "empresa" | "pessoa"
    numero_processo_detectado: str | None = None
    confianca: ConfidenceLevel = ConfidenceLevel.BAIXA


@dataclass(frozen=True)
class Movimento:
    nome: str
    data: str | None = None


@dataclass(frozen=True)
class DadosOficiaisProcesso:
    """Dados oficiais de um processo, obtidos via consulta por numero a uma fonte
    oficial (DataJud/CNJ). O DataJud nao expoe partes (nome/CPF/CNPJ) - por isso
    este registro nao afirma a quem o processo pertence."""

    numero_processo: str
    tribunal: str
    grau: str | None
    orgao_julgador: str | None
    classe: str | None
    assuntos: list[str]
    movimentos: list[Movimento]
    data_ajuizamento: str | None
    sistema: str | None
    fonte: str
    consultado_em: datetime


@dataclass(frozen=True)
class ProcessoConfirmado:
    """Um processo cujos dados oficiais foram obtidos (via DadosOficiaisProcesso),
    combinados com o contexto de investigacao (a referencia que levou ate ele e a
    quem ele foi associado). A confianca da associacao vem da referencia de origem,
    nunca da fonte oficial (que nao sabe quem sao as partes)."""

    dados: DadosOficiaisProcesso
    relacionado_a: str
    tipo_relacionado: str  # "empresa" | "pessoa"
    confianca: ConfidenceLevel
    origem: ReferenciaProcessual


@dataclass(frozen=True)
class ConsultaProcessualStatus:
    status: str  # "realizada" | "parcial" | "nao_confirmada"
    motivo: str | None = None


@dataclass(frozen=True)
class ConsultaProcessual:
    confirmados: list[ProcessoConfirmado]
    referencias: list[ReferenciaProcessual]
    status: ConsultaProcessualStatus


@dataclass(frozen=True)
class LinkedInResultado:
    empresa: PerfilRedeSocial | None
    pessoas_chave: list[PessoaChave]


@dataclass(frozen=True)
class Relacionamento:
    """Uma aresta na rede: como uma origem se relaciona com um destino."""

    origem: str
    destino: str
    tipo_relacionamento: str  # ex.: "socio_de", "relacionada_por_socio"
    fonte: str
    confianca: ConfidenceLevel


@dataclass(frozen=True)
class EmpresaRelacionada:
    """Uma empresa descoberta a partir de um socio da empresa principal (ou de
    outra empresa relacionada, ate o limite de profundidade). Carrega sua propria
    sub-investigacao completa (dados cadastrais, socios, LinkedIn, noticias,
    processos, PEP dos seus socios) - so a EXPANSAO da rede a partir dela e que
    fica limitada pela profundidade."""

    empresa: Company
    origem_socio: str
    participacao: str  # "atual" | "historica" | "desconhecida"
    fonte: str
    confianca: ConfidenceLevel
    investigacao: EmpresaInvestigada


@dataclass(frozen=True)
class PessoaRelacionada:
    """Uma pessoa encontrada atraves da rede (socia ou pessoa-chave de uma empresa
    relacionada). Nao implica relacao familiar ou pessoal com ninguem."""

    nome: str
    papel: str
    empresa_relacionada: str
    fonte: str
    confianca: ConfidenceLevel


@dataclass(frozen=True)
class PossivelRelacaoFamiliar:
    """Uma possivel relacao familiar. `similaridade_de_sobrenome` NUNCA e uma
    afirmacao de parentesco - e so um sinal fraco. Somente
    `relacao_familiar_publicamente_declarada` reflete uma fonte que afirma a
    relacao explicitamente, e mesmo assim preserva a fonte para verificacao."""

    tipo: str  # "similaridade_de_sobrenome" | "relacao_familiar_publicamente_declarada"
    pessoas: list[str]
    evidencias: list[str]
    confianca: ConfidenceLevel
    fonte: str | None = None


class StatusPEP(StrEnum):
    PEP_CONFIRMADA = "PEP_CONFIRMADA"
    NAO_IDENTIFICADA = "NAO_IDENTIFICADA"
    POSSIVEL_HOMONIMO = "POSSIVEL_HOMONIMO"
    NAO_FOI_POSSIVEL_VERIFICAR = "NAO_FOI_POSSIVEL_VERIFICAR"


@dataclass(frozen=True)
class RegistroPEP:
    pessoa: str
    status: StatusPEP
    funcao: str | None
    orgao: str | None
    data_inicio: str | None
    data_fim: str | None
    data_fim_carencia: str | None
    fonte: str
    confianca: ConfidenceLevel


@dataclass(frozen=True)
class EmpresaInvestigada:
    identificador_usado: str
    empresa: Company | None
    candidatos: list[Company]
    socios: list[Socio]
    pessoas_chave: list[PessoaChave]
    linkedin: LinkedInResultado
    redes_sociais: list[PerfilRedeSocial]
    noticias: list[Noticia]
    contatos: list[str]
    processos: ConsultaProcessual
    fontes: list[str]
    empresas_relacionadas: list[EmpresaRelacionada] = field(default_factory=list)
    pessoas_relacionadas: list[PessoaRelacionada] = field(default_factory=list)
    relacionamentos: list[Relacionamento] = field(default_factory=list)
    possiveis_relacoes_familiares: list[PossivelRelacaoFamiliar] = field(default_factory=list)
    peps: list[RegistroPEP] = field(default_factory=list)
    limitacoes: list[str] = field(default_factory=list)
