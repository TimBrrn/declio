from __future__ import annotations

from dataclasses import dataclass

# ── Pricing constants — single source of truth ──────────────────
# All prices in USD.

MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

DEEPGRAM_PRICE_PER_MINUTE = 0.0043  # Nova-2
ELEVENLABS_PRICE_PER_1K_CHARS = 0.30  # Multilingual v2
USD_TO_EUR = 0.92


@dataclass(frozen=True)
class TokenUsage:
    """Usage de tokens LLM pour un appel unique au modele."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = "gpt-4o"

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def cost_usd(self) -> float:
        pricing = MODEL_PRICING.get(self.model, MODEL_PRICING["gpt-4o"])
        return (
            self.prompt_tokens * pricing["input"]
            + self.completion_tokens * pricing["output"]
        ) / 1_000_000
