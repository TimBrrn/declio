"""Dependency injection providers — centralized adapter creation.

All adapters are instantiated here based on settings.stt_provider,
settings.llm_provider, settings.tts_provider. Webhook and pipeline
get their dependencies through FastAPI Depends().

Adapters are created lazily (on first call) to avoid import-time failures
in tests that override dependencies.
"""

import logging

from sqlmodel import Session

from backend.src.infrastructure.adapters.telnyx_telephony import (
    TelnyxTelephonyAdapter,
)
from backend.src.infrastructure.config.settings import settings
from backend.src.infrastructure.persistence.database import engine

logger = logging.getLogger(__name__)

# ── Singleton adapters (lazy) ─────────────────────────────────────────────────

_telephony_adapter = TelnyxTelephonyAdapter()

_stt_adapter = None
_tts_adapter = None
_conversation_adapter = None
_calendar_adapter = None


def _create_stt_adapter():
    """Create STT adapter based on settings.stt_provider."""
    if settings.stt_provider == "deepgram":
        from backend.src.infrastructure.adapters.deepgram_stt import DeepgramSTTAdapter
        logger.info("STT provider: Deepgram")
        return DeepgramSTTAdapter()
    else:
        from backend.src.infrastructure.adapters.voxtral_stt import VoxtralSTTAdapter
        logger.info("STT provider: Voxtral")
        return VoxtralSTTAdapter(api_key=settings.mistral_api_key)


def _create_tts_adapter():
    """Create TTS adapter based on settings.tts_provider."""
    if settings.tts_provider == "elevenlabs":
        from backend.src.infrastructure.adapters.elevenlabs_tts import ElevenLabsTTSAdapter
        logger.info("TTS provider: ElevenLabs")
        return ElevenLabsTTSAdapter()
    elif settings.tts_provider == "openai":
        from backend.src.infrastructure.adapters.openai_tts import OpenAITTSAdapter
        logger.info("TTS provider: OpenAI")
        return OpenAITTSAdapter()
    else:
        from backend.src.infrastructure.adapters.voxtral_tts import VoxtralTTSAdapter
        logger.info("TTS provider: Voxtral")
        return VoxtralTTSAdapter(api_key=settings.mistral_api_key)


def _create_conversation_adapter():
    """Create LLM conversation adapter based on settings.llm_provider."""
    if settings.llm_provider == "openai":
        from backend.src.infrastructure.adapters.openai_conversation import (
            OpenAIConversationAdapter,
        )
        logger.info("LLM provider: OpenAI GPT-4o")
        return OpenAIConversationAdapter(api_key=settings.openai_api_key)
    else:
        from backend.src.infrastructure.adapters.mistral_conversation import (
            MistralConversationAdapter,
        )
        logger.info("LLM provider: Mistral Small")
        return MistralConversationAdapter(api_key=settings.mistral_api_key)


def _create_calendar_adapter():
    """Create calendar adapter — internal DB calendar (replaces Google)."""
    from backend.src.infrastructure.adapters.internal_calendar import (
        InternalCalendarAdapter,
    )

    def session_factory():
        return Session(engine)

    logger.info("Calendar provider: Internal DB")
    return InternalCalendarAdapter(session_factory)


# ── FastAPI Depends() providers ───────────────────────────────────────────────


def get_db_session():
    with Session(engine) as session:
        yield session


def get_telephony():
    return _telephony_adapter


def get_stt():
    global _stt_adapter
    if _stt_adapter is None:
        _stt_adapter = _create_stt_adapter()
    return _stt_adapter


def get_tts():
    global _tts_adapter
    if _tts_adapter is None:
        _tts_adapter = _create_tts_adapter()
    return _tts_adapter


def get_conversation():
    global _conversation_adapter
    if _conversation_adapter is None:
        _conversation_adapter = _create_conversation_adapter()
    return _conversation_adapter


def get_calendar():
    global _calendar_adapter
    if _calendar_adapter is None:
        _calendar_adapter = _create_calendar_adapter()
    return _calendar_adapter
