"""VoxtralSTTAdapter — implements STTPort via Voxtral Realtime streaming.

Uses mistralai[realtime] WebSocket API for low-latency French transcription.
Accepts MULAW 8kHz from Telnyx, converts to PCM S16LE internally.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from backend.src.infrastructure.audio.audio_codecs import ulaw8k_to_pcm16k

logger = logging.getLogger(__name__)

STT_MODEL = "mistral-stt-latest"


class VoxtralSTTAdapter:
    """Implements STTPort — streams audio to Voxtral, yields (text, confidence)."""

    model_name: str = STT_MODEL

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[tuple[str, float]]:
        """Stream audio to Voxtral Realtime STT, yield final transcriptions.

        Pipeline converts MULAW 8kHz → PCM S16LE 16kHz before sending
        to Voxtral which expects PCM input.

        Yields:
            (transcript_text, confidence) tuples for each final segment.
        """
        from mistralai.client import Mistral
        from mistralai.extra.realtime import AudioFormat

        client = Mistral(api_key=self._api_key)

        audio_format = AudioFormat(
            encoding="pcm_s16le",
            sample_rate=16000,
        )

        async def _pcm_stream() -> AsyncIterator[bytes]:
            """Convert incoming MULAW audio to PCM for Voxtral."""
            async for mulaw_chunk in audio_stream:
                if mulaw_chunk:
                    pcm_chunk = ulaw8k_to_pcm16k(mulaw_chunk)
                    yield pcm_chunk

        try:
            async for event in client.audio.realtime.transcribe_stream(
                _pcm_stream(),
                audio_format=audio_format,
                query_params={"model": STT_MODEL},
            ):
                # TranscriptionStreamTextDelta has .text attribute
                if hasattr(event, "text") and event.text:
                    text = event.text.strip()
                    if text:
                        # Voxtral doesn't provide per-segment confidence,
                        # use 0.90 as default (high-quality model)
                        yield (text, 0.90)

        except Exception as e:
            logger.error("Voxtral STT error: %s", e)
            raise
