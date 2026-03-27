"""Tests tool_exec node avec ports mockes."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from backend.src.application.graph.nodes.tool_exec import tool_exec_node
from backend.src.domain.entities.cabinet import Cabinet
from backend.src.domain.entities.call_record import ScenarioEnum
from backend.src.domain.ports.conversation_port import ToolCall


def _make_cabinet() -> Cabinet:
    return Cabinet(
        id="cab-1",
        nom_cabinet="Kine Dupont",
        nom_praticien="Jean Dupont",
        adresse="12 rue de la Sante, 75013 Paris",
        telephone="0145678900",
        horaires={"lundi": ["09:00-12:00", "14:00-18:00"]},
        tarifs={"seance": 50.0},
        google_calendar_id="cal@group.calendar.google.com",
        numero_sms_kine="0612345678",
    )


def _make_mock_calendar():
    calendar = AsyncMock()
    calendar.get_available_slots = AsyncMock(return_value=[])
    calendar.cancel = AsyncMock(return_value=None)
    return calendar


class TestToolExecNode:
    @pytest.mark.asyncio
    async def test_get_available_slots_produces_tool_message(self):
        calendar = _make_mock_calendar()
        state = {
            "cabinet": _make_cabinet(),
            "messages": [AIMessage(content="")],
            "pending_tool_calls": [
                ToolCall(
                    id="call_1",
                    name="get_available_slots",
                    arguments={"date_hint": "lundi"},
                )
            ],
        }

        result = await tool_exec_node(state, calendar=calendar)

        # Verifie qu'un ToolMessage est ajoute
        tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].tool_call_id == "call_1"

    @pytest.mark.asyncio
    async def test_cancel_appointment_tool(self):
        calendar = _make_mock_calendar()
        state = {
            "cabinet": _make_cabinet(),
            "messages": [],
            "pending_tool_calls": [
                ToolCall(
                    id="call_2",
                    name="cancel_appointment",
                    arguments={"patient_name": "Martin", "date_hint": "jeudi"},
                )
            ],
        }

        result = await tool_exec_node(state, calendar=calendar)

        tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert "Martin" in tool_msgs[0].content

    @pytest.mark.asyncio
    async def test_leave_message_tool(self):
        calendar = _make_mock_calendar()
        state = {
            "cabinet": _make_cabinet(),
            "messages": [],
            "pending_tool_calls": [
                ToolCall(
                    id="call_3",
                    name="leave_message",
                    arguments={"message": "Rappeler le patient"},
                )
            ],
        }

        result = await tool_exec_node(state, calendar=calendar)

        tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert "Rappeler le patient" in tool_msgs[0].content

    @pytest.mark.asyncio
    async def test_clears_pending_tool_calls(self):
        calendar = _make_mock_calendar()
        state = {
            "cabinet": _make_cabinet(),
            "messages": [],
            "pending_tool_calls": [
                ToolCall(id="call_4", name="leave_message", arguments={"message": "test"}),
            ],
        }

        result = await tool_exec_node(state, calendar=calendar)
        assert result["pending_tool_calls"] == []

    @pytest.mark.asyncio
    async def test_scenario_detected_from_tool(self):
        calendar = _make_mock_calendar()
        state = {
            "cabinet": _make_cabinet(),
            "messages": [],
            "pending_tool_calls": [
                ToolCall(
                    id="call_5",
                    name="cancel_appointment",
                    arguments={"patient_name": "X"},
                )
            ],
        }

        result = await tool_exec_node(state, calendar=calendar)
        assert result.get("scenario") == ScenarioEnum.CANCELLATION

    @pytest.mark.asyncio
    async def test_leave_message_stores_patient_message(self):
        """leave_message tool stores message content in state."""
        calendar = _make_mock_calendar()
        state = {
            "cabinet": _make_cabinet(),
            "messages": [],
            "pending_tool_calls": [
                ToolCall(
                    id="call_6",
                    name="leave_message",
                    arguments={"message": "J'ai mal au dos, rappelez-moi SVP"},
                )
            ],
        }

        result = await tool_exec_node(state, calendar=calendar)
        assert result["patient_message"] == "J'ai mal au dos, rappelez-moi SVP"

    @pytest.mark.asyncio
    async def test_non_leave_message_no_patient_message(self):
        """Non leave_message tools do not set patient_message."""
        calendar = _make_mock_calendar()
        state = {
            "cabinet": _make_cabinet(),
            "messages": [],
            "pending_tool_calls": [
                ToolCall(
                    id="call_7",
                    name="get_available_slots",
                    arguments={"date_hint": "lundi"},
                )
            ],
        }

        result = await tool_exec_node(state, calendar=calendar)
        assert "patient_message" not in result
