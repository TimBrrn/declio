import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from backend.src.api.dependencies import get_db_session, get_stt, get_telephony, get_tts
from backend.src.domain.entities.cabinet import Cabinet
from backend.src.infrastructure.adapters.deepgram_stt import DeepgramSTTAdapter
from backend.src.infrastructure.adapters.elevenlabs_tts import ElevenLabsTTSAdapter
from backend.src.infrastructure.adapters.telnyx_telephony import (
    TelnyxTelephonyAdapter,
)
from backend.src.infrastructure.audio.pipeline import AudioPipeline
from backend.src.domain.value_objects.token_usage import (
    DEEPGRAM_PRICE_PER_MINUTE,
    ELEVENLABS_PRICE_PER_1K_CHARS,
)
from backend.src.infrastructure.persistence.models import (
    ApiUsageModel,
    CabinetModel,
    CallRecordModel,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Active pipelines indexed by call_control_id
_active_pipelines: dict[str, AudioPipeline] = {}

# Track caller numbers from call.initiated for use in call.answered
_caller_numbers: dict[str, str] = {}


# ── Background helpers (fire-and-forget from webhook) ────────────


async def _safe_answer_call(
    telephony: TelnyxTelephonyAdapter, call_control_id: str
) -> None:
    """Answer call in background so webhook returns 200 immediately."""
    try:
        await telephony.answer_call(call_control_id)
    except Exception:
        logger.exception("Failed to answer call %s", call_control_id)


async def _start_call_pipeline(
    telephony: TelnyxTelephonyAdapter,
    pipeline: AudioPipeline,
    call_control_id: str,
) -> None:
    """Start Telnyx audio stream + run pipeline in background."""
    try:
        await telephony.start_audio_stream(call_control_id)
        await pipeline.start()
    except Exception:
        logger.exception("Pipeline start failed for call %s", call_control_id)


def _build_adapters():
    """Build conversation and calendar adapters for the pipeline.

    Imports from infrastructure/ at call time to avoid circular imports.
    Returns (conversation, calendar) tuple.
    """
    from backend.src.infrastructure.config.settings import settings as _settings

    conversation = None
    calendar = None

    try:
        from backend.src.infrastructure.adapters.openai_conversation import (
            OpenAIConversationAdapter,
        )

        conversation = OpenAIConversationAdapter(api_key=_settings.openai_api_key)
    except Exception:
        logger.exception("Failed to initialize OpenAI adapter")

    try:
        from backend.src.infrastructure.adapters.google_calendar import (
            GoogleCalendarAdapter,
        )

        calendar = GoogleCalendarAdapter(
            calendar_id=_settings.google_calendar_id,
            service_account_file=_settings.google_service_account_file,
        )
    except Exception:
        logger.exception("Failed to initialize Google Calendar adapter")

    return conversation, calendar


@router.post("/telnyx")
async def telnyx_webhook(
    request: Request,
    telephony: TelnyxTelephonyAdapter = Depends(get_telephony),
    stt: DeepgramSTTAdapter = Depends(get_stt),
    tts: ElevenLabsTTSAdapter = Depends(get_tts),
    session: Session = Depends(get_db_session),
):
    body = await request.json()
    data = body.get("data", {})
    event_type = data.get("event_type", "")
    payload = data.get("payload", {})
    call_control_id = payload.get("call_control_id", "")

    logger.info(
        "Telnyx event: %s | call_control_id: %s",
        event_type,
        call_control_id,
    )

    if event_type == "call.initiated":
        direction = payload.get("direction", "")
        caller = payload.get("from", "")
        logger.info(
            "Call initiated — direction: %s, caller: %s", direction, caller
        )
        if direction == "incoming":
            _caller_numbers[call_control_id] = caller
            # Fire-and-forget: answer in background so webhook returns 200 instantly
            asyncio.create_task(_safe_answer_call(telephony, call_control_id))

    elif event_type == "call.answered":
        # Idempotency guard: skip if we already have a pipeline for this call
        if call_control_id in _active_pipelines:
            logger.warning(
                "Duplicate call.answered for %s — skipping (pipeline already exists)",
                call_control_id,
            )
            return {"status": "ok"}

        try:
            logger.info("Call answered — setting up pipeline")

            # Load the PoC cabinet from DB (fast, needs session context)
            cabinet_model = session.exec(select(CabinetModel)).first()
            cabinet_entity = None
            cabinet_id = ""
            if cabinet_model:
                cabinet_entity = Cabinet(**cabinet_model.to_domain_dict())
                cabinet_id = cabinet_entity.id
                logger.info("Loaded cabinet '%s' for call", cabinet_entity.nom_cabinet)
            else:
                logger.warning("No cabinet configured — call will use defaults")

            caller_number = _caller_numbers.pop(call_control_id, "")

            # Build adapters for pipeline
            conversation, calendar = _build_adapters()
            initial_state = {
                "call_id": call_control_id,
                "messages": [],
                "current_transcript": "",
                "stt_confidence": 0.0,
                "response_text": "",
                "should_hangup": False,
                "pending_tool_calls": [],
                "tool_results": [],
                "cabinet": cabinet_entity,
                "caller_phone": caller_number or None,
                "token_turns": [],
            }

            pipeline = AudioPipeline(
                call_control_id=call_control_id,
                telephony=telephony,
                stt=stt,
                tts=tts,
                conversation=conversation,
                calendar=calendar,
                initial_state=initial_state,
                caller_number=caller_number,
                cabinet_id=cabinet_id,
            )
            # Store pipeline immediately so call.hangup can find it
            _active_pipelines[call_control_id] = pipeline

            # Fire-and-forget: start stream + greeting in background
            # so webhook returns 200 instantly (TTS greeting takes 2-5s)
            asyncio.create_task(
                _start_call_pipeline(telephony, pipeline, call_control_id)
            )

        except Exception:
            logger.exception(
                "Failed to set up pipeline for call %s", call_control_id
            )

    elif event_type == "call.hangup":
        logger.info("Call hung up — cleaning up pipeline")
        pipeline = _active_pipelines.pop(call_control_id, None)
        if pipeline:
            await pipeline.stop()

            # Persist call record with cost data
            metrics = pipeline.get_metrics()
            call_record = CallRecordModel(
                cabinet_id=metrics.get("cabinet_id", ""),
                caller_number=metrics.get("caller_number", ""),
                duration_seconds=metrics.get("duration_seconds", 0),
                scenario=metrics.get("scenario", ""),
                summary=metrics.get("summary", ""),
                actions_taken=metrics.get("actions_taken", "[]"),
                stt_confidence=metrics.get("stt_confidence", 0.0),
                transcript_json=metrics.get("transcript", "[]"),
                telnyx_call_id=call_control_id,
                ended_at=datetime.now(UTC),
                # Structured patient data
                patient_name=metrics.get("patient_name", ""),
                patient_message=metrics.get("patient_message", ""),
                error_detail=metrics.get("error") or "",
                # Cost aggregates
                total_cost_usd=metrics.get("total_cost_usd", 0.0),
                total_cost_eur=metrics.get("total_cost_eur", 0.0),
                llm_cost_usd=metrics.get("llm_cost_usd", 0.0),
                stt_cost_usd=metrics.get("stt_cost_usd", 0.0),
                tts_cost_usd=metrics.get("tts_cost_usd", 0.0),
                tts_chars_total=metrics.get("tts_chars_total", 0),
                total_prompt_tokens=metrics.get("total_prompt_tokens", 0),
                total_completion_tokens=metrics.get("total_completion_tokens", 0),
                total_tokens=metrics.get("total_tokens", 0),
            )
            session.add(call_record)
            session.flush()

            # Persist per-turn API usage rows
            token_turns = metrics.get("token_turns") or []
            for turn in token_turns:
                session.add(ApiUsageModel(
                    call_record_id=call_record.id,
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
            duration_s = metrics.get("duration_seconds", 0)
            stt_cost = metrics.get("stt_cost_usd", 0.0)
            session.add(ApiUsageModel(
                call_record_id=call_record.id,
                service="stt",
                turn_index=0,
                cost_usd=stt_cost,
                model="nova-2",
                duration_seconds=float(duration_s),
            ))

            # TTS summary row
            tts_chars = metrics.get("tts_chars_total", 0)
            tts_cost = metrics.get("tts_cost_usd", 0.0)
            session.add(ApiUsageModel(
                call_record_id=call_record.id,
                service="tts",
                turn_index=0,
                cost_usd=tts_cost,
                model="eleven_multilingual_v2",
                chars=tts_chars,
            ))

            session.commit()
            logger.info(
                "Call record persisted: scenario=%s, duration=%ds, "
                "cost_eur=%.4f, llm_turns=%d",
                call_record.scenario,
                call_record.duration_seconds,
                call_record.total_cost_eur,
                len(token_turns),
            )

        telephony.end_audio(call_control_id)
        _caller_numbers.pop(call_control_id, None)

    elif event_type == "call.streaming.started":
        logger.info("Audio streaming started for call %s", call_control_id)

    elif event_type == "call.streaming.stopped":
        logger.info("Audio streaming stopped for call %s", call_control_id)

    else:
        logger.debug("Unhandled Telnyx event: %s", event_type)

    return {"status": "ok"}
