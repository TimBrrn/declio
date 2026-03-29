"""Health check endpoint — reports status of all services."""

import logging

from fastapi import APIRouter, Depends
from sqlmodel import Session, text

from backend.src.api.dependencies import get_db_session
from backend.src.infrastructure.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check(session: Session = Depends(get_db_session)):
    """Return health status of all services. Public — no auth required."""
    services = {}

    # Database
    try:
        session.exec(text("SELECT 1"))
        services["database"] = "ok"
    except Exception as e:
        logger.error("Health check — database error: %s", e)
        services["database"] = "error"

    # Telnyx — check API key is configured
    services["telnyx"] = "ok" if settings.telnyx_api_key else "error"

    # Mistral — single key for STT + LLM + TTS (new stack)
    services["mistral"] = "ok" if settings.mistral_api_key else "error"

    # Legacy providers — only check if actively selected
    if settings.stt_provider == "deepgram":
        services["deepgram"] = "ok" if settings.deepgram_api_key else "error"
    if settings.llm_provider == "openai" or settings.tts_provider == "openai":
        services["openai"] = "ok" if settings.openai_api_key else "error"
    if settings.tts_provider == "elevenlabs":
        services["elevenlabs"] = "ok" if settings.elevenlabs_api_key else "error"

    all_ok = all(v == "ok" for v in services.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "services": services,
        "version": "0.1.0",
    }
