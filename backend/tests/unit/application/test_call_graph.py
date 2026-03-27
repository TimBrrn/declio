"""Tests du graphe conversationnel LangGraph avec ports mockes."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.src.application.graph.nodes.greeting import greeting_node
from backend.src.application.graph.nodes.listening import listening_node
from backend.src.application.graph.nodes.responding import responding_node
from backend.src.application.graph.nodes.thinking import thinking_node
from backend.src.application.graph.nodes.tool_exec import tool_exec_node
from backend.src.domain.entities.cabinet import Cabinet
from backend.src.domain.entities.call_record import CallRecord, ScenarioEnum
from backend.src.domain.ports.conversation_port import ToolCall
from backend.src.domain.value_objects.token_usage import TokenUsage


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


def _make_call_record() -> CallRecord:
    return CallRecord(
        id="call-1",
        cabinet_id="cab-1",
        caller_phone="0612345678",
    )


# ── Greeting ─────────────────────────────────────────────────


class TestGreetingNode:
    def test_greeting_creates_message(self):
        state = {
            "cabinet": _make_cabinet(),
            "messages": [],
        }
        result = greeting_node(state)
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)
        assert "Jean Dupont" in result["messages"][0].content

    def test_greeting_sets_response_text(self):
        state = {
            "cabinet": _make_cabinet(),
            "messages": [],
        }
        result = greeting_node(state)
        assert "Jean Dupont" in result["response_text"]


# ── Listening ────────────────────────────────────────────────


class TestListeningNode:
    def test_adds_human_message(self):
        state = {
            "messages": [],
            "current_transcript": "Bonjour, je voudrais un rdv",
            "stt_confidence": 0.95,
        }
        result = listening_node(state)
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], HumanMessage)

    def test_low_confidence_asks_to_repeat(self):
        state = {
            "messages": [],
            "current_transcript": "hmm...",
            "stt_confidence": 0.3,
        }
        result = listening_node(state)
        # Human message + AI repeat request
        assert len(result["messages"]) == 2
        assert "repeter" in result["response_text"].lower()

    def test_empty_transcript(self):
        state = {
            "messages": [],
            "current_transcript": "",
            "stt_confidence": 0.0,
        }
        result = listening_node(state)
        assert len(result["messages"]) == 0


# ── Responding ───────────────────────────────────────────────


class TestRespondingNode:
    def test_passes_response_text(self):
        state = {
            "response_text": "Bien sur, je regarde les creneaux.",
        }
        result = responding_node(state)
        assert result["response_text"] == "Bien sur, je regarde les creneaux."


# ── Scenario complet : greeting → listening → thinking → tool_exec → thinking → responding


class TestFullScenario:
    """Test bout-en-bout du flow greeting → ... → responding."""

    @pytest.mark.asyncio
    async def test_booking_flow(self):
        cabinet = _make_cabinet()

        # Step 1: GREETING
        state = {"cabinet": cabinet, "messages": []}
        greeting_result = greeting_node(state)
        assert "Jean Dupont" in greeting_result["response_text"]

        # Step 2: LISTENING — patient dit "je voudrais un rdv"
        state_after_greeting = {
            "cabinet": cabinet,
            "messages": greeting_result["messages"],
            "current_transcript": "Bonjour, je voudrais prendre un rendez-vous",
            "stt_confidence": 0.92,
        }
        listening_result = listening_node(state_after_greeting)
        assert isinstance(listening_result["messages"][-1], HumanMessage)

        # Step 3: THINKING — LLM decide d'appeler get_available_slots
        conversation = AsyncMock()
        tc = ToolCall(
            id="call_slots",
            name="get_available_slots",
            arguments={"date_hint": "cette semaine"},
        )
        conversation.chat_with_tools = AsyncMock(return_value=("", [tc], TokenUsage()))

        state_after_listening = {
            "cabinet": cabinet,
            "messages": listening_result["messages"],
        }
        thinking_result = await thinking_node(
            state_after_listening, conversation=conversation
        )
        assert len(thinking_result["pending_tool_calls"]) == 1
        assert thinking_result["pending_tool_calls"][0].name == "get_available_slots"

        # Step 4: TOOL_EXEC — execute get_available_slots
        calendar = AsyncMock()
        calendar.get_available_slots = AsyncMock(return_value=[])

        state_after_thinking = {
            "cabinet": cabinet,
            "messages": thinking_result["messages"],
            "pending_tool_calls": thinking_result["pending_tool_calls"],
        }
        tool_result = await tool_exec_node(state_after_thinking, calendar=calendar)
        tool_msgs = [m for m in tool_result["messages"] if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert tool_result["pending_tool_calls"] == []

        # Step 5: THINKING again — LLM formule la reponse
        conversation.chat_with_tools = AsyncMock(
            return_value=("Je suis desole, aucun creneau n'est disponible cette semaine.", [], TokenUsage())
        )
        state_after_tool = {
            "cabinet": cabinet,
            "messages": tool_result["messages"],
        }
        thinking_result2 = await thinking_node(
            state_after_tool, conversation=conversation
        )
        assert "aucun creneau" in thinking_result2["response_text"].lower()
        assert thinking_result2["pending_tool_calls"] == []

        # Step 6: RESPONDING
        state_for_responding = {
            "response_text": thinking_result2["response_text"],
        }
        responding_result = responding_node(state_for_responding)
        assert "aucun creneau" in responding_result["response_text"].lower()
