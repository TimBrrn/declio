#!/usr/bin/env python3
"""CLI interactive — teste le cerveau Declio (LLM + tools) avec micro + TTS.

Mode vocal : tu parles dans ton micro (Deepgram STT), l'assistant repond (ElevenLabs TTS).
Mode texte : si Deepgram/ElevenLabs ne marchent pas, on fallback sur clavier/texte.

Usage:
    source .venv/bin/activate
    python -m backend.scripts.cli_chat          # auto-detect micro
    python -m backend.scripts.cli_chat --text   # force mode texte
"""

import argparse
import asyncio
import json
import os
import struct
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.src.infrastructure.config.settings import settings
from backend.src.infrastructure.adapters.openai_conversation import (
    OpenAIConversationAdapter,
)
from backend.src.infrastructure.adapters.google_calendar import GoogleCalendarAdapter
from backend.src.application.graph.nodes.greeting import greeting_node
from backend.src.application.graph.nodes.thinking import thinking_node
from backend.src.application.graph.nodes.tool_exec import tool_exec_node
from backend.src.domain.entities.cabinet import Cabinet
from backend.src.infrastructure.persistence.database import engine, init_db
from backend.src.infrastructure.persistence.models import ApiUsageModel, CabinetModel, CallRecordModel
from backend.src.domain.services.call_processor import CallProcessor
from backend.src.domain.value_objects.token_usage import (
    DEEPGRAM_PRICE_PER_MINUTE,
    USD_TO_EUR,
)
from backend.src.infrastructure.config.pricing import get_tts_price_per_1k_chars

from langchain_core.messages import HumanMessage

from sqlmodel import Session, select


def load_cabinet() -> Cabinet:
    init_db()
    with Session(engine) as session:
        model = session.exec(select(CabinetModel)).first()
        if not model:
            print("Aucun cabinet en base. Lance: python -m backend.scripts.seed_cabinet")
            sys.exit(1)
        return Cabinet(**model.to_domain_dict())


# ── TTS (ElevenLabs) ──────────────────────────────────────


def init_tts():
    """Retourne (tts_client, voice_id) ou (None, "") si indisponible."""
    if not settings.elevenlabs_api_key:
        print("[TTS] Pas de cle ElevenLabs — mode texte")
        return None, ""

    try:
        from elevenlabs import ElevenLabs
        voice_id = settings.elevenlabs_voice_id or "pFZP5JQG7iQjIQuC4Bku"
        client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        # Test rapide
        test_iter = client.text_to_speech.stream(
            voice_id=voice_id, text="test", output_format="mp3_44100_128",
            model_id="eleven_multilingual_v2", language_code="fr",
        )
        for _ in test_iter:
            break
        print("[TTS] ElevenLabs OK")
        return client, voice_id
    except Exception as e:
        print(f"[TTS] Desactive ({e})")
        return None, ""


def play_tts(text: str, tts_client, voice_id: str) -> int:
    """Play TTS and return number of characters sent."""
    if not text.strip() or tts_client is None:
        return 0
    try:
        audio_iter = tts_client.text_to_speech.stream(
            voice_id=voice_id, text=text, output_format="mp3_44100_128",
            model_id="eleven_multilingual_v2", language_code="fr",
        )
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            for chunk in audio_iter:
                f.write(chunk)
            tmp_path = f.name
        os.system(f'afplay "{tmp_path}" 2>/dev/null')
        os.unlink(tmp_path)
        return len(text)
    except Exception as e:
        print(f"  [TTS erreur: {e}]")
        return 0


# ── STT (Deepgram via micro) ──────────────────────────────

SAMPLE_RATE = 16000  # 16kHz linear16 pour Deepgram


def init_stt() -> bool:
    """Verifie que Deepgram + sounddevice fonctionnent."""
    if not settings.deepgram_api_key:
        print("[STT] Pas de cle Deepgram — mode clavier")
        return False
    try:
        import sounddevice  # noqa: F401
        print("[STT] Deepgram + micro OK")
        return True
    except Exception as e:
        print(f"[STT] Micro indisponible ({e}) — mode clavier")
        return False


