from dataclasses import dataclass


@dataclass(frozen=True)
class PublicPageInfo:
    url: str
    titulo: str | None
    texto: str
