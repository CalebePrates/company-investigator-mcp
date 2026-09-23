"""Modelos Pydantic de saida compartilhados entre `investigar_empresa`,
`obter_secao_investigacao` e o MCP Resource de investigacao. Vivem num modulo
proprio (em vez de dentro de um dos arquivos de tool) porque sao usados por
mais de um adapter de interface - nenhum deles "pertence" a uma unica tool."""

from __future__ import annotations

from pydantic import BaseModel

from company_investigator.application.services.investigation_storage_service import (
    EmpresaRelacionadaResumo,
    IndiceInvestigacao,
    MovimentoProcessual,
    PaginaSecao,
    SecaoResumo,
)
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import (
    ConsultaProcessualStatus,
    DadosOficiaisProcesso,
    LinkedInResultado,
    Noticia,
    PerfilRedeSocial,
    PessoaChave,
    PessoaRelacionada,
    PossivelRelacaoFamiliar,
    ProcessoConfirmado,
    ReferenciaProcessual,
    RegistroPEP,
    Relacionamento,
)
from company_investigator.domain.entities.socio import Socio


class SocioOutput(BaseModel):
    nome: str
    qualificacao: str
    documento: str | None

    @classmethod
    def from_entity(cls, socio: Socio) -> SocioOutput:
        return cls(nome=socio.nome, qualificacao=socio.qualificacao, documento=socio.documento)


class EmpresaOutput(BaseModel):
    cnpj: str
    razao_social: str
    nome_fantasia: str
    situacao: str
    endereco: str | None

    @classmethod
    def from_entity(cls, company: Company) -> EmpresaOutput:
        return cls(
            cnpj=company.cnpj,
            razao_social=company.razao_social,
            nome_fantasia=company.nome_fantasia,
            situacao=company.situacao,
            endereco=company.endereco,
        )


class NoticiaOutput(BaseModel):
    titulo: str
    url: str
    fonte: str
    resumo: str
    consultado_em: str
    data_publicacao: str | None
    confianca: str

    @classmethod
    def from_entity(cls, noticia: Noticia) -> NoticiaOutput:
        return cls(
            titulo=noticia.titulo,
            url=noticia.url,
            fonte=noticia.fonte,
            resumo=noticia.resumo,
            consultado_em=noticia.consultado_em.isoformat(),
            data_publicacao=noticia.data_publicacao,
            confianca=noticia.confianca.value,
        )


class PerfilRedeSocialOutput(BaseModel):
    plataforma: str
    nome_perfil: str
    url: str
    tipo: str
    nome_pessoa: str | None
    confianca: str
    fonte: str
    consultado_em: str

    @classmethod
    def from_entity(cls, perfil: PerfilRedeSocial) -> PerfilRedeSocialOutput:
        return cls(
            plataforma=perfil.plataforma,
            nome_perfil=perfil.nome_perfil,
            url=perfil.url,
            tipo=perfil.tipo,
            nome_pessoa=perfil.nome_pessoa,
            confianca=perfil.confianca.value,
            fonte=perfil.fonte,
            consultado_em=perfil.consultado_em.isoformat(),
        )


class PessoaChaveOutput(BaseModel):
    nome: str
    cargo: str
    empresa_relacionada: str
    url_linkedin: str
    tipo_cargo: str
    confianca: str
    fontes: list[str]
    consultado_em: str

    @classmethod
    def from_entity(cls, pessoa: PessoaChave) -> PessoaChaveOutput:
        return cls(
            nome=pessoa.nome,
            cargo=pessoa.cargo,
            empresa_relacionada=pessoa.empresa_relacionada,
            url_linkedin=pessoa.url_linkedin,
            tipo_cargo=pessoa.tipo_cargo,
            confianca=pessoa.confianca.value,
            fontes=pessoa.fontes,
            consultado_em=pessoa.consultado_em.isoformat(),
        )


class ReferenciaProcessualOutput(BaseModel):
    titulo: str
    url: str
    fonte: str
    resumo: str
    consultado_em: str
    relacionado_a: str
    tipo_relacionado: str
    numero_processo_detectado: str | None
    confianca: str

    @classmethod
    def from_entity(cls, referencia: ReferenciaProcessual) -> ReferenciaProcessualOutput:
        return cls(
            titulo=referencia.titulo,
            url=referencia.url,
            fonte=referencia.fonte,
            resumo=referencia.resumo,
            consultado_em=referencia.consultado_em.isoformat(),
            relacionado_a=referencia.relacionado_a,
            tipo_relacionado=referencia.tipo_relacionado,
            numero_processo_detectado=referencia.numero_processo_detectado,
            confianca=referencia.confianca.value,
        )


