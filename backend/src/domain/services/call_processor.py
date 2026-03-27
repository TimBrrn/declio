from __future__ import annotations

import re

from backend.src.domain.entities.call_record import ScenarioEnum

_BOOKING_KEYWORDS = [
    r"\brdv\b", r"\brendez[- ]?vous\b", r"\bprendre\b.*\b(rdv|rendez)",
    r"\breserver\b", r"\bcreneau\b", r"\bdisponibilite\b",
]
_CANCEL_KEYWORDS = [
    r"\bannuler\b", r"\bannulation\b", r"\bsupprimer\b",
    r"\bdeplacer\b.*\b(rdv|rendez)", r"\bdecommander\b",
]
_FAQ_KEYWORDS = [
    r"\btarif\b", r"\bprix\b", r"\bcombien\b", r"\bhoraires?\b",
    r"\badresse\b", r"\bou se trouve\b", r"\bparking\b",
    r"\bremboursement\b", r"\bmutuelle\b", r"\bdocument\b",
]


class CallProcessor:
    """Detection de scenario a partir d'une transcription — logique pure."""

    def detect_scenario(self, transcript: str) -> ScenarioEnum:
        """Detecte le scenario d'appel a partir de la transcription."""
        text = transcript.lower().strip()

        if not text:
            return ScenarioEnum.OUT_OF_SCOPE

        if self._matches(text, _CANCEL_KEYWORDS):
            return ScenarioEnum.CANCELLATION

        if self._matches(text, _BOOKING_KEYWORDS):
            return ScenarioEnum.BOOKING

        if self._matches(text, _FAQ_KEYWORDS):
            return ScenarioEnum.FAQ

        return ScenarioEnum.OUT_OF_SCOPE

    def _matches(self, text: str, patterns: list[str]) -> bool:
        return any(re.search(p, text) for p in patterns)
