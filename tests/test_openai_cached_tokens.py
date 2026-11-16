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
        # Malformed counts must not raise: a raise would skip cost, user-token and
        # agent-spend recording in the router's cost hook, understating budgets.
        ({"prompt_tokens": 1000, "prompt_tokens_details": {"cached_tokens": "many"}}, 0),
        ({"prompt_tokens": 1000, "input_tokens_details": {"cached_tokens": [1]}}, 0),
        ({"cache_read_input_tokens": "unreadable", "prompt_tokens": 1000}, 0),
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
    assert "usage_counts(" in src
    assert '_usage.get("cache_read_input_tokens")' not in src
    # No bare int() on a provider-supplied count may remain in the cost hook.
    assert "int(_usage.get(" not in src


def test_malformed_cache_counts_still_record_cost():
    """A junk cached-token count reads as 0 tokens cached, so the response is
    still billed at the full input rate instead of the charge being skipped."""
    usage = {"prompt_tokens": 1_000_000, "prompt_tokens_details": {"cached_tokens": "junk"}}
    cost = cost_for_tokens("gemini-4-argon", 1_000_000, 0, cached_prompt_tokens(usage))
    assert cost == pytest.approx(cost_for_tokens("gemini-4-argon", 1_000_000, 0, 0))


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan"), "many", [1], {"a": 1}, -5])
def test_no_malformed_count_raises_or_goes_negative(bad):
    """float("inf") raised OverflowError past the old (TypeError, ValueError) guard."""
    from packages.ai.cost_tracker import _usage_int, anthropic_prompt_tokens, usage_counts

    assert _usage_int(bad) == 0
    for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
        assert anthropic_prompt_tokens({"input_tokens": 10, key: bad}) >= 0
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        counts = usage_counts({"prompt_tokens": 10, "completion_tokens": 5, key: bad})
        assert all(isinstance(c, int) and c >= 0 for c in counts)


def test_anthropic_prompt_total_survives_an_unreadable_cache_count():
    """anthropic_prompt_tokens called int() directly on cache_read_input_tokens."""
    from packages.ai.cost_tracker import anthropic_prompt_tokens

    usage = {"input_tokens": 100, "cache_read_input_tokens": "many", "cache_creation_input_tokens": 7}
    assert anthropic_prompt_tokens(usage) == 107


def test_usage_counts_matches_the_old_hook_for_well_formed_usage():
    from packages.ai.cost_tracker import usage_counts

    openai = {
        "prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200,
        "prompt_tokens_details": {"cached_tokens": 600},
    }
    assert usage_counts(openai) == (1000, 200, 600, 1200)
    assert usage_counts({"prompt_tokens": 30, "completion_tokens": 12}) == (30, 12, 0, 42)
    anthropic = {
        "prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70,
        "cache_read_input_tokens": 400, "cache_creation_input_tokens": 10,
    }
    assert usage_counts(anthropic, anthropic=True) == (460, 20, 400, 70)


def test_a_junk_total_still_charges_the_agent_for_prompt_plus_completion():
    from packages.ai.cost_tracker import usage_counts

    assert usage_counts({"prompt_tokens": 30, "completion_tokens": 12, "total_tokens": "?"})[3] == 42
