from __future__ import annotations

import re
from dataclasses import dataclass

_CNPJ_LENGTH = 14
_PUNCTUATION = re.compile(r"[.\-/\s]")
_FIRST_DIGIT_WEIGHTS = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_SECOND_DIGIT_WEIGHTS = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


class InvalidCnpjError(ValueError):
    """CNPJ com formato ou digitos verificadores invalidos."""


@dataclass(frozen=True)
class Cnpj:
    """Value object que representa um CNPJ ja normalizado e validado."""

    value: str

    @staticmethod
    def normalize(raw: str) -> str:
        """Remove pontuacao comum (. - / espaco), sem validar o resultado."""
        return _PUNCTUATION.sub("", raw or "")

    @classmethod
    def parse(cls, raw: str) -> Cnpj:
        """Normaliza e valida um CNPJ, levantando InvalidCnpjError se invalido."""
        if not raw or not raw.strip():
            raise InvalidCnpjError("CNPJ nao pode ser vazio.")

        digits = cls.normalize(raw)

        if not digits.isdigit():
            raise InvalidCnpjError("CNPJ deve conter apenas digitos e pontuacao (. - /).")

        if len(digits) != _CNPJ_LENGTH:
            raise InvalidCnpjError(f"CNPJ deve ter {_CNPJ_LENGTH} digitos, recebido {len(digits)}.")

        if not _has_valid_check_digits(digits):
            raise InvalidCnpjError("CNPJ possui digitos verificadores invalidos.")

        return cls(value=digits)

    def __str__(self) -> str:
        return self.value


def _calculate_check_digit(base_digits: str, weights: tuple[int, ...]) -> int:
    total = sum(int(digit) * weight for digit, weight in zip(base_digits, weights, strict=True))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def _has_valid_check_digits(digits: str) -> bool:
    first_digit = _calculate_check_digit(digits[:12], _FIRST_DIGIT_WEIGHTS)
    second_digit = _calculate_check_digit(digits[:12] + str(first_digit), _SECOND_DIGIT_WEIGHTS)
    return digits[12:14] == f"{first_digit}{second_digit}"
