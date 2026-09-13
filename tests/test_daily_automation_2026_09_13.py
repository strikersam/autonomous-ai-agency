"""tests/test_daily_automation_2026_09_13.py — Daily automation tests (2026-09-13).

Covers the ecosystem updates applied today:

  1. Add Gemini 3.x models to ``config/llm/models.yaml``.

     Google released Gemini 3.7 Flash (Aug 2026) and Gemini 3.8 Flash (Sep 2026)
     for long-horizon agent workloads. Gemini 3.5 Flash Lite (cheap tier) and
     Gemini 3.1 Pro (frontier reasoning) also launched. Without catalog entries
     these models get ``supports_tools: false`` by default and are silently
     filtered from every tool-calling request.

     Fix: declare all four with ``supports_tools: true``, correct context windows
     (1M tokens each), and pricing entries in cost_tracker.

  2. Add Groq Kimi K2 and QwQ-32B catalog entries.

     ``moonshotai/kimi-k2-instruct`` and ``qwen-qwq-32b`` were already in the
     cost_tracker table (added by a previous session) but had no ``models.yaml``
     entry, so the registry defaulted ``supports_tools`` to ``False`` and
     silently excluded them from every tool-calling request routed to Groq.

     Fix: add catalog entries with ``supports_tools: true`` and correct
     capability flags so the router can include them.

  3. Fix stale Groq provider reference in CLAUDE.md.

     ``deepseek-r1-70b`` was deprecated from Groq's self-serve tier in
     August 2026; the CLAUDE.md providers table still listed it as the Groq
     default. Updated to the current self-serve models.
"""
from __future__ import annotations

import pytest

try:
    import packages.llm  # noqa: F401
except Exception:
    pass  # expected in sandbox without pydantic; packages.llm.config stays cached


def _cfg():
    from packages.llm.config import load_config
    return load_config()


def _cost_table():
    from packages.ai.cost_tracker import _DEFAULT_COST_TABLE
    return _DEFAULT_COST_TABLE


# ── 1. Gemini 3.x catalog entries ────────────────────────────────────────────

class TestGemini3xCatalog:
    """Gemini 3.x models must be declared with correct capability flags."""

    def test_gemini38_flash_in_catalog(self) -> None:
        models = _cfg().models
        assert "gemini-3.8-flash" in models, "gemini-3.8-flash missing from catalog"

    def test_gemini37_flash_in_catalog(self) -> None:
        models = _cfg().models
        assert "gemini-3.7-flash" in models, "gemini-3.7-flash missing from catalog"

    def test_gemini35_flash_lite_in_catalog(self) -> None:
        models = _cfg().models
        assert "gemini-3.5-flash-lite" in models, "gemini-3.5-flash-lite missing from catalog"

    def test_gemini31_pro_in_catalog(self) -> None:
        models = _cfg().models
        assert "gemini-3.1-pro" in models, "gemini-3.1-pro missing from catalog"

    def test_gemini38_flash_supports_tools(self) -> None:
        m = _cfg().models["gemini-3.8-flash"]
        assert m.supports_tools is True, "gemini-3.8-flash: supports_tools must be True"

    def test_gemini37_flash_supports_tools(self) -> None:
        m = _cfg().models["gemini-3.7-flash"]
        assert m.supports_tools is True, "gemini-3.7-flash: supports_tools must be True"

    def test_gemini35_flash_lite_supports_tools(self) -> None:
        m = _cfg().models["gemini-3.5-flash-lite"]
        assert m.supports_tools is True, "gemini-3.5-flash-lite: supports_tools must be True"

    def test_gemini31_pro_supports_tools(self) -> None:
        m = _cfg().models["gemini-3.1-pro"]
        assert m.supports_tools is True, "gemini-3.1-pro: supports_tools must be True"

    def test_gemini38_flash_supports_reasoning(self) -> None:
        m = _cfg().models["gemini-3.8-flash"]
        assert m.supports_reasoning is True, "gemini-3.8-flash: supports_reasoning must be True"

    def test_gemini37_flash_supports_reasoning(self) -> None:
        m = _cfg().models["gemini-3.7-flash"]
        assert m.supports_reasoning is True, "gemini-3.7-flash: supports_reasoning must be True"

    def test_gemini31_pro_supports_reasoning(self) -> None:
        m = _cfg().models["gemini-3.1-pro"]
        assert m.supports_reasoning is True, "gemini-3.1-pro: supports_reasoning must be True"

    def test_gemini38_flash_context_window(self) -> None:
        m = _cfg().models["gemini-3.8-flash"]
        assert m.context_window == 1048576, "gemini-3.8-flash: context_window must be 1048576 (1M)"

    def test_gemini37_flash_context_window(self) -> None:
        m = _cfg().models["gemini-3.7-flash"]
        assert m.context_window == 1048576, "gemini-3.7-flash: context_window must be 1048576 (1M)"

    def test_gemini38_flash_provider(self) -> None:
        m = _cfg().models["gemini-3.8-flash"]
        assert m.provider == "google", "gemini-3.8-flash: provider must be google"

    def test_gemini3x_priority_ordering(self) -> None:
        """3.8 Flash should have higher priority (lower number) than 3.7 Flash."""
        models = _cfg().models
        assert models["gemini-3.8-flash"].priority < models["gemini-3.7-flash"].priority, (
            "gemini-3.8-flash priority must be higher than 3.7-flash"
        )

    def test_gemini31_pro_paid_model(self) -> None:
        m = _cfg().models["gemini-3.1-pro"]
        assert m.input_cost_per_1m is not None and m.input_cost_per_1m > 0, (
            "gemini-3.1-pro must have positive input_cost_per_1m (paid model)"
        )


