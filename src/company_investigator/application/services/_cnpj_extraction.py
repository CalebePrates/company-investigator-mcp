import re

_CNPJ_CANDIDATE_PATTERN = re.compile(r"\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}")


def extract_cnpj_candidates(*textos: str) -> set[str]:
    """Extrai substrings com formato de CNPJ (com ou sem pontuacao) de um texto
    livre. Sao apenas candidatos - quem chama ainda precisa validar (Cnpj.parse)
    e confirmar contra uma fonte oficial antes de tratar como uma empresa real."""
    texto = " ".join(textos)
    return {match.group(0) for match in _CNPJ_CANDIDATE_PATTERN.finditer(texto)}
