"""tests/test_daily_automation_2026_10_07.py — Daily automation 2026-10-07.

One change lands today (a proposed NVIDIA NIM
``nvidia/llama-3.3-nemotron-super-49b-v1.5`` addition was dropped: that id is
on RETIRED in tests/test_nvidia_default_model.py).

1. **Groq prompt-caching cost fractions** — Groq's implicit caching
   (automatic, 5-min TTL, no code changes required) discounts cached input
   tokens by 50 %.  The ``_CACHE_READ_FRACTIONS`` table in ``cost_tracker.py``
   gains entries for ``qwen/`` and ``meta-llama/`` model-id prefixes so that
   ``cost_for_tokens`` attributes the correct reduced cost when Groq reports
   ``prompt_tokens_details.cached_tokens`` in a completion response.
   The free ``openai/gpt-oss-*`` ids cost $0, so no fraction is needed there.
   Source: console.groq.com/docs/prompt-caching (2026-07).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_07",
        REPO_ROOT / "packages" / "ai" / "cost_tracker.py",
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def llm_models():
    return yaml.safe_load(
        (REPO_ROOT / "config" / "llm" / "models.yaml").read_text()
    )["models"]


@pytest.fixture(scope="module")
def legacy_models():
    return yaml.safe_load(
        (REPO_ROOT / "config" / "models.yaml").read_text()
    )


@pytest.fixture(scope="module")
def brain_cfg_text():
    """Return the raw text of brain_config.py — used when pydantic_core is not
    compiled for the test Python (C-extension mismatch in CI).  Tests grep the
    source text rather than importing the live module."""
    return (REPO_ROOT / "packages" / "ai" / "brain_config.py").read_text()


# ---------------------------------------------------------------------------
# Groq prompt-caching cost fractions
# ---------------------------------------------------------------------------

class TestGroqPromptCachingFractions:
    """Groq implicit caching discounts cached input tokens by 50 %.
    We test the three paid Groq models: qwen3.8-27b and llama-4-scout.
    The free openai/gpt-oss-* models cost $0 so no test needed there.
    """

    def test_qwen_fraction_exists(self, ct):
        """qwen/ prefix must have a fraction < 1.0 in _CACHE_READ_FRACTIONS."""
        frac = ct._cache_read_fraction("qwen/qwen3.8-27b")
        assert frac == pytest.approx(0.50), (
            "qwen/qwen3.8-27b cache-read fraction must be 0.50 (50 % discount)"
        )

    def test_meta_llama_fraction_exists(self, ct):
        frac = ct._cache_read_fraction("meta-llama/llama-4-scout-17b-16e-instruct")
        assert frac == pytest.approx(0.50), (
            "meta-llama/llama-4-scout cache-read fraction must be 0.50"
        )

    def test_qwen_cache_reduces_cost(self, ct):
        """1M cached input tokens on qwen3.8-27b should cost half the non-cached rate."""
        full_cost = ct.cost_for_tokens("qwen/qwen3.8-27b", 1_000_000, 0, cached_tokens=0)
        cached_cost = ct.cost_for_tokens("qwen/qwen3.8-27b", 1_000_000, 0, cached_tokens=1_000_000)
        assert cached_cost == pytest.approx(full_cost * 0.50), (
            "All-cached request must cost 50 % of the uncached equivalent"
        )

    def test_qwen_mixed_cache_cost(self, ct):
        """500K cached + 500K non-cached should cost 75 % of a fully non-cached request."""
        full_cost = ct.cost_for_tokens("qwen/qwen3.8-27b", 1_000_000, 0, cached_tokens=0)
        mixed_cost = ct.cost_for_tokens("qwen/qwen3.8-27b", 1_000_000, 0, cached_tokens=500_000)
        assert mixed_cost == pytest.approx(full_cost * 0.75), (
            "Half-cached request must cost 75 % of the fully non-cached rate"
        )

    def test_groq_free_models_still_zero(self, ct):
        """Free Groq models must remain $0 regardless of caching."""
        for model_id in ("openai/gpt-oss-120b", "openai/gpt-oss-20b"):
            cost = ct.cost_for_tokens(model_id, 1_000_000, 1_000_000, cached_tokens=500_000)
            assert cost == pytest.approx(0.0), (
                f"{model_id} is free-tier; cost must be 0.0 with any caching"
            )

    def test_anthropic_fraction_unchanged(self, ct):
        """Adding Groq fractions must not disturb existing Anthropic fractions."""
        assert ct._cache_read_fraction("claude-sonnet-5") == pytest.approx(0.10)
        assert ct._cache_read_fraction("claude-fable-5-1") == pytest.approx(0.025)
        assert ct._cache_read_fraction("claude-opus-5-5") == pytest.approx(0.05)

    def test_gemini_fraction_unchanged(self, ct):
        assert ct._cache_read_fraction("gemini-2.5-flash") == pytest.approx(0.25)

    def test_deepseek_fraction_unchanged(self, ct):
        assert ct._cache_read_fraction("deepseek-chat") == pytest.approx(0.02)

    def test_unknown_model_fraction_is_one(self, ct):
        """A model with no entry must get fraction 1.0 (no discount assumed)."""
        assert ct._cache_read_fraction("some-unknown-model-xyz") == pytest.approx(1.0)
