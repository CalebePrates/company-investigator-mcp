import dataclasses

import pytest

from company_investigator.domain.entities.company import Company


def test_is_immutable() -> None:
    company = Company(
        cnpj="11444777000161",
        razao_social="Empresa Exemplo LTDA",
        nome_fantasia="Empresa Exemplo",
        situacao="ATIVA",
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        company.situacao = "BAIXADA"  # type: ignore[misc]