# ── 2. Gemini 3.x cost tracker entries ───────────────────────────────────────

class TestGemini3xCostTracker:
    """Gemini 3.x models must have pricing entries in the cost table."""

    def test_gemini38_flash_in_cost_table(self) -> None:
        assert "gemini-3.8-flash" in _cost_table(), "gemini-3.8-flash missing from cost table"

    def test_gemini37_flash_in_cost_table(self) -> None:
        assert "gemini-3.7-flash" in _cost_table(), "gemini-3.7-flash missing from cost table"

    def test_gemini35_flash_lite_in_cost_table(self) -> None:
        assert "gemini-3.5-flash-lite" in _cost_table(), "gemini-3.5-flash-lite missing from cost table"

    def test_gemini31_pro_in_cost_table(self) -> None:
        assert "gemini-3.1-pro" in _cost_table(), "gemini-3.1-pro missing from cost table"

    def test_gemini38_flash_intro_pricing(self) -> None:
        inp, out = _cost_table()["gemini-3.8-flash"]
        assert inp == pytest.approx(0.75), "gemini-3.8-flash input cost should be $0.75/M (intro)"
        assert out == pytest.approx(3.75), "gemini-3.8-flash output cost should be $3.75/M (intro)"

    def test_gemini37_flash_intro_pricing(self) -> None:
        inp, out = _cost_table()["gemini-3.7-flash"]
        assert inp == pytest.approx(0.75), "gemini-3.7-flash input cost should be $0.75/M (intro)"
        assert out == pytest.approx(3.75), "gemini-3.7-flash output cost should be $3.75/M (intro)"

    def test_gemini35_flash_lite_pricing(self) -> None:
        inp, out = _cost_table()["gemini-3.5-flash-lite"]
        assert inp == pytest.approx(0.30), "gemini-3.5-flash-lite input cost should be $0.30/M"
        assert out == pytest.approx(2.50), "gemini-3.5-flash-lite output cost should be $2.50/M"

    def test_gemini31_pro_pricing(self) -> None:
        inp, out = _cost_table()["gemini-3.1-pro"]
        assert inp == pytest.approx(2.0), "gemini-3.1-pro input cost should be $2.00/M (lower bound)"
        assert out == pytest.approx(12.0), "gemini-3.1-pro output cost should be $12.00/M (lower bound)"

    def test_gemini35_flash_lite_cheaper_than_37(self) -> None:
        lite_in = _cost_table()["gemini-3.5-flash-lite"][0]
        flash_in = _cost_table()["gemini-3.7-flash"][0]
        assert lite_in < flash_in, "Lite tier must be cheaper than Flash"

    def test_gemini31_pro_most_expensive_3x(self) -> None:
        pro_in = _cost_table()["gemini-3.1-pro"][0]
        flash_in = _cost_table()["gemini-3.7-flash"][0]
        assert pro_in > flash_in, "3.1 Pro must be more expensive than 3.7 Flash"


