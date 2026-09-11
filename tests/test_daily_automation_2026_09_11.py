"""tests/test_daily_automation_2026_09_11.py — Daily automation tests (2026-09-11).

Covers the ecosystem updates applied today:

  1. Add ``gemini-2.5-pro`` to ``config/llm/models.yaml``.

     ``gemini-2.5-pro`` is referenced in the "google" BRAIN_PRESET in
     ``packages/ai/brain_config.py`` as the planner and judge model.  Because
     it had no entry in the catalog, ``packages/llm/config.py::ModelConfig``
     defaulted ``supports_tools`` to ``False``; ``packages/llm/registry.py``
     line 161 then silently filtered it from every tool-calling request,
     so the entire Google brain preset's planner/judge was unreachable when
     any tool-calling agent ran.

     Fix: declare it with ``supports_tools: true``, ``supports_reasoning: true``
     (native thinking capability), 1M context, and conservative 8 192-token
     output floor.

  2. Add cost entries for Google Gemini models to ``packages/ai/cost_tracker.py``.

     ``gemini-2.5-flash`` and ``gemini-2.0-flash`` were in the YAML catalog but
     absent from the cost table — any call would have logged $0.00 regardless of
     actual usage.  ``gemini-2.5-pro`` is a paid model; tracking at the lower
     bound ($1.25/$10.0 per MTok for ≤200 K-token requests; $2.50/$15.0 above
     that threshold which the router does not model).
"""
from __future__ import annotations

import pytest

# packages/llm/__init__.py imports packages.llm.config at line ~20 (success)
# then packages.llm.router at line ~28 (fails without pydantic in this sandbox).
# The first import attempt propagates the pydantic error, but leaves
# packages.llm.config cached in sys.modules. Pre-loading here silences the
# error and ensures all _cfg() calls below can reach the cached module.
try:
    import packages.llm  # noqa: F401
except Exception:
    pass  # expected in sandbox without pydantic; packages.llm.config stays cached


# ── helpers ──────────────────────────────────────────────────────────────────

def _cfg():
    from packages.llm.config import load_config
    return load_config()


def _cost_table():
    from packages.ai.cost_tracker import _DEFAULT_COST_TABLE
    return _DEFAULT_COST_TABLE


# ── 1. gemini-2.5-pro catalog entry ──────────────────────────────────────────

class TestGemini25ProCatalog:
    """gemini-2.5-pro must be declared in models.yaml with tool support."""

    def test_gemini25pro_is_in_catalog(self) -> None:
        models = _cfg().models
        assert "gemini-2.5-pro" in models, (
            "gemini-2.5-pro is missing from config/llm/models.yaml; "
            "the Google BRAIN_PRESET planner/judge is silently excluded from "
            "all tool-calling requests"
        )

    def test_gemini25pro_provider(self) -> None:
        m = _cfg().models["gemini-2.5-pro"]
        assert m.provider == "google", (
            f"expected provider 'google', got {m.provider!r}"
        )

    def test_gemini25pro_supports_tools(self) -> None:
        m = _cfg().models["gemini-2.5-pro"]
        assert m.supports_tools is True, (
            "gemini-2.5-pro must have supports_tools: true — without it the "
            "router filters it from every tool-calling request (registry.py:161)"
        )

    def test_gemini25pro_supports_function_calling(self) -> None:
        m = _cfg().models["gemini-2.5-pro"]
        assert m.supports_function_calling is True

    def test_gemini25pro_supports_images(self) -> None:
        m = _cfg().models["gemini-2.5-pro"]
        assert m.supports_images is True

    def test_gemini25pro_supports_reasoning(self) -> None:
        m = _cfg().models["gemini-2.5-pro"]
        assert m.supports_reasoning is True, (
            "gemini-2.5-pro supports native thinking; marking supports_reasoning "
            "allows the router to route reasoning-required requests to it"
        )

    def test_gemini25pro_context_window(self) -> None:
        m = _cfg().models["gemini-2.5-pro"]
        assert m.context_window >= 1_000_000, (
            f"gemini-2.5-pro context window should be ≥ 1M, got {m.context_window}"
        )

    def test_gemini25pro_has_input_cost(self) -> None:
        m = _cfg().models["gemini-2.5-pro"]
        assert m.input_cost_per_1m > 0.0, (
            "gemini-2.5-pro is a paid model; input_cost_per_1m must be > 0"
        )

    def test_gemini25pro_has_output_cost(self) -> None:
        m = _cfg().models["gemini-2.5-pro"]
        assert m.output_cost_per_1m > 0.0, (
            "gemini-2.5-pro is a paid model; output_cost_per_1m must be > 0"
        )

    def test_gemini25pro_lower_priority_than_flash(self) -> None:
        """Pro should be tried after Flash (lower priority number = higher preference)."""
        cfg = _cfg()
        flash = cfg.models["gemini-2.5-flash"]
        pro = cfg.models["gemini-2.5-pro"]
        assert flash.priority < pro.priority, (
            f"gemini-2.5-flash priority {flash.priority} should be lower than "
            f"gemini-2.5-pro priority {pro.priority} (Flash is the free default)"
        )

    def test_gemini25pro_not_filtered_for_tool_calls(self) -> None:
        """The router must not exclude gemini-2.5-pro from tool-calling requests."""
        m = _cfg().models["gemini-2.5-pro"]
        # mirrors the filter at packages/llm/registry.py:161
        require_tools = True
        is_filtered = require_tools and not (m.supports_tools or m.supports_function_calling)
        assert not is_filtered, (
            "gemini-2.5-pro is filtered from tool-calling requests — "
            "check that supports_tools: true in the yaml is being loaded"
        )


