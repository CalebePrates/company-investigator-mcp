from company_investigator.infrastructure.browser.html_page_parser import extract_title_and_text


def test_extracts_title_and_visible_text_from_well_formed_html() -> None:
    html = "<html><head><title>Exemplo</title></head><body><p>Ola mundo</p></body></html>"

    titulo, texto = extract_title_and_text(html)

    assert titulo == "Exemplo"
    assert "Ola mundo" in texto


def test_returns_none_title_when_page_has_no_title_tag() -> None:
    html = "<html><body><p>Sem titulo aqui</p></body></html>"

    titulo, texto = extract_title_and_text(html)

    assert titulo is None
    assert "Sem titulo aqui" in texto


def test_returns_none_title_when_title_tag_is_empty() -> None:
    html = "<html><head><title>   </title></head><body><p>Conteudo</p></body></html>"

    titulo, texto = extract_title_and_text(html)

    assert titulo is None


def test_handles_malformed_html_without_raising() -> None:
    titulo, texto = extract_title_and_text("<<<isso nao e html valido>>>")

    assert titulo is None
    assert isinstance(texto, str)


def test_handles_empty_html_without_raising() -> None:
    titulo, texto = extract_title_and_text("")

    assert titulo is None
    assert texto == ""


def test_strips_script_and_style_content_from_extracted_text() -> None:
    html = (
        "<html><head><title>T</title><style>body { color: red; }</style></head>"
        "<body><script>alert('x')</script><p>Texto visivel</p></body></html>"
    )

    _, texto = extract_title_and_text(html)

    assert "Texto visivel" in texto
    assert "color: red" not in texto
    assert "alert" not in texto