class MovimentoProcessualOutput(BaseModel):
    """Um movimento de um processo confirmado, como item da secao
    'movimentos_processuais' (ligado ao seu processo por `numero_processo`)."""

    numero_processo: str
    nome: str
    data: str | None

    @classmethod
    def from_entity(cls, movimento: MovimentoProcessual) -> MovimentoProcessualOutput:
        return cls(
            numero_processo=movimento.numero_processo, nome=movimento.nome, data=movimento.data
        )


class DadosOficiaisProcessoOutput(BaseModel):
    """Os movimentos NAO vem embutidos aqui (um processo antigo pode ter milhares):
    `total_movimentos` diz quantos existem, e cada um esta na secao paginada
    'movimentos_processuais', filtravel por `numero_processo`."""

    numero_processo: str
    tribunal: str
    grau: str | None
    orgao_julgador: str | None
    classe: str | None
    assuntos: list[str]
    total_movimentos: int
    data_ajuizamento: str | None
    sistema: str | None
    fonte: str
    consultado_em: str

    @classmethod
    def from_entity(cls, dados: DadosOficiaisProcesso) -> DadosOficiaisProcessoOutput:
        return cls(
            numero_processo=dados.numero_processo,
            tribunal=dados.tribunal,
            grau=dados.grau,
            orgao_julgador=dados.orgao_julgador,
            classe=dados.classe,
            assuntos=dados.assuntos,
            total_movimentos=len(dados.movimentos),
            data_ajuizamento=dados.data_ajuizamento,
            sistema=dados.sistema,
            fonte=dados.fonte,
            consultado_em=dados.consultado_em.isoformat(),
        )


class ProcessoConfirmadoOutput(BaseModel):
    dados: DadosOficiaisProcessoOutput
    relacionado_a: str
    tipo_relacionado: str
    confianca: str
    origem: ReferenciaProcessualOutput

    @classmethod
    def from_entity(cls, processo: ProcessoConfirmado) -> ProcessoConfirmadoOutput:
        return cls(
            dados=DadosOficiaisProcessoOutput.from_entity(processo.dados),
            relacionado_a=processo.relacionado_a,
            tipo_relacionado=processo.tipo_relacionado,
            confianca=processo.confianca.value,
            origem=ReferenciaProcessualOutput.from_entity(processo.origem),
        )


class ConsultaProcessualStatusOutput(BaseModel):
    status: str
    motivo: str | None

    @classmethod
    def from_entity(cls, status: ConsultaProcessualStatus) -> ConsultaProcessualStatusOutput:
        return cls(status=status.status, motivo=status.motivo)


class LinkedInOutput(BaseModel):
    empresa: PerfilRedeSocialOutput | None
    pessoas_chave: list[PessoaChaveOutput]

    @classmethod
    def from_entity(cls, linkedin: LinkedInResultado) -> LinkedInOutput:
        return cls(
            empresa=PerfilRedeSocialOutput.from_entity(linkedin.empresa)
            if linkedin.empresa
            else None,
            pessoas_chave=[PessoaChaveOutput.from_entity(p) for p in linkedin.pessoas_chave],
        )


class RelacionamentoOutput(BaseModel):
    origem: str
    destino: str
    tipo_relacionamento: str
    fonte: str
    confianca: str

    @classmethod
    def from_entity(cls, relacionamento: Relacionamento) -> RelacionamentoOutput:
        return cls(
            origem=relacionamento.origem,
            destino=relacionamento.destino,
            tipo_relacionamento=relacionamento.tipo_relacionamento,
            fonte=relacionamento.fonte,
            confianca=relacionamento.confianca.value,
        )


class PessoaRelacionadaOutput(BaseModel):
    nome: str
    papel: str
    empresa_relacionada: str
    fonte: str
    confianca: str

    @classmethod
    def from_entity(cls, pessoa: PessoaRelacionada) -> PessoaRelacionadaOutput:
        return cls(
            nome=pessoa.nome,
            papel=pessoa.papel,
            empresa_relacionada=pessoa.empresa_relacionada,
            fonte=pessoa.fonte,
            confianca=pessoa.confianca.value,
        )


class PossivelRelacaoFamiliarOutput(BaseModel):
    tipo: str
    pessoas: list[str]
    evidencias: list[str]
    confianca: str
    fonte: str | None

    @classmethod
    def from_entity(cls, relacao: PossivelRelacaoFamiliar) -> PossivelRelacaoFamiliarOutput:
        return cls(
            tipo=relacao.tipo,
            pessoas=relacao.pessoas,
            evidencias=relacao.evidencias,
            confianca=relacao.confianca.value,
            fonte=relacao.fonte,
        )


