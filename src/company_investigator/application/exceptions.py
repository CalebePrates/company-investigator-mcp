class CompanyNotFoundError(Exception):
    """Nenhuma empresa foi encontrada para o CNPJ informado."""


class InvestigationNotFoundError(Exception):
    """Nenhuma investigacao guardada corresponde ao investigation_id informado
    (nunca existiu, ou foi descartada pelo limite de capacidade do armazenamento
    em memoria)."""
