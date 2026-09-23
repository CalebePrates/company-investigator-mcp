import json

import pytest

from company_investigator.domain.entities.company import Company
from company_investigator.domain.entities.socio import Socio
from company_investigator.domain.ports.company_repository import CompanyRepositoryPort
from company_investigator.domain.value_objects.cnpj import Cnpj
from company_investigator.infrastructure.search.unconfigured_search_provider import (
    UnconfiguredSearchProvider,
)
from company_investigator.interface.mcp_server.server import build_server

_EMPRESA = Company(
    cnpj="11444777000161",
    razao_social="Empresa Exemplo LTDA",
    nome_fantasia="Empresa Exemplo",
    situacao="ATIVA",
    socios=[
        Socio(nome="Joana Silva", qualificacao="Socia-Administradora"),
        Socio(nome="Carlos Souza", qualificacao="Socio"),
        Socio(nome="Marta Lima", qualificacao="Socia"),
    ],
)


class FakeCompanyRepository(CompanyRepositoryPort):
    async def find_by_cnpj(self, cnpj: Cnpj) -> Company | None:
        return _EMPRESA if cnpj.value == _EMPRESA.cnpj else None


async def _server_and_id() -> tuple[object, str]:
    server = build_server(
        company_repository=FakeCompanyRepository(),
        search_provider=UnconfiguredSearchProvider(),
    )
    result = await server.call_tool("investigar_empresa", {"identificador": "11.444.777/0001-61"})
    return server, result.structured_content["investigation_id"]


async def _read_json(server, uri: str) -> dict:
    contents = list(await server.read_resource(uri))
    assert len(contents) == 1
    assert contents[0].mime_type == "application/json"
    return json.loads(contents[0].content)


@pytest.mark.asyncio
async def test_resource_template_is_advertised() -> None:
    server, _ = await _server_and_id()

    templates = await server.list_resource_templates()

    assert any(t.uri_template.startswith("investigation://{investigation_id}/") for t in templates)


@pytest.mark.asyncio
async def test_resource_index_matches_the_tool_index() -> None:
    server, investigation_id = await _server_and_id()

    indice = await _read_json(server, f"investigation://{investigation_id}/index")

    assert indice["investigation_id"] == investigation_id
    assert indice["empresa"]["cnpj"] == "11444777000161"
    socios = next(s for s in indice["secoes"] if s["nome"] == "socios")
    assert socios["total_itens"] == 3


@pytest.mark.asyncio
async def test_resource_section_returns_the_first_page_by_default() -> None:
    server, investigation_id = await _server_and_id()

    pagina = await _read_json(server, f"investigation://{investigation_id}/socios")

    assert pagina["secao"] == "socios"
    assert pagina["pagina"] == 1
    assert pagina["total_itens"] == 3
    assert [s["nome"] for s in pagina["itens"]] == ["Joana Silva", "Carlos Souza", "Marta Lima"]


@pytest.mark.asyncio
async def test_resource_can_be_paginated_through_query_parameters() -> None:
    server, investigation_id = await _server_and_id()
    base = f"investigation://{investigation_id}/socios"

    primeira = await _read_json(server, f"{base}?pagina=1&tamanho_pagina=2")
    ultima = await _read_json(server, f"{base}?pagina=2&tamanho_pagina=2")

    assert primeira["total_paginas"] == 2
    assert [s["nome"] for s in primeira["itens"]] == ["Joana Silva", "Carlos Souza"]
    assert [s["nome"] for s in ultima["itens"]] == ["Marta Lima"]


@pytest.mark.asyncio
async def test_resource_pagination_matches_the_tool_page_for_page() -> None:
    server, investigation_id = await _server_and_id()

    via_resource = await _read_json(
        server, f"investigation://{investigation_id}/socios?pagina=2&tamanho_pagina=2"
    )
    via_tool = (
        await server.call_tool(
            "obter_secao_investigacao",
            {
                "investigation_id": investigation_id,
                "secao": "socios",
                "pagina": 2,
                "tamanho_pagina": 2,
            },
        )
    ).structured_content

    assert via_resource == via_tool


@pytest.mark.asyncio
async def test_resource_rejects_an_unknown_investigation_id() -> None:
    server, _ = await _server_and_id()

    with pytest.raises(Exception, match="Nenhuma investigacao encontrada"):
        await server.read_resource("investigation://nao-existe/index")


@pytest.mark.asyncio
async def test_resource_rejects_an_unknown_section() -> None:
    server, investigation_id = await _server_and_id()

    with pytest.raises(Exception, match="Secao desconhecida"):
        await server.read_resource(f"investigation://{investigation_id}/nao_existe")


@pytest.mark.asyncio
async def test_resource_rejects_out_of_range_pagination() -> None:
    server, investigation_id = await _server_and_id()

    with pytest.raises(Exception, match="tamanho_pagina deve estar entre 1 e 50"):
        await server.read_resource(f"investigation://{investigation_id}/socios?tamanho_pagina=500")
    with pytest.raises(Exception, match="pagina deve ser >= 1"):
        await server.read_resource(f"investigation://{investigation_id}/socios?pagina=0")
