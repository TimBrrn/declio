from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ScenarioEnum(Enum):
    BOOKING = "booking"
    CANCELLATION = "cancellation"
    FAQ = "faq"
    OUT_OF_SCOPE = "out_of_scope"
    ERROR = "error"


@dataclass
class CallRecord:
    """Enregistrement metadonnees d'un appel traite."""

    id: str
    cabinet_id: str
    caller_phone: str
    duration_seconds: float = 0.0
    scenario: ScenarioEnum | None = None
    actions_taken: list[str] = field(default_factory=list)
    summary: str = ""
    stt_confidence_score: float = 0.0
    latency_ms: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
