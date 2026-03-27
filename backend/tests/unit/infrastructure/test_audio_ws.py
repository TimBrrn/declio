"""Tests for the bidirectional WebSocket audio endpoint."""

import asyncio
import base64
import json
import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.src.infrastructure.persistence.database import init_db


@pytest.fixture(autouse=True)
def _setup_db():
    init_db()


@pytest.fixture
def client():
    from backend.src.api.main import app
    return TestClient(app)


@pytest.fixture
def mock_telephony():
    """Patch the singleton telephony adapter used by the WS endpoint."""
    mock = MagicMock()
    send_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    mock.get_send_queue.return_value = send_queue
    mock.feed_audio = MagicMock()
    mock.end_audio = MagicMock()
    mock.on_ws_connected = MagicMock()
    mock.on_ws_disconnect = AsyncMock(return_value=False)
    with patch("backend.src.api.websockets.audio_ws.get_telephony", return_value=mock):
        yield mock, send_queue


class TestAudioWebSocket:
    def test_connect_and_receive_media(self, client, mock_telephony):
        """WS accepts connection and decodes inbound Telnyx media."""
        mock, _ = mock_telephony
        audio = b"\x80" * 160  # 160 bytes of mulaw audio
        payload = base64.b64encode(audio).decode("ascii")
        message = json.dumps({
            "event": "media",
            "media": {"payload": payload, "chunk": "1"},
        })

        with client.websocket_connect("/ws/audio/call-123") as ws:
            ws.send_text(message)
            ws.send_text(message)

        assert mock.feed_audio.call_count == 2
        mock.feed_audio.assert_called_with("call-123", audio)

    def test_disconnect_calls_on_ws_disconnect(self, client, mock_telephony):
        """Disconnecting delegates to on_ws_disconnect for reconnexion logic."""
        mock, _ = mock_telephony

        with client.websocket_connect("/ws/audio/call-456"):
            pass

        mock.on_ws_disconnect.assert_called_once_with("call-456")

    def test_connect_calls_on_ws_connected(self, client, mock_telephony):
        """Connecting notifies the adapter via on_ws_connected."""
        mock, _ = mock_telephony

        with client.websocket_connect("/ws/audio/call-789"):
            pass

        mock.on_ws_connected.assert_called_once_with("call-789")

    def test_non_media_event_ignored(self, client, mock_telephony):
        """Non-media events don't call feed_audio."""
        mock, _ = mock_telephony
        message = json.dumps({"event": "connected"})

        with client.websocket_connect("/ws/audio/call-789") as ws:
            ws.send_text(message)

        mock.feed_audio.assert_not_called()

    def test_outbound_audio(self, client, mock_telephony):
        """Audio placed in send queue is sent as base64 JSON to the WS client."""
        mock, send_queue = mock_telephony
        audio_out = b"\x7f" * 80

        with client.websocket_connect("/ws/audio/call-out") as ws:
            send_queue.put_nowait(audio_out)
            send_queue.put_nowait(None)
            time.sleep(0.1)
            ws.send_text(json.dumps({"event": "connected"}))
            raw = ws.receive_text()

        data = json.loads(raw)
        assert data["event"] == "media"
        decoded = base64.b64decode(data["media"]["payload"])
        assert decoded == audio_out
