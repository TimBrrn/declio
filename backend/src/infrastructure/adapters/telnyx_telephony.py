import asyncio
import logging
from typing import AsyncIterator

from telnyx import Telnyx

from backend.src.infrastructure.config.settings import settings

logger = logging.getLogger(__name__)

# Backpressure: max audio chunks in send queue (~1s at 50 chunks/s of 20ms ulaw)
SEND_QUEUE_MAXSIZE = 50

# Reconnexion: how long to wait for a new WS to connect after a drop
RECONNECT_TIMEOUT = 5.0


class TelnyxTelephonyAdapter:
    """Implements TelephonyPort using Telnyx SDK v4 + WebSocket audio.

    Connection lifecycle per call:

        call.answered → start_audio_stream() → WS connects
            → audio flows via feed_audio() / send_audio()
            → WS drops → on_ws_disconnect() → retry start_streaming()
                → new WS connects (reuses same queues)
                → OR timeout → end_audio() (permanent cleanup)
        call.hangup → end_audio()
    """

    def __init__(self) -> None:
        self._client = Telnyx(api_key=settings.telnyx_api_key)
        self._audio_queues: dict[str, asyncio.Queue[bytes | None]] = {}
        self._send_queues: dict[str, asyncio.Queue[bytes | None]] = {}

        # Reconnexion state
        self._connection_states: dict[str, str] = {}  # "connected" | "reconnecting" | "dead"
        self._reconnect_locks: dict[str, asyncio.Lock] = {}
        self._reconnect_events: dict[str, asyncio.Event] = {}  # set when new WS connects

    async def answer_call(self, call_control_id: str) -> None:
        logger.info("Answering call %s", call_control_id)
        await asyncio.to_thread(
            self._client.calls.actions.answer, call_control_id
        )

    async def start_audio_stream(self, call_control_id: str) -> None:
        """Tell Telnyx to start streaming audio via WebSocket (bidirectional)."""
        stream_url = f"{settings.stream_base_url}/ws/audio/{call_control_id}"
        logger.info(
            "Starting audio stream for call %s → %s", call_control_id, stream_url
        )
        await asyncio.to_thread(
            self._client.calls.actions.start_streaming,
            call_control_id,
            stream_url=stream_url,
            stream_track="inbound_track",
            stream_bidirectional_mode="rtp",
            stream_bidirectional_codec="PCMU",
        )

    async def stream_audio(self, call_control_id: str) -> AsyncIterator[bytes]:
        """Yield audio chunks from an internal queue populated by the WS handler."""
        queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._audio_queues[call_control_id] = queue

        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk
        finally:
            self._audio_queues.pop(call_control_id, None)

    async def send_audio(self, call_control_id: str, audio_data: bytes) -> None:
        """Push audio into the send queue for the WS handler to pick up.

        If the queue doesn't exist (WS not connected or already closed),
        log a warning and return — never create an orphan queue.
        If the queue is full, drop the oldest chunk (VoIP jitter buffer pattern).
        """
        queue = self._send_queues.get(call_control_id)
        if queue is None:
            logger.warning(
                "send_audio called but no send queue for call %s — dropping %d bytes",
                call_control_id,
                len(audio_data),
            )
            return

        if queue.full():
            try:
                queue.get_nowait()  # drop oldest
            except asyncio.QueueEmpty:
                pass
            logger.debug(
                "Send queue full for call %s — dropped oldest chunk", call_control_id
            )

        try:
            queue.put_nowait(audio_data)
        except asyncio.QueueFull:
            logger.warning(
                "Send queue still full after drop for call %s", call_control_id
            )

    def get_send_queue(self, call_control_id: str) -> asyncio.Queue[bytes | None]:
        """Return the outbound audio queue for the WS handler to consume.

        Creates a bounded queue (maxsize=SEND_QUEUE_MAXSIZE) if none exists.
        """
        if call_control_id not in self._send_queues:
            self._send_queues[call_control_id] = asyncio.Queue(
                maxsize=SEND_QUEUE_MAXSIZE
            )
        return self._send_queues[call_control_id]

    async def hangup(self, call_control_id: str) -> None:
        logger.info("Hanging up call %s", call_control_id)
        await asyncio.to_thread(
            self._client.calls.actions.hangup, call_control_id
        )

    def feed_audio(self, call_control_id: str, chunk: bytes) -> None:
        """Called by the WebSocket handler to feed audio into the stream."""
        queue = self._audio_queues.get(call_control_id)
        if queue:
            queue.put_nowait(chunk)

    # ── Connection state management ──────────────────────────────

    def on_ws_connected(self, call_control_id: str) -> None:
        """Called when a WebSocket handler connects for this call."""
        self._connection_states[call_control_id] = "connected"

        # Signal any pending reconnexion wait
        event = self._reconnect_events.get(call_control_id)
        if event:
            event.set()

        logger.info("WS connected for call %s", call_control_id)

    async def on_ws_disconnect(self, call_control_id: str) -> bool:
        """Called when a WebSocket handler disconnects.

        Attempts one silent reconnexion via start_streaming().
        Returns True if reconnexion succeeded, False if it failed/timed out.
        On failure, calls end_audio() to permanently clean up.
        """
        state = self._connection_states.get(call_control_id)
        if state == "dead":
            logger.debug(
                "WS disconnect for already-dead call %s — ignoring", call_control_id
            )
            return False

        # Get or create a lock for this call to prevent double reconnexion
        if call_control_id not in self._reconnect_locks:
            self._reconnect_locks[call_control_id] = asyncio.Lock()

        lock = self._reconnect_locks[call_control_id]

        if lock.locked():
            logger.debug(
                "Reconnexion already in progress for call %s — skipping",
                call_control_id,
            )
            return False

        async with lock:
            self._connection_states[call_control_id] = "reconnecting"
            logger.info(
                "WS disconnected for call %s — attempting reconnexion", call_control_id
            )

            # Prepare an event to wait for the new WS to connect
            reconnect_event = asyncio.Event()
            self._reconnect_events[call_control_id] = reconnect_event

            try:
                # Ask Telnyx to re-start streaming (will open a new WS)
                await self.start_audio_stream(call_control_id)

                # Wait for the new WS handler to call on_ws_connected()
                await asyncio.wait_for(
                    reconnect_event.wait(), timeout=RECONNECT_TIMEOUT
                )

                logger.info(
                    "Reconnexion successful for call %s", call_control_id
                )
                return True

            except asyncio.TimeoutError:
                logger.warning(
                    "Reconnexion timed out after %.1fs for call %s",
                    RECONNECT_TIMEOUT,
                    call_control_id,
                )
                self.end_audio(call_control_id)
                return False

            except Exception:
                logger.exception(
                    "Reconnexion failed for call %s", call_control_id
                )
                self.end_audio(call_control_id)
                return False

            finally:
                self._reconnect_events.pop(call_control_id, None)

    def end_audio(self, call_control_id: str) -> None:
        """Signal end of audio stream and permanently clean up all resources."""
        self._connection_states[call_control_id] = "dead"

        queue = self._audio_queues.get(call_control_id)
        if queue:
            queue.put_nowait(None)

        send_queue = self._send_queues.pop(call_control_id, None)
        if send_queue:
            send_queue.put_nowait(None)

        self._reconnect_locks.pop(call_control_id, None)
        self._reconnect_events.pop(call_control_id, None)

        logger.info("Audio ended (permanent cleanup) for call %s", call_control_id)

    def get_connection_state(self, call_control_id: str) -> str:
        """Return the connection state for a call. Used in tests."""
        return self._connection_states.get(call_control_id, "unknown")
