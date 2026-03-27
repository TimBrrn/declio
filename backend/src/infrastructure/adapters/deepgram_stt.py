"""DeepgramSTTAdapter — implements STTPort via Deepgram live streaming (SDK v6)."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import deque
from typing import AsyncIterator

from deepgram import DeepgramClient
from deepgram.listen.v1.types.listen_v1results import ListenV1Results

from backend.src.infrastructure.config.settings import settings

logger = logging.getLogger(__name__)


class DeepgramSTTAdapter:
    """Implements STTPort — streams audio to Deepgram, yields (text, confidence)."""

    def __init__(self) -> None:
        self._client = DeepgramClient(api_key=settings.deepgram_api_key)

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[tuple[str, float]]:
        """Stream audio to Deepgram, yield final transcriptions as (text, confidence).

        Uses Deepgram SDK v6 synchronous WebSocket in a background thread,
        bridged to async via queues.
        """
        result_queue: asyncio.Queue[tuple[str, float] | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_message(result: ListenV1Results) -> None:
            alt = result.channel.alternatives[0] if result.channel.alternatives else None
            if not alt or not alt.transcript:
                return

            if result.is_final:
                logger.info(
                    "STT final: '%s' (confidence=%.2f)",
                    alt.transcript,
                    alt.confidence,
                )
                loop.call_soon_threadsafe(
                    result_queue.put_nowait,
                    (alt.transcript, alt.confidence),
                )
            else:
                logger.debug("STT interim: '%s'", alt.transcript)

        def on_error(error: Exception) -> None:
            logger.error("Deepgram error: %s", error)

        socket_client = None

        def _run_deepgram(audio_chunks: deque[bytes], done_event: threading.Event) -> None:
            nonlocal socket_client
            try:
                with self._client.listen.v1.connect(
                    model="nova-2",
                    language="fr",
                    encoding="mulaw",
                    sample_rate="8000",
                    punctuate="true",
                    interim_results="true",
                    utterance_end_ms="1000",
                    vad_events="true",
                    endpointing="300",
                ) as sc:
                    socket_client = sc
                    sc.on("Results", on_message)
                    sc.on("Error", on_error)
                    sc.start_listening()

                    while not done_event.is_set():
                        try:
                            chunk = audio_chunks.popleft()
                            sc.send_media(chunk)
                        except IndexError:
                            done_event.wait(timeout=0.01)

                    sc.send_close_stream()
            except Exception as e:
                logger.error("Deepgram connection error: %s", e)
            finally:
                loop.call_soon_threadsafe(result_queue.put_nowait, None)

        audio_chunks: deque[bytes] = deque()
        done_event = threading.Event()

        thread = threading.Thread(
            target=_run_deepgram,
            args=(audio_chunks, done_event),
            daemon=True,
        )
        thread.start()

        async def _feed_audio() -> None:
            try:
                async for chunk in audio_stream:
                    audio_chunks.append(chunk)
            finally:
                done_event.set()

        feed_task = asyncio.create_task(_feed_audio())

        try:
            while True:
                result = await result_queue.get()
                if result is None:
                    break
                yield result
        finally:
            done_event.set()
            feed_task.cancel()
            thread.join(timeout=5)

