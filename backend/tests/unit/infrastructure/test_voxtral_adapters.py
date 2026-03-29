"""Tests for VoxtralSTTAdapter and VoxtralTTSAdapter — unit tests with mocked SDK."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── VoxtralSTTAdapter ─────────────────────────────────────────────────────────


class TestVoxtralSTT:
    @pytest.mark.asyncio
    async def test_yields_transcriptions(self):
        """STT adapter yields (text, confidence) from Voxtral events."""
        from backend.src.infrastructure.adapters.voxtral_stt import VoxtralSTTAdapter

        with patch(
            "mistralai.client.Mistral"
        ) as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            # Mock realtime transcription events
            event1 = MagicMock()
            event1.text = "Bonjour"
            event2 = MagicMock()
            event2.text = "je voudrais un rendez-vous"
            event3 = MagicMock()
            event3.text = ""  # Empty event — should be skipped

            async def mock_transcribe(*args, **kwargs):
                for e in [event1, event2, event3]:
                    yield e

            mock_client.audio.realtime.transcribe_stream = mock_transcribe

            adapter = VoxtralSTTAdapter(api_key="test-key")

            # Create a dummy audio stream
            async def audio_gen():
                yield b"\x80\x80\x80"  # Dummy MULAW data

            results = []
            async for text, conf in adapter.transcribe_stream(audio_gen()):
                results.append((text, conf))

            assert len(results) == 2
            assert results[0] == ("Bonjour", 0.90)
            assert results[1] == ("je voudrais un rendez-vous", 0.90)

    @pytest.mark.asyncio
    async def test_error_propagates(self):
        """STT adapter re-raises errors from Voxtral."""
        from backend.src.infrastructure.adapters.voxtral_stt import VoxtralSTTAdapter

        with patch(
            "mistralai.client.Mistral"
        ) as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            async def mock_transcribe(*args, **kwargs):
                raise ConnectionError("WebSocket failed")
                yield  # pragma: no cover

            mock_client.audio.realtime.transcribe_stream = mock_transcribe

            adapter = VoxtralSTTAdapter(api_key="test-key")

            async def audio_gen():
                yield b"\x80"

            with pytest.raises(ConnectionError, match="WebSocket failed"):
                async for _ in adapter.transcribe_stream(audio_gen()):
                    pass

    def test_model_name_attribute(self):
        """Adapter exposes model_name for cost tracking."""
        from backend.src.infrastructure.adapters.voxtral_stt import VoxtralSTTAdapter
        adapter = VoxtralSTTAdapter.__new__(VoxtralSTTAdapter)
        assert adapter.model_name == "mistral-stt-latest"


# ── VoxtralTTSAdapter ─────────────────────────────────────────────────────────


class TestVoxtralTTS:
    @pytest.mark.asyncio
    async def test_empty_text_yields_nothing(self):
        """Empty text should yield no audio chunks."""
        from backend.src.infrastructure.adapters.voxtral_tts import VoxtralTTSAdapter

        adapter = VoxtralTTSAdapter(api_key="test-key")
        chunks = []
        async for chunk in adapter.synthesize_stream("   "):
            chunks.append(chunk)
        assert chunks == []

    def test_model_name_attribute(self):
        """Adapter exposes model_name for cost tracking."""
        from backend.src.infrastructure.adapters.voxtral_tts import VoxtralTTSAdapter
        adapter = VoxtralTTSAdapter.__new__(VoxtralTTSAdapter)
        assert adapter.model_name == "voxtral-mini-tts-2603"
