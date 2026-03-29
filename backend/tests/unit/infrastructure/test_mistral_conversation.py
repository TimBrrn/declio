"""Tests for MistralConversationAdapter — unit tests with mocked SDK."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.src.infrastructure.adapters.mistral_conversation import (
    MistralConversationAdapter,
    MODEL,
)


@pytest.fixture
def adapter():
    with patch(
        "backend.src.infrastructure.adapters.mistral_conversation.Mistral"
    ) as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        a = MistralConversationAdapter(api_key="test-key")
        a._mock_client = mock_client  # expose for tests
        return a


class TestChatWithTools:
    @pytest.mark.asyncio
    async def test_returns_text_and_empty_tools(self, adapter):
        """Basic response with text, no tool calls."""
        mock_msg = MagicMock()
        mock_msg.content = "Bonjour !"
        mock_msg.tool_calls = None

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 50
        mock_usage.completion_tokens = 20

        mock_choice = MagicMock()
        mock_choice.message = mock_msg

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        adapter._mock_client.chat.complete_async = AsyncMock(
            return_value=mock_response
        )

        text, tools, usage = await adapter.chat_with_tools(
            [{"role": "user", "content": "Bonjour"}]
        )

        assert text == "Bonjour !"
        assert tools == []
        assert usage.prompt_tokens == 50
        assert usage.completion_tokens == 20
        assert usage.model == MODEL

    @pytest.mark.asyncio
    async def test_returns_tool_calls(self, adapter):
        """Response with tool calls."""
        mock_tc = MagicMock()
        mock_tc.id = "call_123"
        mock_tc.function.name = "book_appointment"
        mock_tc.function.arguments = '{"slot_index": 2}'

        mock_msg = MagicMock()
        mock_msg.content = ""
        mock_msg.tool_calls = [mock_tc]

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 30

        mock_choice = MagicMock()
        mock_choice.message = mock_msg

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        adapter._mock_client.chat.complete_async = AsyncMock(
            return_value=mock_response
        )

        text, tools, usage = await adapter.chat_with_tools(
            [{"role": "user", "content": "Je veux un rdv"}],
            tools=[{"type": "function", "function": {"name": "book"}}],
        )

        assert text == ""
        assert len(tools) == 1
        assert tools[0].name == "book_appointment"
        assert tools[0].arguments == {"slot_index": 2}
        assert tools[0].id == "call_123"

    @pytest.mark.asyncio
    async def test_tool_call_dict_arguments(self, adapter):
        """Mistral may return dict arguments instead of JSON string."""
        mock_tc = MagicMock()
        mock_tc.id = "call_456"
        mock_tc.function.name = "get_available_slots"
        mock_tc.function.arguments = {"days": 3}

        mock_msg = MagicMock()
        mock_msg.content = None
        mock_msg.tool_calls = [mock_tc]

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 80
        mock_usage.completion_tokens = 25

        mock_choice = MagicMock()
        mock_choice.message = mock_msg

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        adapter._mock_client.chat.complete_async = AsyncMock(
            return_value=mock_response
        )

        text, tools, usage = await adapter.chat_with_tools(
            [{"role": "user", "content": "Quand êtes-vous libre ?"}]
        )

        assert tools[0].arguments == {"days": 3}

    @pytest.mark.asyncio
    async def test_null_usage_returns_zero_tokens(self, adapter):
        """Missing usage data returns zero tokens."""
        mock_msg = MagicMock()
        mock_msg.content = "Réponse"
        mock_msg.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_msg

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None

        adapter._mock_client.chat.complete_async = AsyncMock(
            return_value=mock_response
        )

        _, _, usage = await adapter.chat_with_tools(
            [{"role": "user", "content": "test"}]
        )

        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0

    @pytest.mark.asyncio
    async def test_malformed_tool_args_returns_empty_dict(self, adapter):
        """Malformed JSON in tool_call arguments → empty dict."""
        mock_tc = MagicMock()
        mock_tc.id = "call_bad"
        mock_tc.function.name = "test_tool"
        mock_tc.function.arguments = "not-valid-json"

        mock_msg = MagicMock()
        mock_msg.content = ""
        mock_msg.tool_calls = [mock_tc]

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 50
        mock_usage.completion_tokens = 10

        mock_choice = MagicMock()
        mock_choice.message = mock_msg

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        adapter._mock_client.chat.complete_async = AsyncMock(
            return_value=mock_response
        )

        _, tools, _ = await adapter.chat_with_tools(
            [{"role": "user", "content": "test"}]
        )

        assert tools[0].arguments == {}


class TestChatStream:
    @pytest.mark.asyncio
    async def test_stream_yields_text_deltas(self, adapter):
        """chat_stream yields text content from stream events."""
        event1 = MagicMock()
        event1.data.choices = [MagicMock()]
        event1.data.choices[0].delta.content = "Bonjour"

        event2 = MagicMock()
        event2.data.choices = [MagicMock()]
        event2.data.choices[0].delta.content = " monde"

        class MockStream:
            """Mock async iterable returned by stream_async."""
            def __aiter__(self):
                return self._gen().__aiter__()

            async def _gen(self):
                for e in [event1, event2]:
                    yield e

        adapter._mock_client.chat.stream_async = AsyncMock(
            return_value=MockStream()
        )

        chunks = []
        async for chunk in adapter.chat_stream(
            [{"role": "user", "content": "Salut"}]
        ):
            chunks.append(chunk)

        assert chunks == ["Bonjour", " monde"]
