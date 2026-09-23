from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ValidationError, field_validator

from company_investigator.application.exceptions import CompanyNotFoundError
from company_investigator.application.use_cases.investigar_empresa_use_case import (
    InvestigarEmpresaUseCase,
)
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import (
    ConsultaProcessual,
    DadosOficiaisProcesso,
    EmpresaInvestigada,
    EmpresaRelacionada,
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
from company_investigator.domain.ports.company_repository import CompanyRepositoryError
from company_investigator.domain.ports.search_provider import SearchProviderError

_PROFUNDIDADE_MAXIMA = 2

_DESCRIPTION = (
    "Investiga uma empresa a partir de um CNPJ ou de um nome (razao social/nome "
    "fantasia), combinando dados cadastrais oficiais (BrasilAPI) com buscas publicas "
    "(via uma Search API) por noticias, perfis em redes sociais (LinkedIn, Instagram, "
    "Facebook, YouTube, X/Twitter, TikTok), pessoas-chave no LinkedIn (CEO, "
    "fundadores, socios, diretores etc.) e processos judiciais publicos. Parametro "
    "'identificador' (string, obrigatorio): um CNPJ (com ou sem pontuacao) ou um "
    "nome de empresa. Se o nome for ambiguo, a resposta traz 'candidatos' (varias "
    "empresas possiveis) em vez de afirmar qual delas e a certa. Cada informacao "
    "encontrada preserva a fonte, a URL, a data da consulta e um nivel de confianca "
    "aproximado (alta/media/baixa) — nunca e uma confirmacao definitiva de "
    "identidade, especialmente para pessoas fisicas. Processos judiciais aparecem em "
    "'processos.referencias' (mencoes publicas encontradas por busca, nao "
    "confirmadas) e 'processos.confirmados' (dados oficiais do DataJud/CNJ, "
    "obtidos quando um numero de processo foi identificado); 'processos.status' "
    "informa se a consulta foi 'realizada', 'parcial' ou 'nao_confirmada', com o "
    "motivo. A existencia de um processo NUNCA deve ser interpretada como prova de "
    "irregularidade, culpa ou inadimplencia. Falhas pontuais em uma fonte (timeout, "
    "sem resultados) nao interrompem a investigacao: ficam registradas em "
    "'limitacoes'. Nao acessa areas privadas, nao faz login e nao contorna CAPTCHA "
    "ou mecanismos anti-bot de nenhuma plataforma. Tambem expande a rede societaria: "
    "'empresas_relacionadas' traz outras empresas dos socios (com sua propria "
    "sub-investigacao completa), 'pessoas_relacionadas' agrega quem foi encontrado "
    "nelas, e 'relacionamentos' lista as arestas da rede (quem e socio de quem). "
    "'possiveis_relacoes_familiares' NUNCA afirma parentesco: sobrenome em comum "
    "vira 'similaridade_de_sobrenome' (confianca sempre baixa); so uma fonte que "
    "declare a relacao explicitamente vira 'relacao_familiar_publicamente_declarada'. "
    "'peps' verifica cada socio no cadastro oficial de Pessoas Expostas "
    "Politicamente (CGU); status 'PEP_CONFIRMADA' exige bater o CPF, nunca so o "
    "nome — homonimos ficam em 'POSSIVEL_HOMONIMO'. O parametro 'profundidade' "
    f"(inteiro, padrao 1, maximo {_PROFUNDIDADE_MAXIMA}) controla quantos niveis de "
    "'socio -> nova empresa' sao expandidos; profundidade 0 investiga so a empresa "
    "pedida, sem explorar a rede."
)


class InvestigarEmpresaInput(BaseModel):
    """Modelo validado dos parametros recebidos pela tool investigar_empresa."""

    identificador: str
    profundidade: int = 1

    @field_validator("identificador")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("O identificador (CNPJ ou nome da empresa) nao pode ser vazio.")
        return value.strip()

    @field_validator("profundidade")
    @classmethod
    def _within_bounds(cls, value: int) -> int:
        if not (0 <= value <= _PROFUNDIDADE_MAXIMA):
            raise ValueError(f"profundidade deve estar entre 0 e {_PROFUNDIDADE_MAXIMA}.")
        return value


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


class MovimentoOutput(BaseModel):
    nome: str
    data: str | None


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


class DadosOficiaisProcessoOutput(BaseModel):
    numero_processo: str
    tribunal: str
    grau: str | None
    orgao_julgador: str | None
    classe: str | None
    assuntos: list[str]
    movimentos: list[MovimentoOutput]
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
            movimentos=[MovimentoOutput(nome=m.nome, data=m.data) for m in dados.movimentos],
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


class ConsultaProcessualOutput(BaseModel):
    confirmados: list[ProcessoConfirmadoOutput]
    referencias: list[ReferenciaProcessualOutput]
    status: str
    motivo: str | None

    @classmethod
    def from_entity(cls, consulta: ConsultaProcessual) -> ConsultaProcessualOutput:
        return cls(
            confirmados=[ProcessoConfirmadoOutput.from_entity(p) for p in consulta.confirmados],
            referencias=[ReferenciaProcessualOutput.from_entity(r) for r in consulta.referencias],
            status=consulta.status.status,
            motivo=consulta.status.motivo,
        )


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


class EmpresaRelacionadaOutput(BaseModel):
    empresa: EmpresaOutput
    origem_socio: str
    participacao: str
    fonte: str
    confianca: str
    investigacao: EmpresaInvestigadaOutput

    @classmethod
    def from_entity(cls, relacionada: EmpresaRelacionada) -> EmpresaRelacionadaOutput:
        return cls(
            empresa=EmpresaOutput.from_entity(relacionada.empresa),
            origem_socio=relacionada.origem_socio,
            participacao=relacionada.participacao,
            fonte=relacionada.fonte,
            confianca=relacionada.confianca.value,
            investigacao=EmpresaInvestigadaOutput.from_entity(relacionada.investigacao),
        )


class EmpresaInvestigadaOutput(BaseModel):
    identificador_usado: str
    empresa: EmpresaOutput | None
    candidatos: list[EmpresaOutput]
    socios: list[SocioOutput]
    pessoas_chave: list[PessoaChaveOutput]
    linkedin: LinkedInOutput
    redes_sociais: list[PerfilRedeSocialOutput]
    noticias: list[NoticiaOutput]
    contatos: list[str]
    processos: ConsultaProcessualOutput
    fontes: list[str]
    empresas_relacionadas: list[EmpresaRelacionadaOutput]
    pessoas_relacionadas: list[PessoaRelacionadaOutput]
    relacionamentos: list[RelacionamentoOutput]
    possiveis_relacoes_familiares: list[PossivelRelacaoFamiliarOutput]
    peps: list[RegistroPEPOutput]
    limitacoes: list[str]

    @classmethod
    def from_entity(cls, investigacao: EmpresaInvestigada) -> EmpresaInvestigadaOutput:
        return cls(
            identificador_usado=investigacao.identificador_usado,
            empresa=EmpresaOutput.from_entity(investigacao.empresa)
            if investigacao.empresa
            else None,
            candidatos=[EmpresaOutput.from_entity(c) for c in investigacao.candidatos],
            socios=[SocioOutput.from_entity(s) for s in investigacao.socios],
            pessoas_chave=[PessoaChaveOutput.from_entity(p) for p in investigacao.pessoas_chave],
            linkedin=LinkedInOutput.from_entity(investigacao.linkedin),
            redes_sociais=[
                PerfilRedeSocialOutput.from_entity(r) for r in investigacao.redes_sociais
            ],
            noticias=[NoticiaOutput.from_entity(n) for n in investigacao.noticias],
            contatos=investigacao.contatos,
            processos=ConsultaProcessualOutput.from_entity(investigacao.processos),
            fontes=investigacao.fontes,
            empresas_relacionadas=[
                EmpresaRelacionadaOutput.from_entity(r) for r in investigacao.empresas_relacionadas
            ],
            pessoas_relacionadas=[
                PessoaRelacionadaOutput.from_entity(p) for p in investigacao.pessoas_relacionadas
            ],
            relacionamentos=[
                RelacionamentoOutput.from_entity(r) for r in investigacao.relacionamentos
            ],
            possiveis_relacoes_familiares=[
                PossivelRelacaoFamiliarOutput.from_entity(r)
                for r in investigacao.possiveis_relacoes_familiares
            ],
            peps=[RegistroPEPOutput.from_entity(p) for p in investigacao.peps],
            limitacoes=investigacao.limitacoes,
        )


EmpresaRelacionadaOutput.model_rebuild()


def _first_error_message(exc: ValidationError) -> str:
    errors = exc.errors()
    return str(errors[0]["msg"]) if errors else str(exc)


def register_investigar_empresa_tool(server: MCPServer, use_case: InvestigarEmpresaUseCase) -> None:
    @server.tool(name="investigar_empresa", description=_DESCRIPTION)
    async def investigar_empresa(identificador: str, profundidade: int = 1) -> dict[str, object]:
        try:
            validated = InvestigarEmpresaInput(
                identificador=identificador, profundidade=profundidade
            )
        except ValidationError as exc:
            raise ToolError(_first_error_message(exc)) from exc

        try:
            investigacao = await use_case.execute(
                validated.identificador, depth=validated.profundidade
            )
        except CompanyNotFoundError as exc:
            raise ToolError(str(exc)) from exc
        except CompanyRepositoryError as exc:
            raise ToolError(str(exc)) from exc
        except SearchProviderError as exc:
            raise ToolError(str(exc)) from exc

        return EmpresaInvestigadaOutput.from_entity(investigacao).model_dump()
