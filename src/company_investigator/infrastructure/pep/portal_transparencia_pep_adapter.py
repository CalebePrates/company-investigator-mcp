import httpx
from pydantic import BaseModel, ValidationError

from company_investigator.domain.ports.pep_lookup import (
    PEPLookupError,
    PEPLookupPort,
    RegistroPEPBruto,
)

_ENDPOINT = "https://api.portaldatransparencia.gov.br/api-de-dados/peps"


class _PEPDTO(BaseModel):
    cpf: str | None = None
    nome: str
    descricao_funcao: str | None = None
    nome_orgao: str | None = None
    dt_inicio_exercicio: str | None = None
    dt_fim_exercicio: str | None = None
    dt_fim_carencia: str | None = None


class PortalTransparenciaPEPAdapter(PEPLookupPort):
    """Consulta o cadastro oficial de Pessoas Expostas Politicamente via a API de
    Dados do Portal da Transparencia (CGU): GET /api-de-dados/peps, autenticado
    pelo header 'chave-api-dados'. Chave gratuita, obtida em
    https://www.portaldatransparencia.gov.br/api-de-dados/cadastrar-email"""

    def __init__(self, client: httpx.AsyncClient, api_key: str) -> None:
        self._client = client
        self._api_key = api_key

    async def search(self, nome: str, cpf: str | None = None) -> list[RegistroPEPBruto]:
        params: dict[str, str | int] = {"nome": nome, "pagina": 1}
        if cpf:
            params["cpf"] = cpf

        try:
            response = await self._client.get(
                _ENDPOINT, params=params, headers={"chave-api-dados": self._api_key}
            )
        except httpx.TimeoutException as exc:
            raise PEPLookupError(f"Tempo limite excedido ao consultar PEP para '{nome}'.") from exc
        except httpx.HTTPError as exc:
            raise PEPLookupError(f"Falha de comunicacao ao consultar PEP para '{nome}'.") from exc

        if response.status_code == 401:
            raise PEPLookupError(
                "Portal da Transparencia rejeitou a API key (autenticacao invalida)."
            )

        if response.status_code != 200:
            raise PEPLookupError(
                f"Portal da Transparencia retornou status {response.status_code} para '{nome}'."
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise PEPLookupError(
                f"Portal da Transparencia retornou uma resposta que nao e JSON "
                f"valido para '{nome}'."
            ) from exc

        try:
            parsed = [_PEPDTO.model_validate(item) for item in payload]
        except ValidationError as exc:
            raise PEPLookupError(
                f"Portal da Transparencia retornou um formato de resposta inesperado para '{nome}'."
            ) from exc

        return [
            RegistroPEPBruto(
                cpf=item.cpf,
                nome=item.nome,
                funcao=item.descricao_funcao,
                orgao=item.nome_orgao,
                data_inicio=item.dt_inicio_exercicio,
                data_fim=item.dt_fim_exercicio,
                data_fim_carencia=item.dt_fim_carencia,
            )
            for item in parsed
        ]
