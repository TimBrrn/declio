"""Tests for _graceful_hangup() in AudioPipeline."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.src.infrastructure.audio.pipeline import AudioPipeline


def _make_pipeline(**overrides) -> AudioPipeline:
    """Create a pipeline with mocked dependencies."""
    telephony = MagicMock()
    telephony.send_audio = AsyncMock()
    telephony.hangup = AsyncMock()
    telephony.stream_audio = MagicMock()

    stt = MagicMock()
    tts = MagicMock()

    defaults = dict(
        call_control_id="call-test",
        telephony=telephony,
        stt=stt,
        tts=tts,
        conversation=MagicMock(),
        calendar=MagicMock(),
        initial_state={
            "call_id": "call-test",
            "messages": [],
            "current_transcript": "",
            "stt_confidence": 0.0,
            "response_text": "",
            "should_hangup": False,
            "pending_tool_calls": [],
            "tool_results": [],
        },
        caller_number="+33612345678",
        cabinet_id="cab-1",
    )
    defaults.update(overrides)
    return AudioPipeline(**defaults)


class TestGracefulHangup:
    @pytest.mark.asyncio
    async def test_happy_path_speak_then_hangup(self):
        """_graceful_hangup speaks the message then hangs up."""
        pipeline = _make_pipeline()
        pipeline._speak = AsyncMock()

        await pipeline._graceful_hangup("Au revoir !")

        pipeline._speak.assert_called_once_with("Au revoir !")
        pipeline._telephony.hangup.assert_called_once_with("call-test")

    @pytest.mark.asyncio
    async def test_speak_fails_still_hangs_up(self):
        """If TTS fails, hangup is still called."""
        pipeline = _make_pipeline()
        pipeline._speak = AsyncMock(side_effect=RuntimeError("TTS error"))

        await pipeline._graceful_hangup("Au revoir !")

        pipeline._speak.assert_called_once()
        pipeline._telephony.hangup.assert_called_once_with("call-test")

    @pytest.mark.asyncio
    async def test_hangup_fails_no_exception(self):
        """If hangup fails, no exception propagates."""
        pipeline = _make_pipeline()
        pipeline._speak = AsyncMock()
        pipeline._telephony.hangup = AsyncMock(
            side_effect=RuntimeError("Telnyx error")
        )

        # Should not raise
        await pipeline._graceful_hangup("Au revoir !")

        pipeline._speak.assert_called_once()
        pipeline._telephony.hangup.assert_called_once()

    @pytest.mark.asyncio
    async def test_both_fail_no_exception(self):
        """If both TTS and hangup fail, no exception propagates."""
        pipeline = _make_pipeline()
        pipeline._speak = AsyncMock(side_effect=RuntimeError("TTS error"))
        pipeline._telephony.hangup = AsyncMock(
            side_effect=RuntimeError("Telnyx error")
        )

        # Should not raise
        await pipeline._graceful_hangup("Au revoir !")
