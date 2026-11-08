from __future__ import annotations

import inspect

import pytest

from packages.ai.cost_tracker import cached_prompt_tokens, cost_for_tokens


@pytest.mark.parametrize(
    "usage, expected",
    [
        ({"cache_read_input_tokens": 700, "prompt_tokens": 1000}, 700),
        ({"prompt_tokens": 1000, "prompt_tokens_details": {"cached_tokens": 600}}, 600),
        ({"input_tokens": 1000, "input_tokens_details": {"cached_tokens": 400}}, 400),
        ({"prompt_tokens": 1000, "prompt_tokens_details": {"cached_tokens": None}}, 0),
        ({"prompt_tokens": 1000, "prompt_tokens_details": None}, 0),
        ({"prompt_tokens": 1000}, 0),
        ({}, 0),
    ],
)
def test_cached_prompt_tokens_reads_every_usage_shape(usage, expected):
    assert cached_prompt_tokens(usage) == expected


def test_openai_shaped_cache_hits_are_discounted():
    """Gemini 4 Argon served through an OpenAI-compatible endpoint reports cache
    hits in prompt_tokens_details; read that way they cost 5% of the input rate."""
    usage = {
        "prompt_tokens": 1_000_000,
        "completion_tokens": 0,
        "prompt_tokens_details": {"cached_tokens": 1_000_000},
    }
    cost = cost_for_tokens("gemini-4-argon", 1_000_000, 0, cached_prompt_tokens(usage))
    assert cost == pytest.approx(cost_for_tokens("gemini-4-argon", 1_000_000, 0, 0) * 0.05)


def test_router_records_cost_from_the_shared_helper():
    """The router's cost hook read only Anthropic's cache_read_input_tokens, so
    every other provider's cache reads were billed at the full input rate."""
    from packages.ai.router import ProviderRouter

    src = inspect.getsource(ProviderRouter._try_one_provider)
    assert "cached_prompt_tokens(_usage)" in src
    assert '_usage.get("cache_read_input_tokens")' not in src
