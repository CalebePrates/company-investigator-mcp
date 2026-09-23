import httpx
from pydantic import BaseModel, ValidationError

from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.socio import Socio
from company_investigator.domain.ports.company_repository import (
    CompanyRepositoryError,
    CompanyRepositoryPort,
)
from company_investigator.domain.value_objects.cnpj import Cnpj

_BASE_URL = "https://brasilapi.com.br/api/cnpj/v1"


class _BrasilApiPartner(BaseModel):
    nome_socio: str
    qualificacao_socio: str
    cnpj_cpf_do_socio: str | None = None


class _BrasilApiCompanyResponse(BaseModel):
    """Formato (parcial) do payload de sucesso da BrasilAPI, so os campos usados aqui."""

    cnpj: str
    razao_social: str
    nome_fantasia: str | None = None
    descricao_situacao_cadastral: str
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    municipio: str | None = None
    uf: str | None = None
    cep: str | None = None
    qsa: list[_BrasilApiPartner] = []

    def endereco_formatado(self) -> str | None:
        partes = [
            " ".join(p for p in (self.logradouro, self.numero) if p),
            self.complemento,
            self.bairro,
            " - ".join(p for p in (self.municipio, self.uf) if p),
            self.cep,
        ]
        endereco = ", ".join(p for p in partes if p)
        return endereco or None


class BrasilApiCompanyRepository(CompanyRepositoryPort):
    """Busca dados de empresas na BrasilAPI (https://brasilapi.com.br), publica e sem
    necessidade de chave de acesso: GET /api/cnpj/v1/{cnpj}."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def find_by_cnpj(self, cnpj: Cnpj) -> Company | None:
        try:
            response = await self._client.get(f"{_BASE_URL}/{cnpj.value}")
        except httpx.TimeoutException as exc:
            raise CompanyRepositoryError(
                f"Tempo limite excedido ao consultar o CNPJ {cnpj.value} na BrasilAPI."
            ) from exc
        except httpx.HTTPError as exc:
            raise CompanyRepositoryError(
                f"Falha de comunicacao ao consultar o CNPJ {cnpj.value} na BrasilAPI."
            ) from exc

        if response.status_code == 404:
            return None

        if response.status_code != 200:
            raise CompanyRepositoryError(
                f"BrasilAPI retornou status {response.status_code} para o CNPJ {cnpj.value}."
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise CompanyRepositoryError(
                f"BrasilAPI retornou uma resposta que nao e JSON valido para o CNPJ {cnpj.value}."
            ) from exc

        try:
            parsed = _BrasilApiCompanyResponse.model_validate(payload)
        except ValidationError as exc:
            raise CompanyRepositoryError(
                f"BrasilAPI retornou um formato de resposta inesperado para o CNPJ {cnpj.value}."
            ) from exc

        return Company(
            cnpj=parsed.cnpj,
            razao_social=parsed.razao_social,
            nome_fantasia=parsed.nome_fantasia or "",
            situacao=parsed.descricao_situacao_cadastral,
            endereco=parsed.endereco_formatado(),
            socios=[
                Socio(
                    nome=p.nome_socio,
                    qualificacao=p.qualificacao_socio,
                    documento=p.cnpj_cpf_do_socio,
                )
                for p in parsed.qsa
            ],
        )
