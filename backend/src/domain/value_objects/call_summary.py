from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.src.domain.entities.call_record import ScenarioEnum


@dataclass(frozen=True)
class CallSummary:
    """Resume d'appel immutable, utilise pour le SMS au kine."""

    patient_name: str | None
    patient_phone: str
    call_type: ScenarioEnum
    action_taken: str
    is_urgent: bool = False

    def to_sms_text(self) -> str:
        """Formate le SMS comme defini dans le cahier des charges."""
        patient = self.patient_name or "Patient inconnu"
        urgent = " [URGENT]" if self.is_urgent else ""
        return (
            f"[Declio]{urgent} {patient} ({self.patient_phone}) "
            f"- {self.action_taken}."
        )
