"""Tests for send queue backpressure and send_audio guard."""

import asyncio

import pytest

from backend.src.infrastructure.adapters.telnyx_telephony import (
    SEND_QUEUE_MAXSIZE,
    TelnyxTelephonyAdapter,
)


@pytest.fixture
def adapter():
    """Create an adapter with mocked Telnyx client."""
    a = TelnyxTelephonyAdapter.__new__(TelnyxTelephonyAdapter)
    a._audio_queues = {}
    a._send_queues = {}
    a._connection_states = {}
    a._reconnect_locks = {}
    a._reconnect_events = {}
    return a


class TestBackpressure:
    def test_send_queue_has_maxsize(self, adapter):
        """get_send_queue creates a bounded queue."""
        queue = adapter.get_send_queue("call-1")
        assert queue.maxsize == SEND_QUEUE_MAXSIZE

    def test_maxsize_is_50(self):
        """SEND_QUEUE_MAXSIZE is 50 (~1s of ulaw audio)."""
        assert SEND_QUEUE_MAXSIZE == 50

    @pytest.mark.asyncio
    async def test_drop_oldest_when_full(self, adapter):
        """When send queue is full, oldest chunk is dropped to make room."""
        queue = adapter.get_send_queue("call-1")

        # Fill the queue
        for i in range(SEND_QUEUE_MAXSIZE):
            await queue.put(bytes([i]))

        assert queue.full()

        # send_audio should drop oldest and add new
        await adapter.send_audio("call-1", b"\xff")

        # Queue should still be full
        assert queue.full()

        # First item should be bytes([1]) (bytes([0]) was dropped)
        first = queue.get_nowait()
        assert first == bytes([1])

    @pytest.mark.asyncio
    async def test_normal_send_when_not_full(self, adapter):
        """send_audio works normally when queue has room."""
        adapter.get_send_queue("call-1")

        await adapter.send_audio("call-1", b"\xaa")
        await adapter.send_audio("call-1", b"\xbb")

        queue = adapter._send_queues["call-1"]
        assert queue.qsize() == 2
        assert queue.get_nowait() == b"\xaa"
        assert queue.get_nowait() == b"\xbb"


class TestSendAudioGuard:
    @pytest.mark.asyncio
    async def test_no_queue_returns_silently(self, adapter):
        """send_audio with no queue logs warning and returns (no orphan queue)."""
        # Don't create a queue — send_audio should not create one
        await adapter.send_audio("call-ghost", b"\x00" * 100)
        assert "call-ghost" not in adapter._send_queues

    @pytest.mark.asyncio
    async def test_existing_queue_works(self, adapter):
        """send_audio pushes to existing queue normally."""
        adapter.get_send_queue("call-ok")
        await adapter.send_audio("call-ok", b"\xab")

        queue = adapter._send_queues["call-ok"]
        assert queue.qsize() == 1
