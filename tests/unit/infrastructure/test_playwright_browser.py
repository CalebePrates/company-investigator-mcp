"""Usa o Playwright real, mas apontando para uma pasta de navegadores vazia: o
lancamento falha localmente (sem rede, sem abrir navegador), exatamente como numa
instalacao nova via pip/uvx em que o Chromium ainda nao foi baixado."""

import pytest

from company_investigator.domain.ports.browser import BrowserError
from company_investigator.infrastructure.browser.playwright_browser import PlaywrightBrowser


@pytest.mark.asyncio
async def test_missing_chromium_raises_error_explaining_how_to_install_it(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))

    with pytest.raises(BrowserError) as exc_info:
        await PlaywrightBrowser().fetch_page("https://example.com/")

    message = str(exc_info.value)
    assert "Chromium" in message
    assert "playwright install chromium" in message
    assert "uvx --from company-investigator-mcp playwright install chromium" in message
