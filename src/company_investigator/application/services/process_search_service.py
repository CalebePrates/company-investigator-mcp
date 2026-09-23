import re
from datetime import UTC, datetime

from company_investigator.application.services._confidence import classify_name_match
from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.investigation import (
    ConsultaProcessual,
    ConsultaProcessualStatus,
    ProcessoConfirmado,
    ReferenciaProcessual,
)
from company_investigator.domain.ports.process_lookup import (
    ProcessLookupError,
    ProcessNumberLookupPort,
)
from company_investigator.domain.ports.search_provider import (
    SearchProviderError,
    SearchProviderPort,
)

_NUMERO_PROCESSO_PATTERN = re.compile(r"\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}")


class ProcessSearchService:
    """Pesquisa referencias publicas a processos envolvendo a empresa e as pessoas
    encontradas na investigacao (via SearchProvider), e tenta confirmar cada uma
    delas em uma fonte oficial (via ProcessNumberLookupPort) quando um numero de
    processo puder ser identificado no resultado da busca.

    Nao existe hoje nenhuma fonte oficial, publica e sem CAPTCHA para buscar
    processos diretamente por CNPJ/CPF/nome de parte (ver README/discussao da
    Fase 5) - por isso a confirmacao so acontece por numero, e a confianca da
    associacao vem sempre da referencia que originou o numero, nunca da fonte
    oficial (que nao expoe partes).

    Erros sao tratados internamente: esta classe nunca deixa uma falha de rede
    (busca ou consulta oficial) derrubar a investigacao - ela sempre devolve um
    ConsultaProcessual valido, com o status refletindo o que foi possivel fazer.
    """

    def __init__(
        self,
        search_provider: SearchProviderPort,
        process_number_lookup: ProcessNumberLookupPort | None = None,
    ) -> None:
        self._search_provider = search_provider
        self._process_number_lookup = process_number_lookup

    async def search(self, company: Company, pessoas: list[str]) -> ConsultaProcessual:
        nome_empresa = company.nome_fantasia or company.razao_social
        sujeitos: list[tuple[str, str]] = [("empresa", nome_empresa)]
        sujeitos += [("pessoa", nome) for nome in pessoas]

        referencias: list[ReferenciaProcessual] = []
        busca_falhou = False
        ultimo_erro_busca: str | None = None

        for tipo, nome in sujeitos:
            try:
                resultados = await self._search_provider.search(
                    f'"{nome}" processo judicial', max_results=5
                )
            except SearchProviderError as exc:
                busca_falhou = True
                ultimo_erro_busca = str(exc)
                continue

            consultado_em = datetime.now(UTC)
            for resultado in resultados:
                numero = _extrair_numero_processo(f"{resultado.title} {resultado.snippet}")
                referencias.append(
                    ReferenciaProcessual(
                        titulo=resultado.title,
                        url=resultado.url,
                        fonte=resultado.source,
                        resumo=resultado.snippet,
                        consultado_em=consultado_em,
                        relacionado_a=nome,
                        tipo_relacionado=tipo,
                        numero_processo_detectado=numero,
                        confianca=classify_name_match(nome, resultado.title, resultado.snippet),
                    )
                )

        confirmados, lookup_falhou = await self._confirmar_referencias(referencias)

        status = _build_status(
            referencias=referencias,
            confirmados=confirmados,
            busca_falhou=busca_falhou,
            erro_busca=ultimo_erro_busca,
            lookup_configurado=self._process_number_lookup is not None,
            lookup_falhou=lookup_falhou,
        )
        return ConsultaProcessual(confirmados=confirmados, referencias=referencias, status=status)

    async def _confirmar_referencias(
        self, referencias: list[ReferenciaProcessual]
    ) -> tuple[list[ProcessoConfirmado], bool]:
        if self._process_number_lookup is None:
            return [], False

        confirmados: list[ProcessoConfirmado] = []
        lookup_falhou = False
        ja_consultados: set[str] = set()

        for referencia in referencias:
            numero = referencia.numero_processo_detectado
            if numero is None or numero in ja_consultados:
                continue
            ja_consultados.add(numero)

            try:
                dados = await self._process_number_lookup.find_by_number(numero)
            except ProcessLookupError:
                lookup_falhou = True
                continue

            if dados is not None:
                confirmados.append(
                    ProcessoConfirmado(
                        dados=dados,
                        relacionado_a=referencia.relacionado_a,
                        tipo_relacionado=referencia.tipo_relacionado,
                        confianca=referencia.confianca,
                        origem=referencia,
                    )
                )

        return confirmados, lookup_falhou


def _extrair_numero_processo(texto: str) -> str | None:
    match = _NUMERO_PROCESSO_PATTERN.search(texto)
    return match.group(0) if match else None


def _build_status(
    *,
    referencias: list[ReferenciaProcessual],
    confirmados: list[ProcessoConfirmado],
    busca_falhou: bool,
    erro_busca: str | None,
    lookup_configurado: bool,
    lookup_falhou: bool,
) -> ConsultaProcessualStatus:
    if confirmados:
        return ConsultaProcessualStatus(status="realizada")

    if referencias:
        motivo = (
            "Referencias publicas encontradas, mas nenhum processo pode ser "
            "confirmado em fonte oficial."
        )
        if not lookup_configurado:
            motivo = (
                "Referencias publicas encontradas, mas nenhuma fonte oficial de "
                "confirmacao por numero de processo esta configurada (DATAJUD_API_KEY)."
            )
        elif lookup_falhou:
            motivo = (
                "Referencias publicas encontradas, mas a fonte oficial (DataJud) "
                "falhou ao confirmar."
            )
        return ConsultaProcessualStatus(status="parcial", motivo=motivo)

    if busca_falhou:
        return ConsultaProcessualStatus(
            status="nao_confirmada",
            motivo=f"Falha ao pesquisar referencias publicas: {erro_busca}",
        )

    return ConsultaProcessualStatus(
        status="nao_confirmada",
        motivo=(
            "Nenhuma fonte publica disponivel permitiu encontrar processos para este identificador."
        ),
    )
