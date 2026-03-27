"""End-to-end scenario tests — simulate full conversations through graph nodes.

Each scenario mocks ConversationPort + CalendarPort and drives nodes
in sequence, verifying state at each step.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.src.application.graph.nodes.greeting import greeting_node
from backend.src.application.graph.nodes.listening import listening_node
from backend.src.application.graph.nodes.responding import responding_node
from backend.src.application.graph.nodes.summary import summary_node
from backend.src.application.graph.nodes.thinking import thinking_node
from backend.src.application.graph.nodes.tool_exec import tool_exec_node
from backend.src.domain.entities.appointment import Appointment, AppointmentStatus
from backend.src.domain.entities.cabinet import Cabinet
from backend.src.domain.entities.call_record import CallRecord, ScenarioEnum
from backend.src.domain.ports.conversation_port import ToolCall
from backend.src.domain.value_objects.patient_contact import PatientContact
from backend.src.domain.value_objects.phone_number import PhoneNumber
from backend.src.domain.value_objects.time_slot import TimeSlot
from backend.tests.unit.application.conftest import _mock_llm_response


# ── Helpers ───────────────────────────────────────────────


def _cabinet() -> Cabinet:
    return Cabinet(
        id="cab-1",
        nom_cabinet="Kine Dupont",
        nom_praticien="Jean Dupont",
        adresse="12 rue de la Sante, 75013 Paris",
        telephone="0145678900",
        horaires={
            "lundi": ["09:00-12:00", "14:00-18:00"],
            "mardi": ["09:00-12:00"],
        },
        tarifs={"seance": 50.0, "bilan": 70.0},
        google_calendar_id="cal@group.calendar.google.com",
        numero_sms_kine="0612345678",
    )


def _slots() -> list[TimeSlot]:
    base = datetime.now().replace(hour=9, minute=0, second=0) + timedelta(days=1)
    return [
        TimeSlot(start=base, end=base + timedelta(minutes=30)),
        TimeSlot(start=base + timedelta(hours=2), end=base + timedelta(hours=2, minutes=30)),
        TimeSlot(start=base + timedelta(hours=5), end=base + timedelta(hours=5, minutes=30)),
    ]


def _call_record() -> CallRecord:
    return CallRecord(
        id="call-001",
        cabinet_id="cab-1",
        caller_phone="0678901234",
        scenario=ScenarioEnum.BOOKING,
        summary="RDV confirme",
    )


def _appointment(name: str = "Martin") -> Appointment:
    return Appointment(
        id="evt-001",
        cabinet_id="cab-1",
        patient_contact=PatientContact(
            phone=PhoneNumber("0678901234"), name=name
        ),
        time_slot=TimeSlot(
            start=datetime(2025, 1, 10, 14, 0),
            end=datetime(2025, 1, 10, 14, 30),
        ),
        status=AppointmentStatus.CONFIRMED,
    )


def _merge(state: dict, updates: dict) -> dict:
    """Apply node updates to state."""
    merged = dict(state)
    merged.update(updates)
    return merged


# ── a) BOOKING scenario ──────────────────────────────────


class TestBookingScenario:
    """Full booking: greeting → rdv request → get_available_slots →
    propose slots → patient picks → confirm_booking → goodbye → summary."""

    @pytest.mark.asyncio
    async def test_full_booking_flow(self):
        cabinet = _cabinet()
        slots = _slots()

        # Calendar mock
        calendar = AsyncMock()
        calendar.get_available_slots = AsyncMock(return_value=slots)
        calendar.book = AsyncMock(
            return_value=Appointment(
                id="appt-123",
                cabinet_id="cab-1",
                patient_contact=PatientContact(
                    phone=PhoneNumber("0678901234"), name="Dupont"
                ),
                time_slot=slots[1],
                status=AppointmentStatus.CONFIRMED,
            )
        )

        # Conversation mock: sequence of LLM responses for each thinking turn
        conversation = AsyncMock()
        conversation.chat_with_tools = AsyncMock(
            side_effect=[
                # Turn 1: patient says "je veux un rdv" → LLM calls get_available_slots
                _mock_llm_response(
                    "",
                    [ToolCall(id="call_1", name="get_available_slots", arguments={"date_hint": "cette semaine"})],
                ),
                # Turn 2: after tool result → LLM proposes slots
                _mock_llm_response(
                    "J'ai trois creneaux disponibles. Lequel vous conviendrait ?",
                    [],
                ),
                # Turn 3: patient picks slot 2 → LLM calls confirm_booking
                _mock_llm_response(
                    "",
                    [ToolCall(id="call_2", name="confirm_booking", arguments={"slot_index": 2, "patient_name": "Dupont"})],
                ),
                # Turn 4: after booking → LLM confirms + calls end_conversation
                _mock_llm_response(
                    "C'est note, monsieur Dupont. Bonne journee !",
                    [ToolCall(id="call_end", name="end_conversation", arguments={})],
                ),
            ]
        )

        notification = AsyncMock()
        notification.send_sms = AsyncMock(return_value=True)

        # ── Step 1: GREETING ──
        state = {"cabinet": cabinet, "messages": [], "caller_phone": "0678901234"}
        state = _merge(state, greeting_node(state))
        assert len(state["messages"]) == 1
        assert "Jean Dupont" in state["response_text"]

        # ── Step 2: LISTENING — patient says "je veux un rdv" ──
        state["current_transcript"] = "Bonjour, je voudrais prendre un rendez-vous"
        state["stt_confidence"] = 0.95
        state = _merge(state, listening_node(state))

        # ── Step 3: THINKING — LLM calls get_available_slots ──
        updates = await thinking_node(state, conversation=conversation)
        state = _merge(state, updates)
        assert len(state["pending_tool_calls"]) == 1
        assert state["pending_tool_calls"][0].name == "get_available_slots"

        # ── Step 4: TOOL_EXEC — run get_available_slots ──
        updates = await tool_exec_node(state, calendar=calendar)
        state = _merge(state, updates)
        assert state["pending_tool_calls"] == []
        assert state["scenario"] == ScenarioEnum.BOOKING

        # ── Step 5: THINKING — LLM proposes slots ──
        updates = await thinking_node(state, conversation=conversation)
        state = _merge(state, updates)
        assert "creneaux" in state["response_text"].lower()

        # ── Step 6: RESPONDING ──
        state = _merge(state, responding_node(state))

        # ── Step 7: LISTENING — patient picks slot 2 ──
        state["current_transcript"] = "Le deuxieme creneau, c'est Dupont"
        state["stt_confidence"] = 0.92
        state = _merge(state, listening_node(state))

        # ── Step 8: THINKING — LLM calls confirm_booking ──
        updates = await thinking_node(state, conversation=conversation)
        state = _merge(state, updates)
        assert len(state["pending_tool_calls"]) == 1
        assert state["pending_tool_calls"][0].name == "confirm_booking"
        assert state["patient_name"] == "Dupont"

        # ── Step 9: TOOL_EXEC — run confirm_booking ──
        updates = await tool_exec_node(state, calendar=calendar)
        state = _merge(state, updates)
        calendar.book.assert_called_once()

        # ── Step 10: THINKING — LLM confirms + end_conversation ──
        updates = await thinking_node(state, conversation=conversation)
        state = _merge(state, updates)
        assert state["should_hangup"] is True
        assert state["patient_name"] == "Dupont"

        # ── Step 11: SUMMARY — SMS sent with patient name ──
        state["call_record"] = _call_record()
        updates = await summary_node(state, notification=notification)
        notification.send_sms.assert_called_once()
        sms_text = notification.send_sms.call_args[1]["message"]
        assert "Dupont" in sms_text

    @pytest.mark.asyncio
    async def test_booking_passes_caller_phone_to_confirm(self):
        """Verify caller_phone is forwarded to confirm_booking."""
        cabinet = _cabinet()
        slots = _slots()
        calendar = AsyncMock()
        calendar.get_available_slots = AsyncMock(return_value=slots)
        calendar.book = AsyncMock(
            return_value=Appointment(
                id="appt-456",
                cabinet_id="cab-1",
                patient_contact=PatientContact(
                    phone=PhoneNumber("0678901234"), name="Test"
                ),
                time_slot=slots[0],
                status=AppointmentStatus.CONFIRMED,
            )
        )

        conversation = AsyncMock()
        conversation.chat_with_tools = AsyncMock(
            side_effect=[
                _mock_llm_response("", [ToolCall(id="c1", name="confirm_booking", arguments={"slot_index": 1, "patient_name": "Test"})]),
            ]
        )

        state = {
            "cabinet": cabinet,
            "messages": [HumanMessage(content="Le premier creneau")],
            "caller_phone": "0678901234",
        }

        updates = await thinking_node(state, conversation=conversation)
        state = _merge(state, updates)

        updates = await tool_exec_node(state, calendar=calendar)
        state = _merge(state, updates)

        # Verify the patient contact has the real phone
        call_kwargs = calendar.book.call_args
        patient = call_kwargs[1].get("patient") or call_kwargs.kwargs.get("patient")
        assert patient.phone.value == "0678901234"


# ── b) CANCELLATION scenario ─────────────────────────────


class TestCancellationScenario:
    """Full cancellation: greeting → cancel request → give name →
    cancel_appointment → goodbye → summary."""

    @pytest.mark.asyncio
    async def test_full_cancellation_flow(self):
        cabinet = _cabinet()
        appt = _appointment("Martin")

        calendar = AsyncMock()
        calendar.find_appointments = AsyncMock(return_value=[appt])
        calendar.cancel = AsyncMock(return_value=None)

        conversation = AsyncMock()
        conversation.chat_with_tools = AsyncMock(
            side_effect=[
                # Turn 1: patient wants to cancel → LLM asks name
                _mock_llm_response("A quel nom est le rendez-vous ?", []),
                # Turn 2: patient gives name → LLM calls cancel_appointment
                _mock_llm_response(
                    "",
                    [ToolCall(id="call_c", name="cancel_appointment", arguments={"patient_name": "Martin", "date_hint": "mardi"})],
                ),
                # Turn 3: after cancel → LLM confirms + proposes rebooking
                _mock_llm_response("Votre rendez-vous est annule. Souhaitez-vous en reprendre un autre ?", []),
                # Turn 4: patient says no → LLM says goodbye + end_conversation
                _mock_llm_response(
                    "Au revoir, bonne journee !",
                    [ToolCall(id="call_end", name="end_conversation", arguments={})],
                ),
            ]
        )

        notification = AsyncMock()
        notification.send_sms = AsyncMock(return_value=True)

        # ── GREETING ──
        state = {"cabinet": cabinet, "messages": []}
        state = _merge(state, greeting_node(state))

        # ── LISTENING: "j'annule mon rdv de mardi" ──
        state["current_transcript"] = "J'aimerais annuler mon rendez-vous de mardi"
        state["stt_confidence"] = 0.90
        state = _merge(state, listening_node(state))

        # ── THINKING: LLM asks name ──
        updates = await thinking_node(state, conversation=conversation)
        state = _merge(state, updates)
        assert "nom" in state["response_text"].lower()

        # ── RESPONDING ──
        state = _merge(state, responding_node(state))

        # ── LISTENING: "c'est Martin" ──
        state["current_transcript"] = "C'est Martin"
        state["stt_confidence"] = 0.95
        state = _merge(state, listening_node(state))

        # ── THINKING: LLM calls cancel_appointment ──
        updates = await thinking_node(state, conversation=conversation)
        state = _merge(state, updates)
        assert len(state["pending_tool_calls"]) == 1
        assert state["pending_tool_calls"][0].name == "cancel_appointment"
        assert state["patient_name"] == "Martin"

        # ── TOOL_EXEC: cancel ──
        updates = await tool_exec_node(state, calendar=calendar)
        state = _merge(state, updates)
        calendar.cancel.assert_called_once_with("evt-001")
        assert state["scenario"] == ScenarioEnum.CANCELLATION

        # ── THINKING: confirm cancellation ──
        updates = await thinking_node(state, conversation=conversation)
        state = _merge(state, updates)
        assert "annule" in state["response_text"].lower()

        # ── RESPONDING + LISTENING: "non merci au revoir" ──
        state = _merge(state, responding_node(state))
        state["current_transcript"] = "Non merci, au revoir"
        state["stt_confidence"] = 0.88
        state = _merge(state, listening_node(state))

        # ── THINKING: goodbye + end_conversation ──
        updates = await thinking_node(state, conversation=conversation)
        state = _merge(state, updates)
        assert state["should_hangup"] is True

        # ── SUMMARY ──
        state["call_record"] = CallRecord(
            id="call-002",
            cabinet_id="cab-1",
            caller_phone="0678901234",
            scenario=ScenarioEnum.CANCELLATION,
            summary="Annulation RDV Martin",
        )
        state["patient_name"] = "Martin"
        await summary_node(state, notification=notification)
        sms_text = notification.send_sms.call_args[1]["message"]
        assert "Martin" in sms_text


# ── c) FAQ scenario ───────────────────────────────────────


class TestFAQScenario:
    """FAQ: greeting → horaires question → answer → tarifs question →
    answer → goodbye."""

    @pytest.mark.asyncio
    async def test_faq_multi_question_flow(self):
        cabinet = _cabinet()

        conversation = AsyncMock()
        conversation.chat_with_tools = AsyncMock(
            side_effect=[
                # Turn 1: horaires question → LLM answers
                _mock_llm_response(
                    "Le cabinet est ouvert le lundi de neuf heures a midi et de quatorze heures a dix-huit heures, et le mardi matin. Avez-vous une autre question ?",
                    [],
                ),
                # Turn 2: tarifs question → LLM answers
                _mock_llm_response(
                    "La seance est a cinquante euros et le bilan a soixante-dix euros. Je vous en prie.",
                    [],
                ),
                # Turn 3: goodbye → end_conversation
                _mock_llm_response(
                    "Bonne journee !",
                    [ToolCall(id="call_end", name="end_conversation", arguments={})],
                ),
            ]
        )

        # ── GREETING ──
        state = {"cabinet": cabinet, "messages": []}
        state = _merge(state, greeting_node(state))

        # ── Q1: horaires ──
        state["current_transcript"] = "Quels sont vos horaires ?"
        state["stt_confidence"] = 0.93
        state = _merge(state, listening_node(state))
        updates = await thinking_node(state, conversation=conversation)
        state = _merge(state, updates)
        assert "lundi" in state["response_text"].lower()
        assert state["pending_tool_calls"] == []

        # ── RESPONDING ──
        state = _merge(state, responding_node(state))

        # ── Q2: tarifs ──
        state["current_transcript"] = "Et combien coute une seance ?"
        state["stt_confidence"] = 0.91
        state = _merge(state, listening_node(state))
        updates = await thinking_node(state, conversation=conversation)
        state = _merge(state, updates)
        assert "euros" in state["response_text"].lower()

        # ── RESPONDING ──
        state = _merge(state, responding_node(state))

        # ── Goodbye ──
        state["current_transcript"] = "Merci, au revoir"
        state["stt_confidence"] = 0.95
        state = _merge(state, listening_node(state))
        updates = await thinking_node(state, conversation=conversation)
        state = _merge(state, updates)
        assert state["should_hangup"] is True

    @pytest.mark.asyncio
    async def test_faq_no_tool_calls_needed(self):
        """FAQ should never trigger tool calls."""
        cabinet = _cabinet()

        conversation = AsyncMock()
        conversation.chat_with_tools = AsyncMock(
            return_value=_mock_llm_response("Le cabinet se trouve au 12 rue de la Sante.", [])
        )

        state = {
            "cabinet": cabinet,
            "messages": [HumanMessage(content="Ou se trouve le cabinet ?")],
        }

        updates = await thinking_node(state, conversation=conversation)
        assert updates["pending_tool_calls"] == []
        assert "Sante" in updates["response_text"]


# ── d) OUT-OF-SCOPE scenario ─────────────────────────────


class TestOutOfScopeScenario:
    """Patient asks medical question → polite refusal → leave_message → end."""

    @pytest.mark.asyncio
    async def test_medical_question_refused_then_message(self):
        cabinet = _cabinet()

        conversation = AsyncMock()
        conversation.chat_with_tools = AsyncMock(
            side_effect=[
                # Turn 1: medical question → polite refusal
                _mock_llm_response(
                    "Je ne suis pas en mesure de vous donner un avis medical. Souhaitez-vous laisser un message pour le kinesitherapeute ?",
                    [],
                ),
                # Turn 2: patient accepts → LLM calls leave_message
                _mock_llm_response(
                    "",
                    [ToolCall(id="call_m", name="leave_message", arguments={"message": "Patient a mal au dos, demande rappel", "patient_name": "Bernard"})],
                ),
                # Turn 3: message saved → LLM confirms + end
                _mock_llm_response(
                    "C'est note, le praticien vous rappellera. Bonne journee !",
                    [ToolCall(id="call_end", name="end_conversation", arguments={})],
                ),
            ]
        )

        calendar = AsyncMock()

        # ── GREETING ──
        state = {"cabinet": cabinet, "messages": []}
        state = _merge(state, greeting_node(state))

        # ── Medical question ──
        state["current_transcript"] = "J'ai mal au dos, que faire ?"
        state["stt_confidence"] = 0.90
        state = _merge(state, listening_node(state))
        updates = await thinking_node(state, conversation=conversation)
        state = _merge(state, updates)
        assert "medical" in state["response_text"].lower()
        assert state["pending_tool_calls"] == []

        # ── RESPONDING ──
        state = _merge(state, responding_node(state))

        # ── Patient says yes → leave_message ──
        state["current_transcript"] = "Oui, dites-lui que j'ai mal au dos"
        state["stt_confidence"] = 0.88
        state = _merge(state, listening_node(state))
        updates = await thinking_node(state, conversation=conversation)
        state = _merge(state, updates)
        assert len(state["pending_tool_calls"]) == 1
        assert state["pending_tool_calls"][0].name == "leave_message"

        # ── TOOL_EXEC: leave_message ──
        updates = await tool_exec_node(state, calendar=calendar)
        state = _merge(state, updates)
        tool_msgs = [m for m in state["messages"] if isinstance(m, ToolMessage)]
        assert any("enregistre" in m.content.lower() for m in tool_msgs)

        # ── THINKING: confirm + end ──
        updates = await thinking_node(state, conversation=conversation)
        state = _merge(state, updates)
        assert state["should_hangup"] is True
        assert "rappellera" in state["response_text"].lower()

    @pytest.mark.asyncio
    async def test_out_of_scope_detects_patient_name_from_leave_message(self):
        """Patient name should be extracted from leave_message arguments."""
        cabinet = _cabinet()

        conversation = AsyncMock()
        conversation.chat_with_tools = AsyncMock(
            return_value=_mock_llm_response(
                "",
                [ToolCall(id="c1", name="leave_message", arguments={"message": "test", "patient_name": "Bernard"})],
            )
        )

        state = {
            "cabinet": cabinet,
            "messages": [HumanMessage(content="test")],
        }

        updates = await thinking_node(state, conversation=conversation)
        assert updates["patient_name"] == "Bernard"


# ── e) ERROR scenario ────────────────────────────────────


class TestErrorScenario:
    """LLM raises exception → thinking_node should propagate error cleanly."""

    @pytest.mark.asyncio
    async def test_llm_exception_propagates(self):
        """If the LLM raises, thinking_node should raise (not swallow)."""
        cabinet = _cabinet()

        conversation = AsyncMock()
        conversation.chat_with_tools = AsyncMock(
            side_effect=Exception("LLM timeout")
        )

        state = {
            "cabinet": cabinet,
            "messages": [HumanMessage(content="Bonjour")],
        }

        with pytest.raises(Exception, match="LLM timeout"):
            await thinking_node(state, conversation=conversation)

    @pytest.mark.asyncio
    async def test_empty_messages_thinking_still_works(self):
        """thinking_node should handle empty message history gracefully."""
        cabinet = _cabinet()

        conversation = AsyncMock()
        conversation.chat_with_tools = AsyncMock(
            return_value=_mock_llm_response("Bonjour, comment puis-je vous aider ?", [])
        )

        state = {
            "cabinet": cabinet,
            "messages": [],
        }

        updates = await thinking_node(state, conversation=conversation)
        assert updates["response_text"] == "Bonjour, comment puis-je vous aider ?"

    @pytest.mark.asyncio
    async def test_tool_exec_with_unknown_tool(self):
        """Unknown tool should return error message, not crash."""
        cabinet = _cabinet()
        calendar = AsyncMock()

        state = {
            "cabinet": cabinet,
            "messages": [],
            "pending_tool_calls": [
                ToolCall(id="call_x", name="unknown_tool", arguments={}),
            ],
        }

        updates = await tool_exec_node(state, calendar=calendar)
        tool_msgs = [m for m in updates["messages"] if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert "erreur" in tool_msgs[0].content.lower()


# ── Summary node tests ────────────────────────────────────


class TestSummaryNode:
    @pytest.mark.asyncio
    async def test_summary_passes_patient_name_to_sms(self):
        cabinet = _cabinet()
        notification = AsyncMock()
        notification.send_sms = AsyncMock(return_value=True)

        state = {
            "cabinet": cabinet,
            "call_record": _call_record(),
            "patient_name": "Dupont",
        }

        await summary_node(state, notification=notification)

        notification.send_sms.assert_called_once()
        sms_text = notification.send_sms.call_args[1]["message"]
        assert "Dupont" in sms_text
        assert "Patient inconnu" not in sms_text

    @pytest.mark.asyncio
    async def test_summary_without_patient_name_uses_fallback(self):
        cabinet = _cabinet()
        notification = AsyncMock()
        notification.send_sms = AsyncMock(return_value=True)

        state = {
            "cabinet": cabinet,
            "call_record": _call_record(),
            # No patient_name in state
        }

        await summary_node(state, notification=notification)

        sms_text = notification.send_sms.call_args[1]["message"]
        assert "Patient inconnu" in sms_text

    @pytest.mark.asyncio
    async def test_summary_skips_when_no_call_record(self):
        cabinet = _cabinet()
        notification = AsyncMock()

        state = {"cabinet": cabinet}

        result = await summary_node(state, notification=notification)
        assert result == {}
        notification.send_sms.assert_not_called()
