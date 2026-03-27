from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TimeSlot:
    """Creneau horaire immutable."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(
                f"end ({self.end}) doit etre apres start ({self.start})"
            )

    @property
    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() / 60)

    def overlaps(self, other: TimeSlot) -> bool:
        """Retourne True si les deux creneaux se chevauchent."""
        return self.start < other.end and other.start < self.end
