"""Tests thinking node — system prompt, routing, message conversion."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.src.application.graph.nodes.thinking import (
    _convert_messages,
    _load_system_prompt,
    thinking_node,
)
from backend.src.domain.entities.cabinet import Cabinet
from backend.src.domain.ports.conversation_port import ToolCall
from backend.src.domain.value_objects.token_usage import TokenUsage


def _make_cabinet() -> Cabinet:
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


# ── System prompt ────────────────────────────────────────────


class TestSystemPrompt:
    def test_includes_cabinet_name(self):
        prompt = _load_system_prompt(_make_cabinet())
        assert "Kine Dupont" in prompt

    def test_includes_praticien(self):
        prompt = _load_system_prompt(_make_cabinet())
        assert "Jean Dupont" in prompt

    def test_includes_adresse(self):
        prompt = _load_system_prompt(_make_cabinet())
        assert "12 rue de la Sante" in prompt

    def test_includes_horaires(self):
        prompt = _load_system_prompt(_make_cabinet())
        assert "lundi" in prompt
        assert "09:00-12:00" in prompt

    def test_includes_tarifs(self):
        prompt = _load_system_prompt(_make_cabinet())
        assert "50 euros" in prompt

    def test_includes_scenario_prompts(self):
        prompt = _load_system_prompt(_make_cabinet())
        # Les scenario prompts doivent etre charges
        assert "rendez-vous" in prompt.lower() or "Prise de rendez-vous" in prompt

    def test_includes_interdictions(self):
        prompt = _load_system_prompt(_make_cabinet())
        assert "Interdictions" in prompt
        assert "intelligence artificielle" in prompt.lower()

    def test_includes_edge_cases(self):
        prompt = _load_system_prompt(_make_cabinet())
        assert "change d'avis" in prompt.lower()
        assert "agressif" in prompt.lower()

    def test_includes_tts_format(self):
        prompt = _load_system_prompt(_make_cabinet())
        assert "format oral" in prompt.lower()
        assert "quarante euros" in prompt.lower()

    def test_includes_confirm_booking_in_example(self):
        prompt = _load_system_prompt(_make_cabinet())
        assert "confirm_booking" in prompt


# ── Message conversion ───────────────────────────────────────


class TestConvertMessages:
    def test_human_message(self):
        msgs = [HumanMessage(content="Bonjour")]
        result = _convert_messages(msgs)
        assert result == [{"role": "user", "content": "Bonjour"}]

    def test_ai_message(self):
        msgs = [AIMessage(content="Bonjour !")]
        result = _convert_messages(msgs)
        assert result == [{"role": "assistant", "content": "Bonjour !"}]

    def test_tool_message(self):
        msgs = [ToolMessage(content="Creneau dispo", tool_call_id="call_1")]
        result = _convert_messages(msgs)
        assert result == [
            {"role": "tool", "content": "Creneau dispo", "tool_call_id": "call_1"}
        ]

    def test_ai_message_with_tool_calls(self):
        tc = [{"id": "call_1", "type": "function", "function": {"name": "test", "arguments": "{}"}}]
        msgs = [AIMessage(content="", additional_kwargs={"tool_calls": tc})]
        result = _convert_messages(msgs)
        assert result[0]["role"] == "assistant"
        assert result[0]["tool_calls"] == tc
        assert result[0]["content"] is None

    def test_mixed_messages(self):
        msgs = [
            AIMessage(content="Bienvenue"),
            HumanMessage(content="Un rdv svp"),
            AIMessage(content="Bien sur"),
        ]
        result = _convert_messages(msgs)
        assert len(result) == 3
        assert result[0]["role"] == "assistant"
        assert result[1]["role"] == "user"
        assert result[2]["role"] == "assistant"


# ── Thinking node ────────────────────────────────────────────


class TestThinkingNode:
    @pytest.mark.asyncio
    async def test_direct_response_no_tool(self):
        conversation = AsyncMock()
        conversation.chat_with_tools = AsyncMock(
            return_value=("Bien sur, je regarde.", [], TokenUsage())
        )

        state = {
            "cabinet": _make_cabinet(),
            "messages": [HumanMessage(content="Un rdv svp")],
        }

        result = await thinking_node(state, conversation=conversation)

        assert result["response_text"] == "Bien sur, je regarde."
        assert result["pending_tool_calls"] == []
        assert result["should_hangup"] is False

    @pytest.mark.asyncio
    async def test_response_with_tool_calls(self):
        conversation = AsyncMock()
        tc = ToolCall(id="call_1", name="get_available_slots", arguments={"date_hint": "lundi"})
        conversation.chat_with_tools = AsyncMock(
            return_value=("", [tc], TokenUsage())
        )

        state = {
            "cabinet": _make_cabinet(),
            "messages": [HumanMessage(content="Un rdv lundi")],
        }

        result = await thinking_node(state, conversation=conversation)

        assert len(result["pending_tool_calls"]) == 1
        assert result["pending_tool_calls"][0].name == "get_available_slots"
        # AIMessage should have tool_calls in additional_kwargs
        ai_msgs = [m for m in result["messages"] if isinstance(m, AIMessage)]
        assert len(ai_msgs) >= 1
        last_ai = ai_msgs[-1]
        assert "tool_calls" in last_ai.additional_kwargs

    @pytest.mark.asyncio
    async def test_end_conversation_sets_hangup(self):
        conversation = AsyncMock()
        tc = ToolCall(id="call_end", name="end_conversation", arguments={})
        conversation.chat_with_tools = AsyncMock(
            return_value=("Au revoir !", [tc], TokenUsage())
        )

        state = {
            "cabinet": _make_cabinet(),
            "messages": [HumanMessage(content="Merci, au revoir")],
        }

        result = await thinking_node(state, conversation=conversation)

        assert result["should_hangup"] is True
        # end_conversation should NOT be in pending_tool_calls
        assert all(
            tc.name != "end_conversation"
            for tc in result["pending_tool_calls"]
        )

    @pytest.mark.asyncio
    async def test_extracts_patient_name(self):
        conversation = AsyncMock()
        tc = ToolCall(
            id="call_c",
            name="cancel_appointment",
            arguments={"patient_name": "Dupont", "date_hint": "jeudi"},
        )
        conversation.chat_with_tools = AsyncMock(return_value=("", [tc], TokenUsage()))

        state = {
            "cabinet": _make_cabinet(),
            "messages": [HumanMessage(content="Annuler le rdv de Dupont")],
        }

        result = await thinking_node(state, conversation=conversation)
        assert result["patient_name"] == "Dupont"
