"""Tests for TokenUsage value object and pricing constants."""

from __future__ import annotations

from backend.src.domain.value_objects.token_usage import (
    DEEPGRAM_PRICE_PER_MINUTE,
    ELEVENLABS_PRICE_PER_1K_CHARS,
    MODEL_PRICING,
    USD_TO_EUR,
    TokenUsage,
)


class TestTokenUsage:
    def test_total_tokens(self):
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50)
        assert usage.total_tokens == 150

    def test_zero_tokens(self):
        usage = TokenUsage()
        assert usage.total_tokens == 0
        assert usage.cost_usd == 0.0

    def test_cost_gpt4o(self):
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=200, model="gpt-4o")
        # (1000 * 2.50 + 200 * 10.00) / 1_000_000
        expected = (1000 * 2.50 + 200 * 10.00) / 1_000_000
        assert abs(usage.cost_usd - expected) < 1e-10

    def test_cost_gpt4o_mini(self):
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=200, model="gpt-4o-mini")
        expected = (1000 * 0.15 + 200 * 0.60) / 1_000_000
        assert abs(usage.cost_usd - expected) < 1e-10

    def test_unknown_model_falls_back_to_gpt4o(self):
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=200, model="unknown-model")
        usage_gpt4o = TokenUsage(prompt_tokens=1000, completion_tokens=200, model="gpt-4o")
        assert usage.cost_usd == usage_gpt4o.cost_usd

    def test_frozen(self):
        usage = TokenUsage(prompt_tokens=100)
        import pytest
        with pytest.raises(AttributeError):
            usage.prompt_tokens = 200  # type: ignore[misc]

    def test_default_model(self):
        usage = TokenUsage()
        assert usage.model == "gpt-4o"


class TestPricingConstants:
    def test_model_pricing_has_gpt4o(self):
        assert "gpt-4o" in MODEL_PRICING
        assert "input" in MODEL_PRICING["gpt-4o"]
        assert "output" in MODEL_PRICING["gpt-4o"]

    def test_deepgram_price(self):
        assert DEEPGRAM_PRICE_PER_MINUTE == 0.0043

    def test_elevenlabs_price(self):
        assert ELEVENLABS_PRICE_PER_1K_CHARS == 0.30

    def test_usd_to_eur(self):
        assert USD_TO_EUR == 0.92
