from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.src.domain.value_objects.phone_number import PhoneNumber


@dataclass(frozen=True)
class PatientContact:
    """Contact patient immutable."""

    phone: PhoneNumber
    name: str | None = None
