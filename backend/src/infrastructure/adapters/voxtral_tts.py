"""VoxtralTTSAdapter — implements TTSPort via Voxtral TTS streaming.

Uses mistralai SDK for low-latency French speech synthesis.
Outputs PCM then converts to G.711 ulaw 8kHz for Telnyx telephony.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import AsyncIterator

from backend.src.infrastructure.audio.audio_codecs import pcm24k_to_ulaw8k

logger = logging.getLogger(__name__)

TTS_MODEL = "voxtral-mini-tts-2603"


class VoxtralTTSAdapter:
    """Implements TTSPort — streams text to Voxtral TTS, yields audio chunks (ulaw 8kHz)."""

    model_name: str = TTS_MODEL

    def __init__(self, api_key: str, voice_id: str = "") -> None:
        self._api_key = api_key
        self._voice_id = voice_id

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Send text to Voxtral TTS, yield audio chunks in ulaw 8kHz format.

        Voxtral outputs PCM (float32 or int16) which is converted to
        G.711 ulaw 8kHz for Telnyx telephony.
        """
        if not text.strip():
            return

        from mistralai.client import Mistral

        client = Mistral(api_key=self._api_key)
        loop = asyncio.get_running_loop()

        logger.debug("TTS: synthesizing %d chars", len(text))

        chunk_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

        def _run_tts() -> None:
            """Run synchronous TTS streaming in a thread."""
            try:
                kwargs = {
                    "model": TTS_MODEL,
                    "input": text,
                    "response_format": "pcm",
                    "stream": True,
                }
                if self._voice_id:
                    kwargs["voice_id"] = self._voice_id

                with client.audio.speech.complete(**kwargs) as stream:
                    pcm_buffer = b""
                    for event in stream:
                        if hasattr(event, "data") and hasattr(event.data, "audio_data"):
                            pcm_chunk = base64.b64decode(event.data.audio_data)
                            pcm_buffer += pcm_chunk

                            # Process in 6-byte-aligned chunks (for 24kHz→8kHz 3:1 downsample)
                            usable = len(pcm_buffer) - (len(pcm_buffer) % 6)
                            if usable >= 4800:  # ~0.1s of audio
                                ulaw = pcm24k_to_ulaw8k(pcm_buffer[:usable])
                                pcm_buffer = pcm_buffer[usable:]
                                if ulaw:
                                    loop.call_soon_threadsafe(
                                        chunk_queue.put_nowait, ulaw
                                    )

                    # Flush remaining buffer
                    if pcm_buffer:
                        ulaw = pcm24k_to_ulaw8k(pcm_buffer)
                        if ulaw:
                            loop.call_soon_threadsafe(
                                chunk_queue.put_nowait, ulaw
                            )
            except Exception as e:
                logger.error("Voxtral TTS error: %s", e)
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
