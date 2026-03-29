"""OpenAITTSAdapter — implements TTSPort via OpenAI TTS API (streaming).

20x cheaper than ElevenLabs ($0.015/1K chars vs $0.30/1K chars).
Outputs PCM 24kHz 16-bit which is converted to G.711 μ-law 8kHz for telephony.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from openai import OpenAI

from backend.src.infrastructure.audio.audio_codecs import pcm24k_to_ulaw8k
from backend.src.infrastructure.config.settings import settings

logger = logging.getLogger(__name__)

# PCM chunk size: must be divisible by 6 (2 bytes × 3 for 24→8kHz downsample)
# 4800 bytes = 2400 samples → 800 ulaw bytes (0.1s at 8kHz)
_PCM_CHUNK_SIZE = 4800


class OpenAITTSAdapter:
    """Implements TTSPort — streams text to OpenAI TTS, yields audio chunks (ulaw 8kHz)."""

    model_name: str = "tts-1"

    def __init__(self) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._voice = "nova"  # warm female voice, good for French

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Send text to OpenAI TTS, yield audio chunks in ulaw 8kHz format.

        OpenAI TTS is synchronous — run in a thread executor.
        """
        if not text.strip():
            return

        loop = asyncio.get_running_loop()
        chunk_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

        def _run_tts() -> None:
            try:
                with self._client.audio.speech.with_streaming_response.create(
                    model="tts-1",
                    voice=self._voice,
                    input=text,
                    response_format="pcm",  # raw PCM 24kHz 16-bit LE mono
                ) as response:
                    buffer = b""
                    for pcm_chunk in response.iter_bytes(chunk_size=_PCM_CHUNK_SIZE):
                        buffer += pcm_chunk
                        # Process in clean 6-byte-aligned chunks
                        usable = len(buffer) - (len(buffer) % 6)
                        if usable > 0:
                            ulaw = pcm24k_to_ulaw8k(buffer[:usable])
                            buffer = buffer[usable:]
                            loop.call_soon_threadsafe(
                                chunk_queue.put_nowait, ulaw
                            )
                    # Flush remaining buffer
                    if buffer:
                        ulaw = pcm24k_to_ulaw8k(buffer)
                        if ulaw:
                            loop.call_soon_threadsafe(
                                chunk_queue.put_nowait, ulaw
                            )
            except Exception as e:
                logger.error("OpenAI TTS error: %s", e)
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
