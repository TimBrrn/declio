"""Tests for pipeline fallback and timeout behavior."""

import asyncio
import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.src.infrastructure.audio.pipeline import (
    AudioPipeline,
    MAX_CALL_DURATION,
    SILENCE_TIMEOUT,
)


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


class TestPipelineMetrics:
    def test_get_metrics_empty(self):
        """Metrics returned even when no transcription happened."""
        pipeline = _make_pipeline()
        metrics = pipeline.get_metrics()
        assert metrics["caller_number"] == "+33612345678"
        assert metrics["cabinet_id"] == "cab-1"
        assert metrics["stt_confidence"] == 0.0
        assert metrics["scenario"] == ""
        assert metrics["error"] is None

    def test_get_metrics_with_data(self):
        """Metrics accumulate STT confidence and detect scenario."""
        pipeline = _make_pipeline()
        pipeline._stt_confidences = [0.9, 0.8, 0.85]
        pipeline._scenario = "booking"
        pipeline._actions = ["get_available_slots", "book_appointment"]
        pipeline._last_response = "RDV confirmé jeudi 14h"

        metrics = pipeline.get_metrics()
        assert metrics["stt_confidence"] == pytest.approx(0.85, rel=0.01)
        assert metrics["scenario"] == "booking"
        assert "get_available_slots" in metrics["actions_taken"]
        assert metrics["summary"] == "RDV confirmé jeudi 14h"

    def test_get_metrics_returns_patient_name(self):
        """Metrics include patient_name from graph state."""
        pipeline = _make_pipeline()
        pipeline._state["patient_name"] = "Martin Durand"

        metrics = pipeline.get_metrics()
        assert metrics["patient_name"] == "Martin Durand"

    def test_get_metrics_returns_patient_message(self):
        """Metrics include patient_message from graph state."""
        pipeline = _make_pipeline()
        pipeline._state["patient_message"] = "Rappeler le patient SVP"

        metrics = pipeline.get_metrics()
        assert metrics["patient_message"] == "Rappeler le patient SVP"

    def test_get_metrics_defaults_empty_when_no_patient_data(self):
        """Metrics default to empty string when no patient data."""
        pipeline = _make_pipeline()

        metrics = pipeline.get_metrics()
        assert metrics["patient_name"] == ""
        assert metrics["patient_message"] == ""


class TestPipelineFallback:
    @pytest.mark.asyncio
    async def test_thinking_error_sets_fallback_text(self):
        """thinking_node exception → fallback text in state."""
        pipeline = _make_pipeline()

        with patch(
            "backend.src.infrastructure.audio.pipeline.thinking_node",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM timeout"),
        ):
            await pipeline._run_thinking()

        assert "souci technique" in pipeline._state["response_text"]
        assert pipeline._error == "thinking_node_error"
        assert pipeline._state["pending_tool_calls"] == []

    def test_metrics_after_error(self):
        """After an error, metrics contain error info."""
        pipeline = _make_pipeline()
        pipeline._error = "thinking_node_error"
        pipeline._scenario = "error"

        metrics = pipeline.get_metrics()
        assert metrics["error"] == "thinking_node_error"


class TestPipelineConstants:
    def test_max_call_duration(self):
        """MAX_CALL_DURATION is 300 seconds (5 minutes)."""
        assert MAX_CALL_DURATION == 300

    def test_silence_timeout(self):
        """SILENCE_TIMEOUT is 15 seconds."""
        assert SILENCE_TIMEOUT == 15
