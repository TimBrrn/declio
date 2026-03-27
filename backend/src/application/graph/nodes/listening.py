from __future__ import annotations

import logging

from langchain_core.messages import AIMessage, HumanMessage

from backend.src.application.graph.state import CallState

logger = logging.getLogger(__name__)

LOW_CONFIDENCE_THRESHOLD = 0.6


def listening_node(state: CallState) -> dict:
    """Traite la transcription STT recue.

    Si la confidence est trop basse, ajoute une demande de repetition.
    """
    transcript = state.get("current_transcript", "")
    confidence = state.get("stt_confidence", 0.0)

    logger.info("Listening node: transcript_len=%d confidence=%.2f", len(transcript), confidence)
    logger.debug("Transcript: %.200s", transcript)

    messages = list(state.get("messages", []))

    if transcript:
        messages.append(HumanMessage(content=transcript))

    if confidence < LOW_CONFIDENCE_THRESHOLD and transcript:
        logger.warning(
            "Low STT confidence=%.2f (threshold=%.2f), asking repetition",
            confidence,
            LOW_CONFIDENCE_THRESHOLD,
        )
        messages.append(
            AIMessage(
                content="Excusez-moi, je n'ai pas bien compris. "
                "Pourriez-vous repeter s'il vous plait ?"
            )
        )
        return {
            "messages": messages,
            "response_text": (
                "Excusez-moi, je n'ai pas bien compris. "
                "Pourriez-vous repeter s'il vous plait ?"
            ),
        }

    return {"messages": messages}
