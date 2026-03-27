"""Shared test helpers for application layer tests."""

from __future__ import annotations

from backend.src.domain.ports.conversation_port import ToolCall
from backend.src.domain.value_objects.token_usage import TokenUsage


def _mock_llm_response(
    text: str = "",
    tools: list[ToolCall] | None = None,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    model: str = "gpt-4o",
) -> tuple[str, list[ToolCall], TokenUsage]:
    """Build a 3-tuple matching ConversationPort.chat_with_tools return type."""
    return (
        text,
        tools or [],
        TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model,
        ),
    )
