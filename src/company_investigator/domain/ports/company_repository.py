from abc import ABC, abstractmethod

from company_investigator.domain.entities.company import Company
from company_investigator.domain.value_objects.cnpj import Cnpj


class CompanyRepositoryError(Exception):
    """Falha de infraestrutura ao consultar uma implementacao de CompanyRepositoryPort.

    Implementacoes devem levantar este erro (ou uma subclasse) para problemas de
    comunicacao com a fonte de dados (timeout, erro HTTP, resposta em formato
    inesperado etc.) e retornar None apenas quando a fonte confirma que a empresa
    nao existe.
    """


class CompanyRepositoryPort(ABC):
    @abstractmethod
    async def find_by_cnpj(self, cnpj: Cnpj) -> Company | None: ...
