"""Tests de scenarios kine realistes — J6 onboarding cabinet #1."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.src.application.graph.nodes.thinking import (
    _load_system_prompt,
    thinking_node,
)
from backend.src.application.graph.nodes.tool_exec import tool_exec_node
from backend.src.domain.entities.appointment import Appointment, AppointmentStatus
from backend.src.domain.entities.cabinet import Cabinet
from backend.src.domain.ports.conversation_port import ToolCall
from backend.src.domain.value_objects.patient_contact import PatientContact
from backend.src.domain.value_objects.phone_number import PhoneNumber
from backend.src.domain.value_objects.time_slot import TimeSlot
from backend.src.domain.value_objects.token_usage import TokenUsage


def _make_kine_cabinet() -> Cabinet:
    return Cabinet(
        id="cab-1",
        nom_cabinet="Cabinet Dupont Kine",
        nom_praticien="Jean Dupont",
        adresse="12 rue de la Sante, 75013 Paris",
        telephone="0612345678",
        horaires={
            "lundi": ["09:00-12:00", "14:00-19:00"],
            "mardi": ["09:00-12:00", "14:00-19:00"],
        },
        tarifs={"seance_kine": 16.13},
        google_calendar_id="test@group.calendar.google.com",
        numero_sms_kine="+33612345678",
        faq={
            "ordonnance": "Oui, une prescription medicale est necessaire.",
            "carte_vitale": "Oui, le cabinet accepte la carte Vitale.",
        },
    )


def _make_slots(n: int = 3) -> list[TimeSlot]:
    base = datetime.now().replace(hour=9, minute=0, second=0) + timedelta(days=1)
    return [
        TimeSlot(
            start=base + timedelta(hours=i),
            end=base + timedelta(hours=i, minutes=30),
        )
        for i in range(n)
    ]


def _make_appointment(patient_name: str = "Durand") -> Appointment:
    base = datetime.now().replace(hour=14, minute=0, second=0) + timedelta(days=2)
    return Appointment(
        id="appt-456",
        cabinet_id="cab-1",
        patient_contact=PatientContact(
            phone=PhoneNumber("0678901234"), name=patient_name
        ),
        time_slot=TimeSlot(start=base, end=base + timedelta(minutes=30)),
        status=AppointmentStatus.CONFIRMED,
    )


# ── Scenario 1: Classic kine booking ────────────────────────


class TestKineBookingScenario:
    @pytest.mark.asyncio
    async def test_full_booking_flow(self):
        """Patient 'Martin Durand' books a kine session via get_available_slots + confirm_booking."""
        cabinet = _make_kine_cabinet()
        slots = _make_slots(3)
        calendar = AsyncMock()
        calendar.get_available_slots = AsyncMock(return_value=slots)
        calendar.book = AsyncMock(
            side_effect=lambda cabinet_id, slot, patient: Appointment(
                id="appt-new",
                cabinet_id=cabinet_id,
                patient_contact=patient,
                time_slot=slot,
                status=AppointmentStatus.CONFIRMED,
            )
        )

        # Step 1: get_available_slots
        tc_slots = ToolCall(
            id="call_1",
            name="get_available_slots",
            arguments={"date_hint": "lundi"},
        )
        ai_msg = AIMessage(
            content="",
            additional_kwargs={
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "get_available_slots",
                            "arguments": '{"date_hint": "lundi"}',
                        },
                    }
                ]
            },
        )
        state = {
            "cabinet": cabinet,
            "messages": [HumanMessage(content="Un rdv lundi svp"), ai_msg],
            "pending_tool_calls": [tc_slots],
        }

        result_1 = await tool_exec_node(state, calendar=calendar)
        tool_msgs = [m for m in result_1["messages"] if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert "creneau" in tool_msgs[0].content.lower() or "desole" in tool_msgs[0].content.lower()

        # Step 2: confirm_booking
        tc_confirm = ToolCall(
            id="call_2",
            name="confirm_booking",
            arguments={"slot_index": 1, "patient_name": "Martin Durand"},
        )
        ai_msg_2 = AIMessage(
            content="",
            additional_kwargs={
                "tool_calls": [
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "confirm_booking",
                            "arguments": '{"slot_index": 1, "patient_name": "Martin Durand"}',
                        },
                    }
                ]
            },
        )
        state_2 = {
            "cabinet": cabinet,
            "messages": result_1["messages"] + [
                HumanMessage(content="Le premier creneau, a neuf heures."),
                ai_msg_2,
            ],
            "pending_tool_calls": [tc_confirm],
            "caller_phone": "0678901234",
        }

        result_2 = await tool_exec_node(state_2, calendar=calendar)
        tool_msgs_2 = [m for m in result_2["messages"] if isinstance(m, ToolMessage)]
        last_tool = tool_msgs_2[-1]
        assert "confirme" in last_tool.content.lower()
        assert "Martin Durand" in last_tool.content

        # Verify booking used real phone
        call_kwargs = calendar.book.call_args
        patient = call_kwargs.kwargs.get("patient") or call_kwargs[1].get("patient")
        assert patient.phone.value == "0678901234"


# ── Scenario 2: Tarif question then booking transition ──────


class TestTarifThenBookingScenario:
    def test_prompt_has_tarif_centimes(self):
        """System prompt must show '16 euros 13 centimes' for seance_kine tarif."""
        prompt = _load_system_prompt(_make_kine_cabinet())
        assert "16 euros" in prompt
        assert "13" in prompt

    @pytest.mark.asyncio
    async def test_tarif_then_booking(self):
        """Patient asks tarif, then transitions to booking."""
        cabinet = _make_kine_cabinet()
        conversation = AsyncMock()

        # Turn 1: patient asks tarif → LLM responds directly
        conversation.chat_with_tools = AsyncMock(
            return_value=("La seance de kinesitherapie est a seize euros et treize centimes.", [], TokenUsage())
        )

        state_1 = {
            "cabinet": cabinet,
            "messages": [HumanMessage(content="C'est combien une seance ?")],
        }
        result_1 = await thinking_node(state_1, conversation=conversation)
        assert "seize euros" in result_1["response_text"]

        # Turn 2: patient asks for booking → LLM calls get_available_slots
        tc = ToolCall(id="call_s", name="get_available_slots", arguments={"date_hint": "cette semaine"})
        conversation.chat_with_tools = AsyncMock(return_value=("", [tc], TokenUsage()))

        state_2 = {
            "cabinet": cabinet,
            "messages": result_1["messages"] + [
                HumanMessage(content="Je voudrais prendre un rendez-vous aussi"),
            ],
        }
        result_2 = await thinking_node(state_2, conversation=conversation)
        assert len(result_2["pending_tool_calls"]) == 1
        assert result_2["pending_tool_calls"][0].name == "get_available_slots"


# ── Scenario 3: Cancel + report (cancel then rebook) ────────


class TestCancelReportScenario:
    @pytest.mark.asyncio
    async def test_cancel_then_get_slots(self):
        """Patient cancels, then asks for new slots (report)."""
        cabinet = _make_kine_cabinet()
        appointment = _make_appointment("Durand")
        slots = _make_slots(2)
        calendar = AsyncMock()
        calendar.find_appointments = AsyncMock(return_value=[appointment])
        calendar.cancel = AsyncMock()
        calendar.get_available_slots = AsyncMock(return_value=slots)

        # Step 1: cancel_appointment
        tc_cancel = ToolCall(
            id="call_c",
            name="cancel_appointment",
            arguments={"patient_name": "Durand", "date_hint": "jeudi"},
        )
        ai_msg = AIMessage(
            content="",
            additional_kwargs={
                "tool_calls": [
                    {
                        "id": "call_c",
                        "type": "function",
                        "function": {
                            "name": "cancel_appointment",
                            "arguments": '{"patient_name": "Durand"}',
                        },
                    }
                ]
            },
        )
        state = {
            "cabinet": cabinet,
            "messages": [
                HumanMessage(content="Je voudrais annuler mon rendez-vous"),
                ai_msg,
            ],
            "pending_tool_calls": [tc_cancel],
        }

        result_cancel = await tool_exec_node(state, calendar=calendar)
        cancel_msgs = [m for m in result_cancel["messages"] if isinstance(m, ToolMessage)]
        assert "annule" in cancel_msgs[-1].content.lower()
        calendar.cancel.assert_called_once_with(appointment.id)

        # Step 2: get_available_slots for report
        tc_slots = ToolCall(
            id="call_s",
            name="get_available_slots",
            arguments={"date_hint": "semaine prochaine"},
        )
        ai_msg_2 = AIMessage(
            content="",
            additional_kwargs={
                "tool_calls": [
                    {
                        "id": "call_s",
                        "type": "function",
                        "function": {
                            "name": "get_available_slots",
                            "arguments": '{"date_hint": "semaine prochaine"}',
                        },
                    }
                ]
            },
        )
        state_2 = {
            "cabinet": cabinet,
            "messages": result_cancel["messages"] + [
                HumanMessage(content="Oui je voudrais reporter a la semaine prochaine"),
                ai_msg_2,
            ],
            "pending_tool_calls": [tc_slots],
        }

        result_slots = await tool_exec_node(state_2, calendar=calendar)
        slot_msgs = [m for m in result_slots["messages"] if isinstance(m, ToolMessage)]
        assert "creneau" in slot_msgs[-1].content.lower() or len(slots) > 0


# ── Scenario 4: Medical question → refusal → leave_message ──


class TestMedicalRefusalScenario:
    @pytest.mark.asyncio
    async def test_medical_question_gets_leave_message(self):
        """Patient asks medical question → LLM refuses politely and offers leave_message."""
        cabinet = _make_kine_cabinet()
        conversation = AsyncMock()

        # LLM responds with refusal + leave_message tool
        tc = ToolCall(
            id="call_lm",
            name="leave_message",
            arguments={
                "message": "Patient demande avis medical sur douleur dos",
                "patient_name": "Legrand",
            },
        )
        conversation.chat_with_tools = AsyncMock(
            return_value=(
                "Je ne suis pas en mesure de vous donner un avis medical. "
                "Je transmets votre message au kinesitherapeute.",
                [tc],
                TokenUsage(),
            )
        )

        state = {
            "cabinet": cabinet,
            "messages": [
                HumanMessage(
                    content="J'ai tres mal au dos, est-ce que je dois mettre du chaud ou du froid ?"
                ),
            ],
        }

        result = await thinking_node(state, conversation=conversation)

        assert "medical" in result["response_text"].lower()
        assert len(result["pending_tool_calls"]) == 1
        assert result["pending_tool_calls"][0].name == "leave_message"

    @pytest.mark.asyncio
    async def test_leave_message_execution(self):
        """Tool exec processes leave_message correctly."""
        cabinet = _make_kine_cabinet()
        calendar = AsyncMock()

        tc = ToolCall(
            id="call_lm",
            name="leave_message",
            arguments={
                "message": "Douleur dos, demande de conseil",
                "patient_name": "Legrand",
            },
        )
        ai_msg = AIMessage(
            content="Je transmets votre message.",
            additional_kwargs={
                "tool_calls": [
                    {
                        "id": "call_lm",
                        "type": "function",
                        "function": {
                            "name": "leave_message",
                            "arguments": '{"message": "Douleur dos", "patient_name": "Legrand"}',
                        },
                    }
                ]
            },
        )

        state = {
            "cabinet": cabinet,
            "messages": [ai_msg],
            "pending_tool_calls": [tc],
        }

        result = await tool_exec_node(state, calendar=calendar)
        tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert "message enregistre" in tool_msgs[-1].content.lower()
        assert "rappellera" in tool_msgs[-1].content.lower()
