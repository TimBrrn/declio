from __future__ import annotations

import re
from dataclasses import dataclass

# Format FR : 06/07 + 8 chiffres, ou +33 6/7 + 8 chiffres
_PATTERN_LOCAL = re.compile(r"^0[67]\d{8}$")
_PATTERN_INTL = re.compile(r"^\+33[67]\d{8}$")


@dataclass(frozen=True)
class PhoneNumber:
    """Numero de telephone francais valide."""

    value: str

    def __post_init__(self) -> None:
        cleaned = self.value.replace(" ", "").replace(".", "").replace("-", "")
        # Use object.__setattr__ because frozen dataclass
        object.__setattr__(self, "value", cleaned)
        if not (_PATTERN_LOCAL.match(cleaned) or _PATTERN_INTL.match(cleaned)):
            raise ValueError(
                f"Numero de telephone invalide : {self.value}. "
                "Format attendu : 06/07XXXXXXXX ou +336/7XXXXXXXX"
            )

    def to_international(self) -> str:
        if self.value.startswith("+33"):
            return self.value
        return "+33" + self.value[1:]

    def __str__(self) -> str:
        return self.value
