"""OpenAI ConversationPort adapter — GPT-4o avec function calling.

Exception architecturale : cet adapter est dans infrastructure/ mais
est gere par l'agent LLM car intimement lie a la logique conversationnelle.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator

from openai import AsyncOpenAI, APITimeoutError, RateLimitError

from backend.src.domain.ports.conversation_port import ConversationPort, ToolCall
from backend.src.domain.value_objects.token_usage import TokenUsage

logger = logging.getLogger(__name__)

MODEL = "gpt-4o"
TEMPERATURE = 0.3
TIMEOUT_SECONDS = 15


class OpenAIConversationAdapter:
    """Implemente ConversationPort via le SDK OpenAI."""

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=TIMEOUT_SECONDS)

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
                "stream": True,
            }
            if tools:
                kwargs["tools"] = tools

            stream = await self._client.chat.completions.create(**kwargs)

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content

        except APITimeoutError:
            logger.error("OpenAI timeout apres %ds", TIMEOUT_SECONDS)
            raise
        except RateLimitError:
            logger.error("OpenAI rate limit (429)")
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

            response = await self._client.chat.completions.create(**kwargs)

            choice = response.choices[0]
            message = choice.message

            response_text = message.content or ""
            tool_calls: list[ToolCall] = []

            if message.tool_calls:
                for tc in message.tool_calls:
                    try:
                        arguments = json.loads(tc.function.arguments)
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
                logger.warning("OpenAI response.usage is None — defaulting to zero")
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

        except APITimeoutError:
            logger.error("OpenAI timeout apres %ds", TIMEOUT_SECONDS)
            raise
        except RateLimitError:
            logger.error("OpenAI rate limit (429)")
            raise
