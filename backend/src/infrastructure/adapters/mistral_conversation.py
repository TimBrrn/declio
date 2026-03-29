"""Mistral ConversationPort adapter — Mistral Small 3.1 avec function calling.

Remplace OpenAI GPT-4o. Meme interface (ConversationPort), 25x moins cher.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator

from mistralai.client import Mistral

from backend.src.domain.ports.conversation_port import ConversationPort, ToolCall
from backend.src.domain.value_objects.token_usage import TokenUsage

logger = logging.getLogger(__name__)

MODEL = "mistral-small-latest"
TEMPERATURE = 0.3
TIMEOUT_SECONDS = 15


class MistralConversationAdapter:
    """Implemente ConversationPort via le SDK Mistral."""

    model_name: str = MODEL

    def __init__(self, api_key: str) -> None:
        self._client = Mistral(api_key=api_key, timeout_ms=TIMEOUT_SECONDS * 1000)

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        """Streaming token par token. Yield chaque delta de texte."""
        start = time.monotonic()
        try:
            kwargs: dict[str, Any] = {
                "model": MODEL,
                "messages": messages,
                "temperature": TEMPERATURE,
            }
            if tools:
                kwargs["tools"] = tools

            stream = await self._client.chat.stream_async(**kwargs)

            async for event in stream:
                delta = event.data.choices[0].delta if event.data.choices else None
                if delta and delta.content:
                    yield delta.content

        except Exception as e:
            logger.error("Mistral chat_stream error: %s", e)
            raise
        finally:
            latency = (time.monotonic() - start) * 1000
            logger.info("chat_stream latency=%.0fms", latency)

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[str, list[ToolCall], TokenUsage]:
        """Appel non-streaming. Retourne reponse + tool_calls + usage."""
        start = time.monotonic()
        try:
            kwargs: dict[str, Any] = {
                "model": MODEL,
                "messages": messages,
                "temperature": TEMPERATURE,
            }
            if tools:
                kwargs["tools"] = tools

            response = await self._client.chat.complete_async(**kwargs)

            choice = response.choices[0]
            message = choice.message

            response_text = message.content or ""
            tool_calls: list[ToolCall] = []

            if message.tool_calls:
                for tc in message.tool_calls:
                    try:
                        args = tc.function.arguments
                        if isinstance(args, str):
                            arguments = json.loads(args)
                        elif isinstance(args, dict):
                            arguments = args
                        else:
                            arguments = {}
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(
                            "Malformed tool_call arguments: %s",
                            tc.function.arguments,
                        )
                        arguments = {}

                    tool_calls.append(
                        ToolCall(
                            id=tc.id,
                            name=tc.function.name,
                            arguments=arguments,
                        )
                    )

            # Build TokenUsage
            usage = response.usage
            if usage:
                token_usage = TokenUsage(
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    model=MODEL,
                )
            else:
                logger.warning("Mistral response.usage is None — defaulting to zero")
                token_usage = TokenUsage(model=MODEL)

            latency = (time.monotonic() - start) * 1000
            logger.info(
                "chat_with_tools model=%s latency=%.0fms "
                "prompt_tokens=%s completion_tokens=%s tool_calls=%d cost_usd=%.6f",
                MODEL,
                latency,
                token_usage.prompt_tokens,
                token_usage.completion_tokens,
                len(tool_calls),
                token_usage.cost_usd,
            )

            return response_text, tool_calls, token_usage

        except Exception as e:
            logger.error("Mistral chat_with_tools error: %s", e)
            raise
