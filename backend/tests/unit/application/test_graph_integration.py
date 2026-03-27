"""Tests d'integration du graphe avec une entite Cabinet reelle."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.src.application.graph.nodes.greeting import greeting_node
from backend.src.application.graph.nodes.thinking import (
    _format_montant,
    _format_tarifs,
    _load_system_prompt,
    thinking_node,
)
from backend.src.application.graph.nodes.tool_exec import tool_exec_node
from backend.src.domain.entities.cabinet import Cabinet
from backend.src.domain.ports.conversation_port import ToolCall
from backend.src.domain.value_objects.token_usage import TokenUsage


def _make_kine_cabinet() -> Cabinet:
    """Cabinet kine realiste avec tarif a centimes et FAQ."""
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


# ── Format helpers ──────────────────────────────────────────


class TestFormatMontant:
    def test_entier(self):
        assert _format_montant(50.0) == "50 euros"

    def test_centimes(self):
        result = _format_montant(16.13)
        assert "16 euros" in result
        assert "13 centimes" in result

    def test_centimes_single_digit(self):
        result = _format_montant(25.05)
        assert "25 euros" in result
        assert "05 centimes" in result

    def test_zero(self):
        assert _format_montant(0.0) == "0 euros"


class TestFormatTarifs:
    def test_kine_tarif_centimes(self):
        result = _format_tarifs({"seance_kine": 16.13})
        assert "16 euros" in result
        assert "13 centimes" in result
        assert "seance_kine" in result

    def test_multiple_tarifs(self):
        result = _format_tarifs({"seance": 50.0, "bilan": 70.0})
        assert "50 euros" in result
        assert "70 euros" in result
        assert "centimes" not in result

    def test_empty(self):
        result = _format_tarifs({})
        assert "Non renseignes" in result


# ── Greeting node with real Cabinet ─────────────────────────


class TestGreetingIntegration:
    def test_greeting_contains_cabinet_name(self):
        cabinet = _make_kine_cabinet()
        state = {"cabinet": cabinet, "messages": []}

        result = greeting_node(state)

        assert "Jean Dupont" in result["response_text"]
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

    def test_greeting_mentions_assistant(self):
        cabinet = _make_kine_cabinet()
        state = {"cabinet": cabinet, "messages": []}

        result = greeting_node(state)

        assert "assistant" in result["response_text"].lower()


# ── System prompt with real Cabinet ─────────────────────────


class TestSystemPromptIntegration:
    def test_includes_cabinet_name(self):
        prompt = _load_system_prompt(_make_kine_cabinet())
        assert "Cabinet Dupont Kine" in prompt

    def test_includes_praticien(self):
        prompt = _load_system_prompt(_make_kine_cabinet())
        assert "Jean Dupont" in prompt

    def test_includes_adresse(self):
        prompt = _load_system_prompt(_make_kine_cabinet())
        assert "12 rue de la Sante" in prompt

    def test_includes_horaires(self):
        prompt = _load_system_prompt(_make_kine_cabinet())
        assert "lundi" in prompt
        assert "09:00-12:00" in prompt
        assert "14:00-19:00" in prompt

    def test_tarif_centimes_preserved(self):
        prompt = _load_system_prompt(_make_kine_cabinet())
        assert "16 euros" in prompt
        assert "13 centimes" in prompt

    def test_tarif_exemple_has_centimes(self):
        prompt = _load_system_prompt(_make_kine_cabinet())
        # The tarif_exemple placeholder should also have centimes
        # Check it's not truncated to "16 euros" without centimes
        assert "16 euros" in prompt
        # Should appear in the example conversation section too
        assert "13 centimes" in prompt

    def test_kine_faq_ordonnance(self):
        prompt = _load_system_prompt(_make_kine_cabinet())
        assert "ordonnance" in prompt.lower()

    def test_kine_faq_carte_vitale(self):
        prompt = _load_system_prompt(_make_kine_cabinet())
        assert "carte vitale" in prompt.lower()

    def test_kine_booking_30min(self):
        prompt = _load_system_prompt(_make_kine_cabinet())
        assert "30 minutes" in prompt

    def test_kine_report_annulation(self):
        prompt = _load_system_prompt(_make_kine_cabinet())
        assert "report" in prompt.lower()


# ── Thinking node with real Cabinet ─────────────────────────


class TestThinkingIntegration:
    @pytest.mark.asyncio
    async def test_cabinet_entity_passed_to_llm(self):
        """Verify the full Cabinet entity is properly used in thinking_node."""
        conversation = AsyncMock()
        conversation.chat_with_tools = AsyncMock(
            return_value=("Bienvenue au Cabinet Dupont Kine.", [], TokenUsage())
        )

        state = {
            "cabinet": _make_kine_cabinet(),
            "messages": [HumanMessage(content="Bonjour")],
        }

        result = await thinking_node(state, conversation=conversation)

        assert result["response_text"] == "Bienvenue au Cabinet Dupont Kine."
        # Verify the system prompt was passed to the LLM
        call_args = conversation.chat_with_tools.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        assert "Cabinet Dupont Kine" in system_msg["content"]
        assert "16 euros" in system_msg["content"]
        assert "13 centimes" in system_msg["content"]


# ── Tool exec node with real Cabinet ────────────────────────


class TestToolExecIntegration:
    @pytest.mark.asyncio
    async def test_get_available_slots_with_cabinet(self):
        """Verify tool_exec passes real Cabinet to use cases."""
        calendar = AsyncMock()
        calendar.get_available_slots = AsyncMock(return_value=[])

        tc = ToolCall(
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
                        "function": {"name": "get_available_slots", "arguments": "{}"},
                    }
                ]
            },
        )

        state = {
            "cabinet": _make_kine_cabinet(),
            "messages": [ai_msg],
            "pending_tool_calls": [tc],
        }

        result = await tool_exec_node(state, calendar=calendar)

        # Calendar was called with the real cabinet ID
        calendar.get_available_slots.assert_called_once()
        call_kwargs = calendar.get_available_slots.call_args
        assert call_kwargs.kwargs.get("cabinet_id") == "cab-1"

        # ToolMessage was appended
        tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
