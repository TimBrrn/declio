from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.messages import ToolMessage

from backend.src.application.graph.state import CallState
from backend.src.application.use_cases.answer_faq import answer_faq
from backend.src.application.use_cases.book_appointment import book_appointment
from backend.src.application.use_cases.cancel_appointment import cancel_appointment
from backend.src.application.use_cases.confirm_booking import confirm_booking
from backend.src.application.use_cases.get_available_slots import get_available_slots
from backend.src.domain.entities.call_record import ScenarioEnum
from backend.src.domain.ports.calendar_port import CalendarPort
from backend.src.domain.ports.conversation_port import ToolCall

logger = logging.getLogger(__name__)

# Mapping tool name → scenario
_TOOL_SCENARIO: dict[str, ScenarioEnum] = {
    "book_appointment": ScenarioEnum.BOOKING,
    "get_available_slots": ScenarioEnum.BOOKING,
    "confirm_booking": ScenarioEnum.BOOKING,
    "cancel_appointment": ScenarioEnum.CANCELLATION,
}


async def tool_exec_node(
    state: CallState,
    calendar: CalendarPort,
) -> dict:
    """Execute les tool calls du LLM et retourne les resultats."""
    pending = state.get("pending_tool_calls", [])
    cabinet = state["cabinet"]
    tool_results: list[dict[str, Any]] = []

    # Tracking pour call_record
    scenario = state.get("scenario")
    patient_message = state.get("patient_message")
    actions_taken = list(state.get("call_record", {}).get("actions_taken", [])
                         if isinstance(state.get("call_record"), dict) else
                         getattr(state.get("call_record"), "actions_taken", []))

    logger.info("Tool exec node: %d tool(s) to execute", len(pending))

    for tool_call in pending:
        logger.info(
            "Executing tool=%s args=%s", tool_call.name, tool_call.arguments
        )
        t0 = time.perf_counter()
        result = await _execute_tool(tool_call, cabinet, calendar, state)
        latency_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "Tool result tool=%s latency_ms=%.0f result_len=%d",
            tool_call.name,
            latency_ms,
            len(result),
        )
        logger.debug("Tool result tool=%s: %.200s", tool_call.name, result)

        tool_results.append(
            {
                "tool_call_id": tool_call.id,
                "name": tool_call.name,
                "result": result,
            }
        )

        # Mettre a jour le scenario si pas encore detecte
        if scenario is None and tool_call.name in _TOOL_SCENARIO:
            scenario = _TOOL_SCENARIO[tool_call.name]
            logger.info("Scenario detected: %s (from tool=%s)", scenario, tool_call.name)

        actions_taken.append(f"{tool_call.name}: {result[:100]}")

        # Store leave_message content for structured persistence
        if tool_call.name == "leave_message":
            patient_message = tool_call.arguments.get("message", "")
            logger.info("Patient message captured: %.200s", patient_message)

    messages = list(state.get("messages", []))
    for tr in tool_results:
        messages.append(
            ToolMessage(
                content=tr["result"],
                tool_call_id=tr["tool_call_id"],
            )
        )

    # Mettre a jour le call_record
    updates: dict[str, Any] = {
        "messages": messages,
        "tool_results": tool_results,
        "pending_tool_calls": [],
    }
    if scenario is not None:
        updates["scenario"] = scenario
    if patient_message is not None:
        updates["patient_message"] = patient_message

    return updates


async def _execute_tool(
    tool_call: ToolCall,
    cabinet: Any,
    calendar: CalendarPort,
    state: CallState,
) -> str:
    """Dispatch un tool call vers le bon use case."""
    name = tool_call.name
    args = tool_call.arguments

    if name == "book_appointment":
        return await book_appointment(
            calendar=calendar,
            cabinet=cabinet,
            date_hint=args.get("date_hint", ""),
        )

    if name == "confirm_booking":
        return await confirm_booking(
            calendar=calendar,
            cabinet=cabinet,
            slot_index=int(args.get("slot_index", 0)),
            patient_name=args.get("patient_name", ""),
            patient_phone=state.get("caller_phone"),
        )

    if name == "cancel_appointment":
        return await cancel_appointment(
            calendar=calendar,
            cabinet_id=cabinet.id,
            patient_name=args.get("patient_name", ""),
            date_hint=args.get("date_hint"),
        )

    if name == "get_available_slots":
        return await get_available_slots(
            calendar=calendar,
            cabinet=cabinet,
            date_hint=args.get("date_hint", ""),
        )

    if name == "leave_message":
        return (
            f"Message enregistre : {args.get('message', '')}. "
            "Le cabinet vous rappellera dans les plus brefs delais."
        )

    logger.warning("Unknown tool called: %s", name)
    return f"Erreur : outil '{name}' inconnu. Les outils disponibles sont : book_appointment, confirm_booking, cancel_appointment, get_available_slots, leave_message."
