from __future__ import annotations

import logging

from backend.src.application.graph.state import CallState

logger = logging.getLogger(__name__)


def responding_node(state: CallState) -> dict:
    """Prepare la reponse pour le TTS streaming.

    Le texte est dans state["response_text"]. Le pipeline audio
    (infrastructure) se chargera du streaming TTS reel.
    """
    response_text = state.get("response_text", "")
    logger.info("Responding node: response_len=%d", len(response_text))
    logger.debug("Response text: %.200s", response_text)
    return {
        "response_text": response_text,
    }
