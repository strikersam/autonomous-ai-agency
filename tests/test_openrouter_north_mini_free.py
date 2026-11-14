"""OpenRouter's free North Mini Code is declared in the gateway catalogue.

It existed only in the brain presets, so the LLM gateway never tried it while
every other free tier was rate limited. It is $0, so it needs no paid opt-in and
nothing here can spend money.
"""
from __future__ import annotations

from packages.llm.config import load_config
from packages.llm.registry import ModelRegistry


def test_north_mini_code_free_is_a_zero_cost_tool_capable_openrouter_model():
    reg = ModelRegistry(load_config())
    m = reg.get("cohere/north-mini-code:free")
    assert m is not None and m.provider == "openrouter"
    assert m.input_cost_per_1m == 0.0 and m.output_cost_per_1m == 0.0
    assert m.is_free and not m.paid_opt_in
    assert m.supports_tools and m.context_window == 256000


def test_it_serves_with_paid_brain_off_and_no_paid_model_does():
    reg = ModelRegistry(load_config())
    served = reg.candidates(allow_paid=False, require_tools=True)
    assert "cohere/north-mini-code:free" in {m.id for m in served}
    assert [m.id for m in served if not m.is_free and not m.paid_opt_in] == []