# ── 2. Cost-tracker entries for Gemini ───────────────────────────────────────

class TestGeminiCostTrackerEntries:
    """Gemini models must have entries in the cost table."""

    def test_gemini25flash_in_cost_table(self) -> None:
        assert "gemini-2.5-flash" in _cost_table(), (
            "gemini-2.5-flash is in models.yaml but absent from cost_tracker; "
            "all calls would log $0.00 ignoring actual free-tier limits"
        )

    def test_gemini20flash_in_cost_table(self) -> None:
        assert "gemini-2.0-flash" in _cost_table(), (
            "gemini-2.0-flash is in models.yaml but absent from cost_tracker"
        )

    def test_gemini25pro_in_cost_table(self) -> None:
        assert "gemini-2.5-pro" in _cost_table(), (
            "gemini-2.5-pro must be tracked in cost_tracker — it is a paid model"
        )

    def test_gemini25pro_input_cost_is_positive(self) -> None:
        inp, _out = _cost_table()["gemini-2.5-pro"]
        assert inp > 0.0, f"gemini-2.5-pro input cost should be > 0, got {inp}"

    def test_gemini25pro_output_cost_is_positive(self) -> None:
        _inp, out = _cost_table()["gemini-2.5-pro"]
        assert out > 0.0, f"gemini-2.5-pro output cost should be > 0, got {out}"

    def test_gemini25flash_cost_is_zero(self) -> None:
        """Flash is on the free tier in this deployment — tracked as $0."""
        inp, out = _cost_table()["gemini-2.5-flash"]
        assert inp == 0.0 and out == 0.0, (
            f"gemini-2.5-flash is the free-tier default; expected (0.0, 0.0), "
            f"got ({inp}, {out})"
        )

    def test_gemini20flash_cost_is_zero(self) -> None:
        """2.0 Flash fallback is on the free tier."""
        inp, out = _cost_table()["gemini-2.0-flash"]
        assert inp == 0.0 and out == 0.0


# ── 3. brain_config BRAIN_PRESET uses declared google models ─────────────────

_skip_without_pydantic = pytest.mark.skipif(
    __import__("importlib.util", fromlist=["find_spec"]).find_spec("pydantic") is None,
    reason="pydantic required for brain_config; skipped in lightweight sandbox",
)


class TestGoogleBrainPresetConsistency:
    """Every model in the 'google' BRAIN_PRESET must be declared in models.yaml."""

    @_skip_without_pydantic
    def test_google_preset_models_are_all_declared(self) -> None:
        from packages.ai.brain_config import BRAIN_PRESETS

        preset = BRAIN_PRESETS.get("google", {})
        assert preset, "the 'google' BRAIN_PRESET must exist"

        cfg = _cfg()
        for role, model_id in preset.items():
            assert model_id in cfg.models, (
                f"BRAIN_PRESETS['google'][{role!r}] = {model_id!r} is not "
                f"declared in config/llm/models.yaml — it will get "
                f"supports_tools: false by default, silently breaking the role"
            )

    @_skip_without_pydantic
    def test_google_preset_planner_supports_tools(self) -> None:
        from packages.ai.brain_config import BRAIN_PRESETS

        planner_id = BRAIN_PRESETS["google"]["planner"]
        m = _cfg().models[planner_id]
        assert m.supports_tools is True, (
            f"BRAIN_PRESETS['google']['planner'] = {planner_id!r} has "
            f"supports_tools: false — it cannot serve tool-calling planner requests"
        )

    @_skip_without_pydantic
    def test_google_preset_judge_supports_tools(self) -> None:
        from packages.ai.brain_config import BRAIN_PRESETS

        judge_id = BRAIN_PRESETS["google"].get("judge", BRAIN_PRESETS["google"]["planner"])
        m = _cfg().models[judge_id]
        assert m.supports_tools is True, (
            f"BRAIN_PRESETS['google']['judge'] = {judge_id!r} has "
            f"supports_tools: false — it cannot serve tool-calling judge requests"
        )
