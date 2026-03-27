"""ElevenLabsTTSAdapter — implements TTSPort via ElevenLabs streaming API."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from elevenlabs import ElevenLabs

from backend.src.infrastructure.config.settings import settings

logger = logging.getLogger(__name__)

# Default French voice — override with ELEVENLABS_VOICE_ID in .env
DEFAULT_VOICE_ID = "pFZP5JQG7iQjIQuC4Bku"  # ElevenLabs "Lily" (French)


class ElevenLabsTTSAdapter:
    """Implements TTSPort — streams text to ElevenLabs, yields audio chunks (mulaw 8kHz)."""

    def __init__(self) -> None:
        self._client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        self._voice_id = settings.elevenlabs_voice_id or DEFAULT_VOICE_ID

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Send text to ElevenLabs, yield audio chunks in ulaw_8000 format.

        ElevenLabs SDK stream() is synchronous — we run it in a thread executor
        to avoid blocking the event loop.
        """
        if not text.strip():
            return

        logger.info("TTS: synthesizing %d chars", len(text))
        loop = asyncio.get_running_loop()
        chunk_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

        def _run_tts() -> None:
            try:
                audio_iter = self._client.text_to_speech.stream(
                    voice_id=self._voice_id,
                    text=text,
                    output_format="ulaw_8000",
                    model_id="eleven_multilingual_v2",
                    language_code="fr",
                )
                for chunk in audio_iter:
                    loop.call_soon_threadsafe(chunk_queue.put_nowait, chunk)
            except Exception as e:
                logger.error("ElevenLabs TTS error: %s", e)
            finally:
                loop.call_soon_threadsafe(chunk_queue.put_nowait, None)

        thread_future = loop.run_in_executor(None, _run_tts)

        try:
            while True:
                chunk = await chunk_queue.get()
                if chunk is None:
                    break
                yield chunk
        finally:
            await thread_future
