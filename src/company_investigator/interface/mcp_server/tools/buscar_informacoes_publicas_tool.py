from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, HttpUrl, ValidationError

from company_investigator.application.use_cases.buscar_informacoes_publicas_use_case import (
    BuscarInformacoesPublicasUseCase,
)
from company_investigator.domain.entities.public_page_info import PublicPageInfo
from company_investigator.domain.ports.browser import BrowserError

_DESCRIPTION = (
    "Abre uma URL publica com um navegador headless e extrai informacoes basicas da "
    "pagina: titulo e texto visivel. Nao interage com formularios nem executa acoes "
    "na pagina, apenas le o conteudo apos o carregamento. Parametro 'url' (string, "
    "obrigatorio): precisa ser uma URL http/https valida e publicamente acessivel. "
    "Retorna um objeto com 'url', 'titulo' (pode ser nulo se a pagina nao tiver a "
    "tag <title> ou ela estiver vazia) e 'texto' (texto visivel extraido da pagina, "
    "sem scripts/estilos). Erros possiveis: URL invalida, timeout ao carregar a "
    "pagina, ou falha de navegacao."
)


class BuscarInformacoesPublicasInput(BaseModel):
    """Modelo validado: garante que a URL recebida pela tool e http/https bem formada."""

    url: HttpUrl


class BuscarInformacoesPublicasOutput(BaseModel):
    """Resposta estruturada retornada pela tool buscar_informacoes_publicas."""

    url: str
    titulo: str | None
    texto: str

    @classmethod
    def from_entity(cls, page_info: PublicPageInfo) -> BuscarInformacoesPublicasOutput:
        return cls(url=page_info.url, titulo=page_info.titulo, texto=page_info.texto)


def _first_error_message(exc: ValidationError) -> str:
    errors = exc.errors()
    return str(errors[0]["msg"]) if errors else str(exc)


def register_buscar_informacoes_publicas_tool(
    server: MCPServer, use_case: BuscarInformacoesPublicasUseCase
) -> None:
    @server.tool(name="buscar_informacoes_publicas", description=_DESCRIPTION)
    async def buscar_informacoes_publicas(url: str) -> dict[str, str | None]:
        try:
            validated = BuscarInformacoesPublicasInput(url=url)
        except ValidationError as exc:
            raise ToolError(_first_error_message(exc)) from exc

        try:
            page_info = await use_case.execute(str(validated.url))
        except BrowserError as exc:
            raise ToolError(str(exc)) from exc

        return BuscarInformacoesPublicasOutput.from_entity(page_info).model_dump()
