from dataclasses import dataclass


@dataclass(frozen=True)
class Socio:
    nome: str
    qualificacao: str
    documento: str | None = None  # CPF mascarado (ex.: "***112108**"), quando disponivel
