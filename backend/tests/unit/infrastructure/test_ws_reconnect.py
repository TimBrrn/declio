"""Tests for WebSocket reconnexion logic in TelnyxTelephonyAdapter."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.src.infrastructure.adapters.telnyx_telephony import (
    RECONNECT_TIMEOUT,
    TelnyxTelephonyAdapter,
)


@pytest.fixture
def adapter():
    """Create an adapter with mocked Telnyx client."""
    a = TelnyxTelephonyAdapter.__new__(TelnyxTelephonyAdapter)
    a._client = MagicMock()
    a._audio_queues = {}
    a._send_queues = {}
    a._connection_states = {}
    a._reconnect_locks = {}
    a._reconnect_events = {}
    return a


class TestConnectionState:
    def test_on_ws_connected_sets_state(self, adapter):
        """on_ws_connected sets state to 'connected'."""
        adapter.on_ws_connected("call-1")
        assert adapter.get_connection_state("call-1") == "connected"

    def test_end_audio_sets_state_dead(self, adapter):
        """end_audio sets state to 'dead'."""
        adapter.on_ws_connected("call-1")
        adapter.end_audio("call-1")
        assert adapter.get_connection_state("call-1") == "dead"

    def test_unknown_call_state(self, adapter):
        """Unknown call returns 'unknown'."""
        assert adapter.get_connection_state("nonexistent") == "unknown"


class TestReconnexionSuccess:
    @pytest.mark.asyncio
    async def test_reconnect_success(self, adapter):
        """on_ws_disconnect retries start_streaming, returns True when new WS connects."""
        adapter.on_ws_connected("call-1")

        # Mock start_audio_stream to simulate Telnyx accepting the request
        adapter.start_audio_stream = AsyncMock()

        async def _simulate_new_ws():
            """Simulate a new WS connecting after a short delay."""
            await asyncio.sleep(0.05)
            adapter.on_ws_connected("call-1")

        # Run reconnexion and simulated new WS concurrently
        reconnect_task = asyncio.create_task(
            adapter.on_ws_disconnect("call-1")
        )
        ws_task = asyncio.create_task(_simulate_new_ws())

        result = await reconnect_task
        await ws_task

        assert result is True
        assert adapter.get_connection_state("call-1") == "connected"
        adapter.start_audio_stream.assert_called_once_with("call-1")

    @pytest.mark.asyncio
    async def test_reconnect_reuses_queues(self, adapter):
        """After reconnexion, the same send queue is still accessible."""
        queue = adapter.get_send_queue("call-1")
        adapter.on_ws_connected("call-1")
        adapter.start_audio_stream = AsyncMock()

        async def _simulate_new_ws():
            await asyncio.sleep(0.05)
            adapter.on_ws_connected("call-1")

        tasks = [
            asyncio.create_task(adapter.on_ws_disconnect("call-1")),
            asyncio.create_task(_simulate_new_ws()),
        ]
        await asyncio.gather(*tasks)

        # Same queue object should still be there
        assert adapter._send_queues["call-1"] is queue


class TestReconnexionFailure:
    @pytest.mark.asyncio
    async def test_reconnect_timeout_ends_audio(self, adapter):
        """on_ws_disconnect returns False and calls end_audio when timeout expires."""
        adapter.on_ws_connected("call-1")
        adapter._audio_queues["call-1"] = asyncio.Queue()
        adapter.get_send_queue("call-1")

        # Mock start_audio_stream — no new WS will connect
        adapter.start_audio_stream = AsyncMock()

        # Use a very short timeout for the test
        with patch(
            "backend.src.infrastructure.adapters.telnyx_telephony.RECONNECT_TIMEOUT",
            0.1,
        ):
            result = await adapter.on_ws_disconnect("call-1")

        assert result is False
        assert adapter.get_connection_state("call-1") == "dead"

    @pytest.mark.asyncio
    async def test_reconnect_start_streaming_exception(self, adapter):
        """on_ws_disconnect returns False when start_streaming raises."""
        adapter.on_ws_connected("call-1")
        adapter.start_audio_stream = AsyncMock(side_effect=RuntimeError("API down"))

        result = await adapter.on_ws_disconnect("call-1")

        assert result is False
        assert adapter.get_connection_state("call-1") == "dead"

    @pytest.mark.asyncio
    async def test_dead_call_disconnect_ignored(self, adapter):
        """on_ws_disconnect on a dead call returns False immediately."""
        adapter._connection_states["call-1"] = "dead"
        result = await adapter.on_ws_disconnect("call-1")
        assert result is False


class TestReconnexionLock:
    @pytest.mark.asyncio
    async def test_concurrent_disconnect_uses_lock(self, adapter):
        """Two concurrent on_ws_disconnect calls — only one attempts reconnexion."""
        adapter.on_ws_connected("call-1")
        adapter.start_audio_stream = AsyncMock()

        call_count = 0

        original_start = adapter.start_audio_stream

        async def _counting_start(cid):
            nonlocal call_count
            call_count += 1
            await original_start(cid)

        adapter.start_audio_stream = _counting_start

        with patch(
            "backend.src.infrastructure.adapters.telnyx_telephony.RECONNECT_TIMEOUT",
            0.1,
        ):
            results = await asyncio.gather(
                adapter.on_ws_disconnect("call-1"),
                adapter.on_ws_disconnect("call-1"),
            )

        # One should have attempted, the other skipped
        assert results.count(False) >= 1
        assert call_count <= 1


class TestReconnectTimeout:
    def test_reconnect_timeout_is_5s(self):
        """RECONNECT_TIMEOUT constant is 5 seconds."""
        assert RECONNECT_TIMEOUT == 5.0
