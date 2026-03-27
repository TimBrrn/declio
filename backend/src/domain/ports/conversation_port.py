from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Protocol

from backend.src.domain.value_objects.token_usage import TokenUsage


@dataclass(frozen=True)
class ToolCall:
    """Representation d'un appel de tool demande par le LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


class ConversationPort(Protocol):
    """Contrat LLM conversation — implemente par OpenAI adapter."""

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        """Yield tokens de reponse en streaming."""
        ...

    async def chat_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[str, list[ToolCall], TokenUsage]:
        """Retourne la reponse complete + les tool calls eventuels + usage tokens."""
        ...
