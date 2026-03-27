"""Tests for TelnyxTelephonyAdapter send_audio and send queue management."""

import asyncio

import pytest
from unittest.mock import patch


@pytest.fixture
def adapter():
    """Create an adapter with mocked Telnyx client."""
    with patch("backend.src.infrastructure.adapters.telnyx_telephony.Telnyx"):
        from backend.src.infrastructure.adapters.telnyx_telephony import (
            TelnyxTelephonyAdapter,
        )
        return TelnyxTelephonyAdapter()


class TestSendAudio:
    @pytest.mark.asyncio
    async def test_send_audio_pushes_to_existing_queue(self, adapter):
        """send_audio() pushes chunk to an existing queue."""
        adapter.get_send_queue("call-1")  # create queue first
        await adapter.send_audio("call-1", b"audio-data")

        queue = adapter._send_queues["call-1"]
        chunk = queue.get_nowait()
        assert chunk == b"audio-data"

    @pytest.mark.asyncio
    async def test_send_audio_no_queue_drops_silently(self, adapter):
        """send_audio() with no queue returns without creating one."""
        await adapter.send_audio("call-ghost", b"audio-data")
        assert "call-ghost" not in adapter._send_queues

    @pytest.mark.asyncio
    async def test_send_audio_multiple_chunks(self, adapter):
        """Multiple send_audio calls queue chunks in order."""
        adapter.get_send_queue("call-2")
        await adapter.send_audio("call-2", b"chunk-1")
        await adapter.send_audio("call-2", b"chunk-2")
        await adapter.send_audio("call-2", b"chunk-3")

        queue = adapter._send_queues["call-2"]
        assert queue.get_nowait() == b"chunk-1"
        assert queue.get_nowait() == b"chunk-2"
        assert queue.get_nowait() == b"chunk-3"

    def test_get_send_queue_creates_if_missing(self, adapter):
        """get_send_queue auto-creates a bounded queue for unknown call_control_id."""
        queue = adapter.get_send_queue("new-call")
        assert isinstance(queue, asyncio.Queue)
        assert queue.empty()
        assert queue.maxsize == 50

    def test_get_send_queue_returns_same_instance(self, adapter):
        """get_send_queue returns the same queue for the same call."""
        q1 = adapter.get_send_queue("call-x")
        q2 = adapter.get_send_queue("call-x")
        assert q1 is q2

    def test_end_audio_cleans_send_queue(self, adapter):
        """end_audio() sends None sentinel and removes the send queue."""
        queue = adapter.get_send_queue("call-cleanup")
        adapter.end_audio("call-cleanup")

        # Sentinel was pushed
        assert queue.get_nowait() is None
        # Queue was removed from the dict
        assert "call-cleanup" not in adapter._send_queues

    def test_end_audio_without_queue_no_error(self, adapter):
        """end_audio() on unknown call doesn't raise."""
        adapter.end_audio("unknown-call")  # should not raise