class RegistroPEPOutput(BaseModel):
    pessoa: str
    status: str
    funcao: str | None
    orgao: str | None
    data_inicio: str | None
    data_fim: str | None
    data_fim_carencia: str | None
    fonte: str
    confianca: str

    @classmethod
    def from_entity(cls, registro: RegistroPEP) -> RegistroPEPOutput:
        return cls(
            pessoa=registro.pessoa,
            status=registro.status.value,
            funcao=registro.funcao,
            orgao=registro.orgao,
            data_inicio=registro.data_inicio,
            data_fim=registro.data_fim,
            data_fim_carencia=registro.data_fim_carencia,
            fonte=registro.fonte,
            confianca=registro.confianca.value,
        )


class EmpresaRelacionadaResumoOutput(BaseModel):
    """O item que aparece na secao 'empresas_relacionadas': o resumo da relacao
    mais uma REFERENCIA (investigation_id) para a sub-investigacao completa -
    nunca a sub-investigacao inteira embutida aqui. Use
    `obter_secao_investigacao`/o resource com esse investigation_id para
    percorrer a empresa relacionada."""

    empresa: EmpresaOutput
    origem_socio: str
    participacao: str
    fonte: str
    confianca: str
    investigation_id: str

    @classmethod
    def from_entity(cls, resumo: EmpresaRelacionadaResumo) -> EmpresaRelacionadaResumoOutput:
        return cls(
            empresa=EmpresaOutput.from_entity(resumo.empresa),
            origem_socio=resumo.origem_socio,
            participacao=resumo.participacao,
            fonte=resumo.fonte,
            confianca=resumo.confianca.value,
            investigation_id=resumo.investigation_id,
        )


class SecaoResumoOutput(BaseModel):
    nome: str
    tipo: str
    total_itens: int

    @classmethod
    def from_entity(cls, secao: SecaoResumo) -> SecaoResumoOutput:
        return cls(nome=secao.nome, tipo=secao.tipo, total_itens=secao.total_itens)


class IndiceInvestigacaoOutput(BaseModel):
    """O que `investigar_empresa` devolve diretamente: pequeno, nao importa o
    tamanho da investigacao completa guardada por tras. Use `investigation_id`
    com `obter_secao_investigacao` (tool) ou o resource
    `investigation://{investigation_id}/{secao}` para recuperar cada secao,
    pagina por pagina, ate ter 100% dos dados coletados."""

    investigation_id: str
    identificador_usado: str
    empresa: EmpresaOutput | None
    processos_status: ConsultaProcessualStatusOutput
    secoes: list[SecaoResumoOutput]

    @classmethod
    def from_entity(cls, indice: IndiceInvestigacao) -> IndiceInvestigacaoOutput:
        return cls(
            investigation_id=indice.investigation_id,
            identificador_usado=indice.identificador_usado,
            empresa=EmpresaOutput.from_entity(indice.empresa) if indice.empresa else None,
            processos_status=ConsultaProcessualStatusOutput.from_entity(indice.processos_status),
            secoes=[SecaoResumoOutput.from_entity(s) for s in indice.secoes],
        )


class PaginaSecaoOutput(BaseModel):
    secao: str
    pagina: int
    tamanho_pagina: int
    total_itens: int
    total_paginas: int
    itens: list[object]

    @classmethod
    def from_entity(cls, pagina: PaginaSecao) -> PaginaSecaoOutput:
        return cls(
            secao=pagina.secao,
            pagina=pagina.pagina,
            tamanho_pagina=pagina.tamanho_pagina,
            total_itens=pagina.total_itens,
            total_paginas=pagina.total_paginas,
            itens=[_serialize_item(pagina.secao, item) for item in pagina.itens],
        )


_STRING_SECTIONS = {"contatos", "fontes", "limitacoes"}

_ITEM_SERIALIZERS = {
    "candidatos": EmpresaOutput,
    "socios": SocioOutput,
    "pessoas_chave": PessoaChaveOutput,
    "linkedin": LinkedInOutput,
    "redes_sociais": PerfilRedeSocialOutput,
    "noticias": NoticiaOutput,
    "processos_confirmados": ProcessoConfirmadoOutput,
    "processos_referencias": ReferenciaProcessualOutput,
    "movimentos_processuais": MovimentoProcessualOutput,
    "processos_status": ConsultaProcessualStatusOutput,
    "empresas_relacionadas": EmpresaRelacionadaResumoOutput,
    "pessoas_relacionadas": PessoaRelacionadaOutput,
    "relacionamentos": RelacionamentoOutput,
    "possiveis_relacoes_familiares": PossivelRelacaoFamiliarOutput,
    "peps": RegistroPEPOutput,
    "empresa": EmpresaOutput,
}


def _serialize_item(secao: str, item: object) -> object:
    if secao in _STRING_SECTIONS:
        return item
    output_cls = _ITEM_SERIALIZERS.get(secao)
    if output_cls is None:
        raise ValueError(f"Nao ha serializador de saida para a secao {secao!r}.")
    return output_cls.from_entity(item).model_dump()