def record_from_mic() -> tuple[str, float]:
    """Enregistre depuis le micro, envoie a Deepgram, retourne (transcript, duration_seconds).

    Appuie sur Entree pour commencer, Entree pour arreter.
    Deepgram fait la transcription en streaming avec endpointing.
    """
    import sounddevice as sd
    from deepgram import DeepgramClient

    input("  [Appuie sur Entree pour parler...]")
    print("  [Parle maintenant... Entree pour arreter]")

    # Collect audio chunks
    audio_chunks: list[bytes] = []
    stop_event = threading.Event()

    def audio_callback(indata, frames, time_info, status):
        if not stop_event.is_set():
            audio_chunks.append(bytes(indata))

    stream = sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=4000,  # 250ms chunks
        callback=audio_callback,
    )
    stream.start()

    # Wait for Enter to stop
    input()
    stop_event.set()
    stream.stop()
    stream.close()

    if not audio_chunks:
        return "", 0.0

    audio_data = b"".join(audio_chunks)
    audio_duration = len(audio_data) / SAMPLE_RATE / 2  # 16-bit = 2 bytes/sample
    print(f"  [Enregistre {audio_duration:.1f}s d'audio, transcription...]")

    # Send to Deepgram (batch transcription)
    client = DeepgramClient(api_key=settings.deepgram_api_key)

    # Build a WAV header so Deepgram knows the format
    import io, wave
    wav_buf = io.BytesIO()
    with wave.open(wav_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_data)
    wav_bytes = wav_buf.getvalue()

    response = client.listen.v1.media.transcribe_file(
        request=wav_bytes,
        model="nova-2",
        language="fr",
        punctuate=True,
    )

    transcript = ""
    try:
        transcript = response.results.channels[0].alternatives[0].transcript
    except (IndexError, AttributeError):
        pass

    return transcript.strip(), audio_duration


