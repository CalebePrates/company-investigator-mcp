import dataclasses

import pytest

from company_investigator.domain.entities.public_page_info import PublicPageInfo


def test_is_immutable() -> None:
    page_info = PublicPageInfo(url="https://example.com/", titulo="Example", texto="conteudo")

    with pytest.raises(dataclasses.FrozenInstanceError):
        page_info.titulo = "outro"  # type: ignore[misc]


def test_allows_a_missing_title() -> None:
    page_info = PublicPageInfo(url="https://example.com/", titulo=None, texto="conteudo")

    assert page_info.titulo is None
