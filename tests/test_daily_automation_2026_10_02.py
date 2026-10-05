"""tests/test_daily_automation_2026_10_02.py — Daily automation 2026-10-02.

Changes shipped today:
- **GPT-OSS-Safeguard-20B added to Groq** (``openai/gpt-oss-safeguard-20b``).
  OpenAI released two safety-reasoning models on 2025-10-29:
  ``gpt-oss-safeguard-20b`` and ``gpt-oss-safeguard-120b``, fine-tuned from
  the corresponding gpt-oss base models and purpose-built for safety
  classification. Groq provides day-zero access to the 20B variant at 1000+
  t/s. Added to ``config/llm/models.yaml`` as a declared-but-unrouted model
  (priority 99; not in any provider's candidates — use via X-Model-Override).
  Source: console.groq.com/docs/model/openai/gpt-oss-safeguard-20b.

- **GPT-OSS-Safeguard cost table entries** added to
  ``packages/ai/cost_tracker.py`` for both the 20B and 120B variants.  The
  20B is billed at $0.075/$0.30 per MTok (Groq, same as the base gpt-oss-20b
  price) and the 120B at $0.15/$0.60 per MTok (Amazon Bedrock / Opper; not
  on Groq self-serve as of 2026-10-02).  Entries enable cost attribution if
  either model is reached via an explicitly configured provider.
  Source: futureagi.com/llm-cost-calculator, 2026-10-02.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ct():
    """Return the cost_tracker module."""
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_02",
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
    )


@pytest.fixture(scope="module")
def models_yaml():
    return yaml.safe_load(
        (REPO_ROOT / "config" / "models.yaml").read_text()
    )


# ---------------------------------------------------------------------------
# 1. Cost table entries
# ---------------------------------------------------------------------------

class TestSafeguardCostEntries:
    """Both safeguard model ids must appear in the cost table."""

    def test_safeguard_20b_input_cost(self, ct):
        cost = ct.cost_for_tokens("openai/gpt-oss-safeguard-20b", 1_000_000, 0)
        assert cost == pytest.approx(0.075), (
            "safeguard-20b input cost should be $0.075/MTok"
        )

    def test_safeguard_20b_output_cost(self, ct):
        cost = ct.cost_for_tokens("openai/gpt-oss-safeguard-20b", 0, 1_000_000)
        assert cost == pytest.approx(0.30)

    def test_safeguard_120b_input_cost(self, ct):
        cost = ct.cost_for_tokens("openai/gpt-oss-safeguard-120b", 1_000_000, 0)
        assert cost == pytest.approx(0.15), (
            "safeguard-120b input cost should be $0.15/MTok"
        )

    def test_safeguard_120b_output_cost(self, ct):
        cost = ct.cost_for_tokens("openai/gpt-oss-safeguard-120b", 0, 1_000_000)
        assert cost == pytest.approx(0.60)

    def test_safeguard_20b_is_more_expensive_than_base_gpt_oss_20b(self, ct):
        """Safeguard fine-tune is priced above the free base model."""
        base = ct.cost_for_tokens("openai/gpt-oss-20b", 1_000_000, 0)
        safe = ct.cost_for_tokens("openai/gpt-oss-safeguard-20b", 1_000_000, 0)
        assert safe > base, (
            f"safeguard-20b (${safe:.4f}) should cost more than free base (${base:.4f})"
        )

    def test_safeguard_120b_is_more_expensive_than_safeguard_20b(self, ct):
        s20 = ct.cost_for_tokens("openai/gpt-oss-safeguard-20b", 1_000_000, 0)
        s120 = ct.cost_for_tokens("openai/gpt-oss-safeguard-120b", 1_000_000, 0)
        assert s120 > s20, (
            f"safeguard-120b (${s120:.4f}) should cost more than safeguard-20b (${s20:.4f})"
        )

    def test_safeguard_120b_is_cheaper_than_base_gpt_oss_120b_cerebras(self, ct):
        """gpt-oss-120b on Cerebras is $0.85/MTok; safeguard is $0.15/MTok."""
        base = ct.cost_for_tokens("gpt-oss-120b", 1_000_000, 0)
        safe = ct.cost_for_tokens("openai/gpt-oss-safeguard-120b", 1_000_000, 0)
        assert safe < base, (
            f"safeguard-120b (${safe:.4f}) should be cheaper than Cerebras gpt-oss-120b (${base:.4f})"
        )


# ---------------------------------------------------------------------------
# 2. llm/models.yaml declaration
# ---------------------------------------------------------------------------

class TestSafeguard20bModelYaml:
    """openai/gpt-oss-safeguard-20b must be declared in llm/models.yaml
    with the correct provider, context window, and conservative capabilities."""

    def test_model_declared(self, llm_models):
        assert "openai/gpt-oss-safeguard-20b" in llm_models.get("models", {}), (
            "openai/gpt-oss-safeguard-20b should be declared in config/llm/models.yaml"
        )

    def test_provider_is_groq(self, llm_models):
        entry = llm_models["models"]["openai/gpt-oss-safeguard-20b"]
        assert entry.get("provider") == "groq"

    def test_context_window(self, llm_models):
        entry = llm_models["models"]["openai/gpt-oss-safeguard-20b"]
        assert entry.get("context_window") == 131072

    def test_max_output_tokens(self, llm_models):
        entry = llm_models["models"]["openai/gpt-oss-safeguard-20b"]
        assert entry.get("max_output_tokens") == 65536

    def test_supports_tools_is_false(self, llm_models):
        """Not probed — declared conservatively false."""
        entry = llm_models["models"]["openai/gpt-oss-safeguard-20b"]
        assert entry.get("supports_tools") is False

    def test_supports_streaming(self, llm_models):
        entry = llm_models["models"]["openai/gpt-oss-safeguard-20b"]
        assert entry.get("supports_streaming") is True

    def test_priority_is_high_number(self, llm_models):
        """Priority >= 90 keeps it out of normal routing."""
        entry = llm_models["models"]["openai/gpt-oss-safeguard-20b"]
        assert entry.get("priority", 0) >= 90, (
            "safeguard model should have a high priority number to stay out of normal routing"
        )


# ---------------------------------------------------------------------------
# 3. Not in routing candidates
# ---------------------------------------------------------------------------

class TestSafeguardNotInRoutingCandidates:
    """Neither safeguard model should appear in config/models.yaml candidates.
    They are safety classifiers, not general-purpose chat models."""

    def _all_candidates(self, models_yaml) -> list[str]:
        candidates: list[str] = []
        for p_data in models_yaml.get("providers", {}).values():
            candidates.extend(p_data.get("candidates", []))
        return candidates

    def test_safeguard_20b_not_in_candidates(self, models_yaml):
        candidates = self._all_candidates(models_yaml)
        assert "openai/gpt-oss-safeguard-20b" not in candidates, (
            "safeguard-20b should not be in provider routing candidates"
        )

    def test_safeguard_120b_not_in_candidates(self, models_yaml):
        candidates = self._all_candidates(models_yaml)
        assert "openai/gpt-oss-safeguard-120b" not in candidates, (
            "safeguard-120b should not be in provider routing candidates"
        )
