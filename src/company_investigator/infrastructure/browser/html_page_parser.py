from bs4 import BeautifulSoup

_NON_VISIBLE_TAGS = ("script", "style")


def extract_title_and_text(html: str) -> tuple[str | None, str]:
    """Extrai titulo e texto visivel de um HTML bruto, tolerando entradas malformadas."""
    soup = BeautifulSoup(html or "", "lxml")

    for tag in soup(_NON_VISIBLE_TAGS):
        tag.decompose()

    titulo = None
    if soup.title is not None:
        title_text = soup.title.get_text(strip=True)
        titulo = title_text or None

    texto = soup.get_text(separator=" ", strip=True)

    return titulo, texto
