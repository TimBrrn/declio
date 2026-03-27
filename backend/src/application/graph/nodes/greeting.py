from __future__ import annotations

import logging

from langchain_core.messages import AIMessage

from backend.src.application.graph.state import CallState

logger = logging.getLogger(__name__)


def greeting_node(state: CallState) -> dict:
    """Genere le message d'accueil TTS depuis cabinet.message_accueil."""
    cabinet = state["cabinet"]
    accueil = cabinet.format_message_accueil()

    logger.info("Greeting node: cabinet=%s", cabinet.nom_cabinet)
    logger.debug("Greeting text: %.200s", accueil)

    messages = list(state.get("messages", []))
    messages.append(AIMessage(content=accueil))

    return {
        "messages": messages,
        "response_text": accueil,
    }
