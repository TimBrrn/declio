"""Barge-in detector — cuts TTS when patient speaks over the agent."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class BargeInDetector:
    """Tracks whether the agent is speaking (TTS streaming) and detects interruptions.

    Usage:
        detector = BargeInDetector()
        detector.start_speaking()   # called when TTS begins
        detector.stop_speaking()    # called when TTS finishes

        # In the STT callback, when a non-empty transcript arrives:
        if detector.is_speaking:
            detector.trigger_barge_in()  # cuts TTS, switches to listening
    """

    def __init__(self) -> None:
        self._is_speaking = False
        self._barge_in_event = asyncio.Event()
        self._cancel_tts_event = asyncio.Event()

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def barge_in_triggered(self) -> asyncio.Event:
        """Set when barge-in is detected. Pipeline should watch this."""
        return self._barge_in_event

    @property
    def cancel_tts(self) -> asyncio.Event:
        """Set to signal TTS streaming to stop immediately."""
        return self._cancel_tts_event

    def start_speaking(self) -> None:
        """Call when TTS audio begins streaming to Telnyx."""
        self._is_speaking = True
        self._barge_in_event.clear()
        self._cancel_tts_event.clear()

    def stop_speaking(self) -> None:
        """Call when TTS finishes or is interrupted."""
        self._is_speaking = False

    def trigger_barge_in(self) -> None:
        """Call when speech is detected during TTS playback."""
        if not self._is_speaking:
            return
        logger.info("Barge-in detected — cutting TTS")
        self._cancel_tts_event.set()
        self._barge_in_event.set()
        self._is_speaking = False

    def reset(self) -> None:
        """Reset state for a new conversational turn."""
        self._is_speaking = False
        self._barge_in_event.clear()
        self._cancel_tts_event.clear()
