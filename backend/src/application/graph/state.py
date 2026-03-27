from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import BaseMessage

from backend.src.domain.entities.cabinet import Cabinet
from backend.src.domain.entities.call_record import CallRecord, ScenarioEnum
from backend.src.domain.ports.conversation_port import ToolCall


class CallState(TypedDict, total=False):
    """Etat du graphe conversationnel LangGraph."""

    # Contexte cabinet
    cabinet: Cabinet

    # Historique conversation LangChain
    messages: list[BaseMessage]

    # Derniere transcription STT
    current_transcript: str
    stt_confidence: float

    # Scenario detecte
    scenario: ScenarioEnum | None

    # Tool calls en attente
    pending_tool_calls: list[ToolCall]
    tool_results: list[dict[str, Any]]

    # Reponse LLM a envoyer en TTS
    response_text: str

    # Enregistrement appel en cours
    call_record: CallRecord

    # Signaux de controle
    should_hangup: bool

    # ID de l'appel (Telnyx call_control_id)
    call_id: str

    # Fallback universel — message d'erreur
    error: str | None

    # Nom du patient extrait au fil de la conversation
    patient_name: str | None

    # Numero de telephone de l'appelant (rempli par le webhook)
    caller_phone: str | None

    # Message laisse par le patient (via tool leave_message)
    patient_message: str | None

    # Per-LLM-turn token usage data
    token_turns: list[dict[str, Any]]
