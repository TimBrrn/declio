"""Tests OpenAI adapter avec mock du SDK."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.src.domain.ports.conversation_port import ToolCall
from backend.src.infrastructure.adapters.openai_conversation import (
    OpenAIConversationAdapter,
)


def _make_adapter() -> OpenAIConversationAdapter:
    return OpenAIConversationAdapter(api_key="test-key")


def _mock_completion(content: str = "Bonjour", tool_calls=None):
    """Cree un mock de ChatCompletion response."""
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls

    choice = MagicMock()
    choice.message = message

    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _mock_tool_call(tc_id: str, name: str, arguments: str):
    """Cree un mock de tool_call OpenAI."""
    tc = MagicMock()
    tc.id = tc_id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


# ── chat_with_tools ──────────────────────────────────────────


class TestChatWithTools:
    @pytest.mark.asyncio
    async def test_happy_path_text_response(self):
        adapter = _make_adapter()
        mock_response = _mock_completion(content="Bien sur, je regarde.")

        with patch.object(
            adapter._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            text, tool_calls, token_usage = await adapter.chat_with_tools(
                messages=[{"role": "user", "content": "Bonjour"}],
            )

        assert text == "Bien sur, je regarde."
        assert tool_calls == []
        assert token_usage.prompt_tokens == 10
        assert token_usage.completion_tokens == 5

    @pytest.mark.asyncio
    async def test_response_with_tool_calls(self):
        adapter = _make_adapter()
        tc = _mock_tool_call(
            "call_123", "get_available_slots", '{"date_hint": "lundi"}'
        )
        mock_response = _mock_completion(content="", tool_calls=[tc])

        with patch.object(
            adapter._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            text, tool_calls, token_usage = await adapter.chat_with_tools(
                messages=[{"role": "user", "content": "Un rdv lundi"}],
                tools=[{"type": "function", "function": {"name": "test"}}],
            )

        assert text == ""
        assert len(tool_calls) == 1
        assert token_usage.total_tokens == 15
        assert tool_calls[0].id == "call_123"
        assert tool_calls[0].name == "get_available_slots"
        assert tool_calls[0].arguments == {"date_hint": "lundi"}

    @pytest.mark.asyncio
    async def test_malformed_tool_arguments(self):
        adapter = _make_adapter()
        tc = _mock_tool_call("call_456", "book_appointment", "not-valid-json")
        mock_response = _mock_completion(content="", tool_calls=[tc])

        with patch.object(
            adapter._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            text, tool_calls, token_usage = await adapter.chat_with_tools(
                messages=[{"role": "user", "content": "test"}],
            )

        assert len(tool_calls) == 1
        assert tool_calls[0].arguments == {}
        assert token_usage.model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_usage_none_returns_zero_token_usage(self):
        adapter = _make_adapter()
        mock_response = _mock_completion(content="Ok")
        mock_response.usage = None  # Simulate missing usage

        with patch.object(
            adapter._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            text, tool_calls, token_usage = await adapter.chat_with_tools(
                messages=[{"role": "user", "content": "test"}],
            )

        assert token_usage.prompt_tokens == 0
        assert token_usage.completion_tokens == 0
        assert token_usage.cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        from openai import APITimeoutError

        adapter = _make_adapter()

        with patch.object(
            adapter._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = APITimeoutError(request=MagicMock())

            with pytest.raises(APITimeoutError):
                await adapter.chat_with_tools(
                    messages=[{"role": "user", "content": "test"}],
                )


# ── chat_stream ──────────────────────────────────────────────


class TestChatStream:
    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self):
        adapter = _make_adapter()

        # Mock streaming chunks
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta = MagicMock()
        chunk1.choices[0].delta.content = "Bon"

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta = MagicMock()
        chunk2.choices[0].delta.content = "jour"

        chunk3 = MagicMock()
        chunk3.choices = [MagicMock()]
        chunk3.choices[0].delta = MagicMock()
        chunk3.choices[0].delta.content = None

        async def mock_stream():
            for c in [chunk1, chunk2, chunk3]:
                yield c

        with patch.object(
            adapter._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_stream()

            tokens = []
            async for token in adapter.chat_stream(
                messages=[{"role": "user", "content": "Bonjour"}],
            ):
                tokens.append(token)

        assert tokens == ["Bon", "jour"]