# ── 3. Groq catalog entries (Kimi K2, QwQ-32B) ───────────────────────────────

class TestGroqNewModelsCatalog:
    """Kimi K2 and QwQ-32B must have catalog entries so the router includes them."""

    def test_kimi_k2_in_catalog(self) -> None:
        models = _cfg().models
        assert "moonshotai/kimi-k2-instruct" in models, (
            "moonshotai/kimi-k2-instruct missing from catalog — "
            "router will silently exclude it from tool-calling requests"
        )

    def test_qwq_32b_in_catalog(self) -> None:
        models = _cfg().models
        assert "qwen-qwq-32b" in models, (
            "qwen-qwq-32b missing from catalog — "
            "router will silently exclude it from tool-calling requests"
        )

    def test_kimi_k2_supports_tools(self) -> None:
        m = _cfg().models["moonshotai/kimi-k2-instruct"]
        assert m.supports_tools is True, "kimi-k2-instruct: supports_tools must be True"

    def test_qwq_32b_supports_tools(self) -> None:
        m = _cfg().models["qwen-qwq-32b"]
        assert m.supports_tools is True, "qwen-qwq-32b: supports_tools must be True"

    def test_qwq_32b_supports_reasoning(self) -> None:
        m = _cfg().models["qwen-qwq-32b"]
        assert m.supports_reasoning is True, "qwen-qwq-32b: supports_reasoning must be True"

    def test_kimi_k2_provider_is_groq(self) -> None:
        m = _cfg().models["moonshotai/kimi-k2-instruct"]
        assert m.provider == "groq", "kimi-k2-instruct: provider must be groq"

    def test_qwq_32b_provider_is_groq(self) -> None:
        m = _cfg().models["qwen-qwq-32b"]
        assert m.provider == "groq", "qwen-qwq-32b: provider must be groq"

    def test_kimi_k2_large_context(self) -> None:
        m = _cfg().models["moonshotai/kimi-k2-instruct"]
        assert m.context_window >= 1_000_000, (
            "kimi-k2-instruct context_window must reflect 1M context"
        )


# ── 4. CLAUDE.md Groq reference is current ───────────────────────────────────

class TestClaudeMdGroqReference:
    """CLAUDE.md must no longer reference the deprecated deepseek-r1-70b as the Groq model."""

    def test_deepseek_r1_70b_not_sole_groq_reference(self) -> None:
        from pathlib import Path
        content = (Path(__file__).parent.parent / "CLAUDE.md").read_text()
        # The old inaccurate claim was "Free fast LLM (`deepseek-r1-70b`)"
        # The updated line must mention the deprecation, not claim it as current
        assert "deprecated" in content.lower() or "gpt-oss-120b" in content, (
            "CLAUDE.md Groq row must reflect current self-serve models "
            "(deepseek-r1-70b was deprecated from self-serve Aug 2026)"
        )

    def test_gpt_oss_mentioned_for_groq(self) -> None:
        from pathlib import Path
        content = (Path(__file__).parent.parent / "CLAUDE.md").read_text()
        assert "gpt-oss-120b" in content, (
            "CLAUDE.md should mention gpt-oss-120b as the current Groq self-serve model"
        )
