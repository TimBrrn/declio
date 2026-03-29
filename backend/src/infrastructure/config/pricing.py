"""Provider-aware pricing helpers.

These functions depend on settings (infrastructure layer) and must NOT live
in the domain layer.  The domain keeps the static pricing constants only.
"""

from __future__ import annotations

from backend.src.domain.value_objects.token_usage import (
    DEEPGRAM_PRICE_PER_MINUTE,
    ELEVENLABS_PRICE_PER_1K_CHARS,
    OPENAI_TTS_PRICE_PER_1K_CHARS,
    VOXTRAL_STT_PRICE_PER_MINUTE,
    VOXTRAL_TTS_PRICE_PER_1K_CHARS,
)
from backend.src.infrastructure.config.settings import settings


def get_stt_price_per_minute() -> float:
    """Return the active STT price based on settings.stt_provider."""
    if getattr(settings, "stt_provider", "voxtral") == "deepgram":
        return DEEPGRAM_PRICE_PER_MINUTE
    return VOXTRAL_STT_PRICE_PER_MINUTE


def get_tts_price_per_1k_chars() -> float:
    """Return the active TTS price based on settings.tts_provider."""
    provider = getattr(settings, "tts_provider", "voxtral")
    if provider == "elevenlabs":
        return ELEVENLABS_PRICE_PER_1K_CHARS
    elif provider == "openai":
        return OPENAI_TTS_PRICE_PER_1K_CHARS
    return VOXTRAL_TTS_PRICE_PER_1K_CHARS
