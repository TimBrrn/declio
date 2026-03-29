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

    model_name: str = "nova-2"

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

        def on_message(message) -> None:
            # SDK v6 emits all message types via EventType.MESSAGE
            if not isinstance(message, ListenV1Results):
                return

            alt = message.channel.alternatives[0] if message.channel.alternatives else None
            if not alt or not alt.transcript:
                return

            if message.is_final:
                loop.call_soon_threadsafe(
                    result_queue.put_nowait,
                    (alt.transcript, alt.confidence),
                )

        def on_error(error) -> None:
            logger.error("Deepgram error: %s", error)

        socket_client = None

        def _run_deepgram(audio_chunks: deque[bytes], done_event: threading.Event) -> None:
            nonlocal socket_client

            def _send_audio(sc_ref, chunks_ref, done_ref):
                """Send audio chunks to Deepgram (runs in its own thread)."""
                while not done_ref.is_set():
                    try:
                        chunk = chunks_ref.popleft()
                        sc_ref.send_media(chunk)
                    except IndexError:
                        done_ref.wait(timeout=0.01)
                try:
                    sc_ref.send_close_stream()
                except Exception:
                    pass

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
                    sc.on("message", on_message)
                    sc.on("error", on_error)

                    # start_listening() blocks (receive loop), so send audio
                    # from a separate thread
                    send_thread = threading.Thread(
                        target=_send_audio,
                        args=(sc, audio_chunks, done_event),
                        daemon=True,
                    )
                    send_thread.start()

                    # Blocks until Deepgram WS closes
                    sc.start_listening()

                    # WS closed — signal the send thread to stop
                    done_event.set()
                    send_thread.join(timeout=2)
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

