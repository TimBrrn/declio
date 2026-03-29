"""AudioPipeline — orchestrates STT → LLM nodes → TTS streaming for a single call.

Calls greeting/thinking/tool_exec nodes directly (same pattern as cli_chat.py),
avoiding full graph invocation which loops due to cyclic edges.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import UTC, datetime
from typing import Any

from langchain_core.messages import HumanMessage

from backend.src.application.graph.nodes.greeting import greeting_node
from backend.src.application.graph.nodes.thinking import thinking_node
from backend.src.application.graph.nodes.tool_exec import tool_exec_node
from backend.src.domain.ports.calendar_port import CalendarPort
from backend.src.domain.ports.conversation_port import ConversationPort
from backend.src.domain.value_objects.token_usage import USD_TO_EUR
from backend.src.infrastructure.config.pricing import (
    get_stt_price_per_minute,
    get_tts_price_per_1k_chars,
)
from backend.src.infrastructure.audio.barge_in import BargeInDetector

logger = logging.getLogger(__name__)

# Regex to split response text into sentences for streaming TTS
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

MAX_CALL_DURATION = 300  # 5 minutes
SILENCE_TIMEOUT = 15  # seconds
UTTERANCE_PAUSE = 1.5  # seconds — wait for user to finish speaking before processing


class AudioPipeline:
    """Manages the full audio lifecycle for one phone call.

    Flow:
        Telnyx audio → Deepgram STT (streaming)
            → final transcript → thinking_node (LLM) → tool_exec if needed
            → response_text → ElevenLabs TTS (streaming, sentence by sentence)
            → audio chunks → Telnyx WebSocket
    """

    def __init__(
        self,
        call_control_id: str,
        telephony: Any,
        stt: Any,
        tts: Any,
        conversation: ConversationPort,
        calendar: CalendarPort,
        initial_state: dict,
        caller_number: str = "",
        cabinet_id: str = "",
    ) -> None:
        self.call_control_id = call_control_id
        self._telephony = telephony
        self._stt = stt
        self._tts = tts
        self._conversation = conversation
        self._calendar = calendar
        self._state = dict(initial_state)
        self._barge_in = BargeInDetector()
        self._running = False
        self._tasks: list[asyncio.Task] = []

        # Metrics
        self._start_time: float = time.monotonic()
        self._caller_number = caller_number
        self._cabinet_id = cabinet_id
        self._stt_confidences: list[float] = []
        self._scenario: str = ""
        self._actions: list[str] = []
        self._last_response: str = ""
        self._error: str | None = None
        self._silence_count: int = 0

        # TTS character counter for cost tracking
        self._tts_chars: int = 0

        # Transcript: list of {role, content, timestamp}
        self._transcript: list[dict[str, str]] = []

    async def start(self) -> None:
        """Start the pipeline — runs greeting then enters listen loop."""
        self._running = True
        self._start_time = time.monotonic()
        logger.info("Pipeline started for call %s", self.call_control_id)

        # Run the greeting node directly (sync node)
        try:
            greet = greeting_node(self._state)
            self._state.update(greet)
        except Exception:
            logger.exception("Greeting node error")
            self._state["response_text"] = (
                "Bonjour, cabinet de kinésithérapie, comment puis-je vous aider ?"
            )

        # Speak the greeting
        greeting_text = self._state.get("response_text", "")
        if greeting_text:
            self._transcript.append({
                "role": "assistant",
                "content": greeting_text,
                "timestamp": datetime.now(UTC).isoformat(),
            })
            await self._speak(greeting_text)

        # Start the listen → respond loop
        self._tasks.append(asyncio.create_task(self._listen_loop()))

    async def stop(self) -> None:
        """Stop the pipeline and clean up resources."""
        logger.info("Pipeline stopping for call %s", self.call_control_id)
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

    def get_metrics(self) -> dict:
        """Return collected metrics for call record persistence."""
        elapsed = time.monotonic() - self._start_time
        avg_confidence = (
            sum(self._stt_confidences) / len(self._stt_confidences)
            if self._stt_confidences
            else 0.0
        )
        # Extract scenario and actions from graph state
        scenario = self._state.get("scenario", "") or self._scenario
        actions = self._state.get("actions_taken", []) or self._actions
        if isinstance(actions, list):
            actions_json = json.dumps(actions)
        else:
            actions_json = str(actions)

        # Cost computation
        token_turns = self._state.get("token_turns") or []
        llm_cost_usd = sum(t.get("cost_usd", 0.0) for t in token_turns)
        stt_cost_usd = (elapsed / 60) * get_stt_price_per_minute()
        tts_cost_usd = (self._tts_chars / 1000) * get_tts_price_per_1k_chars()
        total_cost_usd = llm_cost_usd + stt_cost_usd + tts_cost_usd

        total_prompt_tokens = sum(t.get("prompt_tokens", 0) for t in token_turns)
        total_completion_tokens = sum(t.get("completion_tokens", 0) for t in token_turns)

        return {
            "caller_number": self._caller_number,
            "cabinet_id": self._cabinet_id,
            "duration_seconds": int(elapsed),
            "scenario": scenario,
            "actions_taken": actions_json,
            "stt_confidence": round(avg_confidence, 3),
            "summary": self._last_response,
            "error": self._error,
            "patient_name": self._state.get("patient_name") or "",
            "patient_message": self._state.get("patient_message") or "",
            "transcript": json.dumps(self._transcript, ensure_ascii=False),
            # Cost tracking
            "token_turns": token_turns,
            "tts_chars_total": self._tts_chars,
            "llm_cost_usd": llm_cost_usd,
            "stt_cost_usd": stt_cost_usd,
            "tts_cost_usd": tts_cost_usd,
            "total_cost_usd": total_cost_usd,
            "total_cost_eur": total_cost_usd * USD_TO_EUR,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
        }

    async def _listen_loop(self) -> None:
        """Main loop: stream audio → STT → LLM nodes → TTS → send audio.

        Uses a debounce (UTTERANCE_PAUSE) to accumulate transcript fragments
        before sending to the LLM — lets the user finish their thought.
        TTS runs as a non-blocking task so new STT transcripts can trigger
        barge-in (interrupt the agent mid-speech).
        """
        speak_task: asyncio.Task | None = None
        # Accumulator: collects transcript fragments until user pauses
        pending_fragments: list[str] = []
        pending_confidences: list[float] = []

        try:
            audio_stream = self._telephony.stream_audio(self.call_control_id)
            stt_stream = self._stt.transcribe_stream(audio_stream)
            stt_iter = stt_stream.__aiter__()

            silence_deadline = time.monotonic() + SILENCE_TIMEOUT
            call_deadline = self._start_time + MAX_CALL_DURATION

            while self._running:
                now = time.monotonic()

                # Check max call duration
                if now >= call_deadline:
                    if speak_task and not speak_task.done():
                        self._barge_in.trigger_barge_in()
                        speak_task.cancel()
                    await self._graceful_hangup(
                        "Je vous remercie pour votre appel, bonne journée !"
                    )
                    break

                # ── Wait for next transcript (with debounce timeout) ──
                # If we have pending fragments, use short timeout to check
                # if user keeps speaking. Otherwise, wait indefinitely.
                timeout = UTTERANCE_PAUSE if pending_fragments else None

                try:
                    transcript, confidence = await asyncio.wait_for(
                        stt_iter.__anext__(), timeout=timeout
                    )
                except asyncio.TimeoutError:
                    # Debounce expired — user stopped speaking, process now
                    combined = " ".join(pending_fragments)
                    avg_conf = (
                        sum(pending_confidences) / len(pending_confidences)
                        if pending_confidences
                        else 0.0
                    )
                    pending_fragments.clear()
                    pending_confidences.clear()

                    await self._process_utterance(
                        combined, avg_conf, speak_task
                    )
                    speak_task = self._pending_speak_task

                    if self._state.get("should_hangup", False):
                        logger.info("LLM → hangup")
                        if speak_task:
                            await speak_task
                        await self._telephony.hangup(self.call_control_id)
                        break
                    continue
                except StopAsyncIteration:
                    # STT stream ended (call hangup / Deepgram closed)
                    break

                now = time.monotonic()

                # ── Barge-in: new transcript while agent is speaking ──
                if speak_task and not speak_task.done():
                    if transcript.strip():
                        self._barge_in.trigger_barge_in()
                        try:
                            await speak_task
                        except asyncio.CancelledError:
                            pass
                        speak_task = None
                        logger.info("BARGE-IN: cut by '%s'", transcript[:60])
                    else:
                        continue

                # Collect finished speak task
                if speak_task and speak_task.done():
                    speak_task = None

                if not transcript.strip():
                    if now >= silence_deadline:
                        self._silence_count += 1
                        if self._silence_count >= 2:
                            logger.info("Double silence — hanging up")
                            await self._graceful_hangup(
                                "Au revoir, bonne journée !"
                            )
                            break
                        logger.info("Silence — prompting")
                        await self._speak("Êtes-vous toujours là ?")
                        silence_deadline = now + SILENCE_TIMEOUT
                    continue

                # ── Accumulate fragment (debounce) ──
                self._silence_count = 0
                silence_deadline = time.monotonic() + SILENCE_TIMEOUT
                pending_fragments.append(transcript)
                pending_confidences.append(confidence)

            # Process any remaining fragments
            if pending_fragments:
                combined = " ".join(pending_fragments)
                avg_conf = (
                    sum(pending_confidences) / len(pending_confidences)
                    if pending_confidences
                    else 0.0
                )
                await self._process_utterance(combined, avg_conf, speak_task)
                speak_task = self._pending_speak_task

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception("Listen loop error for call %s", self.call_control_id)
            self._error = str(e)
            self._scenario = "error"
            if speak_task and not speak_task.done():
                speak_task.cancel()
            await self._graceful_hangup(
                "Je rencontre un petit souci technique. "
                "Puis-je prendre votre nom et numéro "
                "pour que le cabinet vous rappelle ?"
            )
        finally:
            if speak_task and not speak_task.done():
                speak_task.cancel()

    # Temporary storage for speak task created in _process_utterance
    _pending_speak_task: asyncio.Task | None = None

    async def _process_utterance(
        self,
        transcript: str,
        confidence: float,
        current_speak_task: asyncio.Task | None,
    ) -> None:
        """Process a complete user utterance: STT → LLM → tools → TTS."""
        self._pending_speak_task = None

        if not transcript.strip():
            return

        self._stt_confidences.append(confidence)
        self._transcript.append({
            "role": "visitor",
            "content": transcript,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        t_start = time.monotonic()
        logger.info("STT → '%s' (%.0f%%)", transcript, confidence * 100)

        # Add HumanMessage to conversation history
        self._state["messages"] = list(self._state.get("messages", [])) + [
            HumanMessage(content=transcript)
        ]

        # THINKING — call LLM
        await self._run_thinking()

        # TOOL_EXEC loop
        while self._state.get("pending_tool_calls"):
            for tc in self._state["pending_tool_calls"]:
                name = tc.name if hasattr(tc, "name") else str(tc)
                if name not in self._actions:
                    self._actions.append(name)

            try:
                tool_result = await tool_exec_node(
                    self._state, calendar=self._calendar
                )
                self._state["messages"] = tool_result["messages"]
                self._state["pending_tool_calls"] = []
            except Exception:
                logger.exception("Tool execution error")
                self._state["pending_tool_calls"] = []
                break

            await self._run_thinking()

        t_graph = time.monotonic()

        scenario = self._state.get("scenario", "")
        if scenario:
            self._scenario = scenario

        # Speak response — NON-BLOCKING (allows barge-in)
        response_text = self._state.get("response_text", "")
        if response_text:
            self._last_response = response_text
            self._transcript.append({
                "role": "assistant",
                "content": response_text,
                "timestamp": datetime.now(UTC).isoformat(),
            })
            logger.info(
                "LLM %.0fms → speaking %d chars",
                (t_graph - t_start) * 1000,
                len(response_text),
            )
            self._pending_speak_task = asyncio.create_task(
                self._speak(response_text)
            )

    async def _run_thinking(self) -> None:
        """Call thinking_node and update state. Handles errors gracefully."""
        try:
            think = await thinking_node(
                self._state, conversation=self._conversation
            )
            self._state["messages"] = think["messages"]
            self._state["response_text"] = think.get("response_text", "")
            self._state["pending_tool_calls"] = think.get("pending_tool_calls", [])
            self._state["should_hangup"] = think.get("should_hangup", False)
            self._state["token_turns"] = think.get(
                "token_turns", self._state.get("token_turns", [])
            )
            if think.get("patient_name"):
                self._state["patient_name"] = think["patient_name"]
        except Exception:
            logger.exception("Thinking node error")
            self._state["response_text"] = (
                "Je rencontre un petit souci technique. "
                "Puis-je prendre votre nom et numero pour que le cabinet vous rappelle ?"
            )
            self._state["pending_tool_calls"] = []
            self._error = "thinking_node_error"

    async def _graceful_hangup(self, message: str) -> None:
        """Speak a farewell message then hang up, with full error protection."""
        try:
            await self._speak(message)
        except Exception:
            logger.exception("TTS failed during graceful hangup")
        try:
            await self._telephony.hangup(self.call_control_id)
        except Exception:
            logger.exception("Hangup failed during graceful hangup")

    async def _speak(self, text: str) -> None:
        """Stream text to TTS sentence by sentence, send audio to Telnyx.

        Supports barge-in: stops sending audio if patient interrupts.
        """
        self._tts_chars += len(text)
        sentences = SENTENCE_SPLIT.split(text)
        self._barge_in.start_speaking()

        t_start = time.monotonic()
        first_chunk = True

        try:
            for sentence in sentences:
                if not sentence.strip():
                    continue
                if self._barge_in.cancel_tts.is_set():
                    break

                async for audio_chunk in self._tts.synthesize_stream(sentence):
                    if self._barge_in.cancel_tts.is_set():
                        break

                    if first_chunk:
                        logger.info(
                            "TTS first chunk: %.0fms",
                            (time.monotonic() - t_start) * 1000,
                        )
                        first_chunk = False

                    await self._telephony.send_audio(
                        self.call_control_id, audio_chunk
                    )
        finally:
            self._barge_in.stop_speaking()
            self._barge_in.reset()