# ── Main loop ─────────────────────────────────────────────


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", action="store_true", help="Force mode texte (pas de micro)")
    args = parser.parse_args()

    cabinet = load_cabinet()
    print(f"\nCabinet: {cabinet.nom_cabinet}")
    print(f"Praticien: {cabinet.nom_praticien}")
    print(f"Adresse: {cabinet.adresse}\n")

    conversation = OpenAIConversationAdapter(api_key=settings.openai_api_key)
    calendar = GoogleCalendarAdapter(
        calendar_id=settings.google_calendar_id,
        service_account_file=settings.google_service_account_file,
    )

    tts_client, voice_id = init_tts()
    use_mic = False if args.text else init_stt()

    if use_mic:
        mode = "vocal" if tts_client else "micro→texte"
    else:
        mode = "texte" + (" + audio" if tts_client else "")
    print(f"\n[Mode: {mode}]\n")

    # State
    state = {
        "cabinet": cabinet,
        "messages": [],
        "current_transcript": "",
        "stt_confidence": 1.0,
        "response_text": "",
        "should_hangup": False,
        "pending_tool_calls": [],
        "tool_results": [],
        "caller_phone": "+33600000000",
        "token_turns": [],
    }

    # Track conversation for call record
    start_time = time.monotonic()
    all_transcripts: list[str] = []
    actions_taken: list[str] = []
    tts_chars_total: int = 0
    stt_seconds_total: float = 0.0

    # GREETING
    greet = greeting_node(state)
    state["messages"] = greet["messages"]
    greeting_text = greet["response_text"]
    print(f"Assistant: {greeting_text}")
    tts_chars_total += play_tts(greeting_text, tts_client, voice_id)

    print("\n--- Ctrl+C pour quitter ---\n")

    while True:
        try:
            if use_mic:
                user_input, stt_dur = record_from_mic()
                stt_seconds_total += stt_dur
                if user_input:
                    print(f"Toi: {user_input}")
            else:
                user_input = input("Toi: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAu revoir!")
            break

        if not user_input:
            continue

        all_transcripts.append(user_input)
        state["messages"] = list(state["messages"]) + [HumanMessage(content=user_input)]

        # THINKING
        think = await thinking_node(state, conversation=conversation)
        state["messages"] = think["messages"]
        state["response_text"] = think.get("response_text", "")
        state["pending_tool_calls"] = think.get("pending_tool_calls", [])
        state["should_hangup"] = think.get("should_hangup", False)
        state["token_turns"] = think.get("token_turns", state.get("token_turns", []))
        if think.get("patient_name"):
            state["patient_name"] = think["patient_name"]

        # TOOL_EXEC loop
        while state["pending_tool_calls"]:
            for tc in state["pending_tool_calls"]:
                actions_taken.append(tc.name)
            tool_result = await tool_exec_node(state, calendar=calendar)
            state["messages"] = tool_result["messages"]
            state["pending_tool_calls"] = []

            think = await thinking_node(state, conversation=conversation)
            state["messages"] = think["messages"]
            state["response_text"] = think.get("response_text", "")
            state["pending_tool_calls"] = think.get("pending_tool_calls", [])
            state["should_hangup"] = think.get("should_hangup", False)
            state["token_turns"] = think.get("token_turns", state.get("token_turns", []))
            if think.get("patient_name"):
                state["patient_name"] = think["patient_name"]

        response = state.get("response_text", "")
        if response:
            print(f"Assistant: {response}")
            tts_chars_total += play_tts(response, tts_client, voice_id)

        # Display token usage for this turn
        turns = state.get("token_turns", [])
        if turns:
            last = turns[-1]
            print(f"  [tokens: {last.get('total_tokens', 0)} | cost: ${last.get('cost_usd', 0):.6f} | model: {last.get('model', '?')}]")

        if state.get("should_hangup"):
            print("\n[Appel termine]")
            break

    # ── Cost summary ────────────────────────────────────────
    token_turns = state.get("token_turns", [])
    llm_cost_usd = sum(t.get("cost_usd", 0) for t in token_turns)
    total_tokens = sum(t.get("total_tokens", 0) for t in token_turns)
    total_prompt = sum(t.get("prompt_tokens", 0) for t in token_turns)
    total_completion = sum(t.get("completion_tokens", 0) for t in token_turns)
    stt_cost_usd = (stt_seconds_total / 60) * DEEPGRAM_PRICE_PER_MINUTE
    tts_cost_usd = (tts_chars_total / 1000) * get_tts_price_per_1k_chars()
    total_cost_usd = llm_cost_usd + stt_cost_usd + tts_cost_usd
    total_cost_eur = total_cost_usd * USD_TO_EUR

    print(f"\n{'='*50}")
    print(f"  LLM : {len(token_turns)} turns, {total_tokens} tokens, ${llm_cost_usd:.6f}")
    print(f"  STT : {stt_seconds_total:.1f}s, ${stt_cost_usd:.6f}")
    print(f"  TTS : {tts_chars_total} chars, ${tts_cost_usd:.6f}")
    print(f"  TOTAL: ${total_cost_usd:.6f} ({total_cost_eur:.4f} EUR)")
    print(f"{'='*50}")

    # ── Persist call record ────────────────────────────────
    duration = int(time.monotonic() - start_time)
    full_transcript = " ".join(all_transcripts)
    processor = CallProcessor()
    scenario = processor.detect_scenario(full_transcript)

    # Build summary from conversation
    summary_parts = []
    for msg in state.get("messages", []):
        if msg.type == "human":
            summary_parts.append(f"Patient: {msg.content}")
        elif msg.type == "ai" and msg.content:
            summary_parts.append(f"Assistant: {msg.content}")
    summary = "\n".join(summary_parts[-10:])  # last 10 exchanges

    with Session(engine) as session:
        record = CallRecordModel(
            cabinet_id=cabinet.id,
            caller_number="CLI-test",
            duration_seconds=duration,
            scenario=scenario.value,
            summary=summary,
            actions_taken=json.dumps(actions_taken),
            stt_confidence=1.0 if not use_mic else 0.9,
            telnyx_call_id=f"cli-{int(time.time())}",
            ended_at=datetime.now(UTC),
            # Cost aggregates
            total_cost_usd=total_cost_usd,
            total_cost_eur=total_cost_eur,
            llm_cost_usd=llm_cost_usd,
            stt_cost_usd=stt_cost_usd,
            tts_cost_usd=tts_cost_usd,
            tts_chars_total=tts_chars_total,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_tokens=total_tokens,
        )
        session.add(record)
        session.flush()

        # Per-turn LLM usage rows
        for turn in token_turns:
            session.add(ApiUsageModel(
                call_record_id=record.id,
                service="llm",
                turn_index=turn.get("turn_index", 0),
                prompt_tokens=turn.get("prompt_tokens", 0),
                completion_tokens=turn.get("completion_tokens", 0),
                total_tokens=turn.get("total_tokens", 0),
                cost_usd=turn.get("cost_usd", 0.0),
                model=turn.get("model", ""),
                tool_name=turn.get("tool_name"),
            ))

        # STT summary row
        session.add(ApiUsageModel(
            call_record_id=record.id,
            service="stt",
            turn_index=0,
            cost_usd=stt_cost_usd,
            model="nova-2",
            duration_seconds=stt_seconds_total,
        ))

        # TTS summary row
        session.add(ApiUsageModel(
            call_record_id=record.id,
            service="tts",
            turn_index=0,
            cost_usd=tts_cost_usd,
            model="eleven_multilingual_v2",
            chars=tts_chars_total,
        ))

        session.commit()
        print(f"\n[Call record enregistre: scenario={scenario.value}, duree={duration}s, cout={total_cost_eur:.4f} EUR]")


if __name__ == "__main__":
    asyncio.run(main())
