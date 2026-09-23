from dataclasses import dataclass, field

from company_investigator.domain.entities.socio import Socio


@dataclass(frozen=True)
class Company:
    cnpj: str
    razao_social: str
    nome_fantasia: str
    situacao: str
    endereco: str | None = None
    socios: list[Socio] = field(default_factory=list)
