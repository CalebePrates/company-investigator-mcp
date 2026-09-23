import pytest

from company_investigator.domain.value_objects.cnpj import Cnpj, InvalidCnpjError


class TestNormalize:
    def test_strips_punctuation_from_formatted_cnpj(self) -> None:
        assert Cnpj.normalize("12.345.678/0001-90") == "12345678000190"

    def test_keeps_already_normalized_cnpj_unchanged(self) -> None:
        assert Cnpj.normalize("12345678000190") == "12345678000190"


class TestParseValid:
    def test_parses_formatted_cnpj_with_valid_check_digits(self) -> None:
        cnpj = Cnpj.parse("11.444.777/0001-61")

        assert cnpj.value == "11444777000161"

    def test_parses_unformatted_cnpj_with_valid_check_digits(self) -> None:
        cnpj = Cnpj.parse("11444777000161")

        assert cnpj.value == "11444777000161"


class TestParseInvalid:
    def test_rejects_empty_string(self) -> None:
        with pytest.raises(InvalidCnpjError):
            Cnpj.parse("")

    def test_rejects_letters(self) -> None:
        with pytest.raises(InvalidCnpjError):
            Cnpj.parse("abc")

    @pytest.mark.parametrize("raw", ["123", "123456789", "12.345.678/0001"])
    def test_rejects_wrong_amount_of_digits(self, raw: str) -> None:
        with pytest.raises(InvalidCnpjError):
            Cnpj.parse(raw)

    def test_rejects_incorrect_check_digits(self) -> None:
        with pytest.raises(InvalidCnpjError):
            Cnpj.parse("12345678000190")
