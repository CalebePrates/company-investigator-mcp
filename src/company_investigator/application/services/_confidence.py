from company_investigator.domain.entities.investigation import ConfidenceLevel

_STOPWORDS = {"empresa", "ltda", "sa", "s/a", "me", "eireli", "ltd", "inc", "grupo", "group"}


def classify_name_match(nome_esperado: str, *textos: str) -> ConfidenceLevel:
    """Heuristica simples: compara os tokens distintivos (>2 letras, sem termos
    genericos como 'empresa'/'ltda') do nome esperado contra o texto encontrado
    (titulo/snippet de um resultado de busca). Nao ha confirmacao real de identidade
    aqui, apenas uma estimativa proporcional para fins didaticos: todos os tokens
    presentes -> ALTA, alguns -> MEDIA, nenhum -> BAIXA."""
    tokens = [t for t in nome_esperado.lower().split() if len(t) > 2 and t not in _STOPWORDS]
    if not tokens:
        return ConfidenceLevel.BAIXA

    haystack = " ".join(textos).lower()
    matches = sum(1 for token in tokens if token in haystack)

    if matches == len(tokens):
        return ConfidenceLevel.ALTA
    if matches > 0:
        return ConfidenceLevel.MEDIA
    return ConfidenceLevel.BAIXA
