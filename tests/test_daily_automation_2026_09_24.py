"""tests/test_daily_automation_2026_09_24.py — Daily automation tests (2026-09-24).

Covers the model catalog updates applied today:

  1. Claude Opus 5.5 (``claude-opus-5-5`` / ``claude-opus-5-5-20260922``).

     Anthropic released Claude Opus 5.5 on 2026-09-22. It matches Fable 5.1 on
     most work, generates output 30% faster, and costs 20% less than Opus 5
     ($4/$20 per MTok vs $5/$25). Context window 1M tokens, max output 128K.

     Changes:
     - Added to ``config/llm/models.yaml`` with full capability flags.
     - Added to ``packages/ai/cost_tracker.py`` at $4.00/$20.00 per MTok.
     - Added as first candidate in the ``anthropic`` and planner/judge preset
       in ``config/models.yaml``.
     - Mirrored first in PROVIDER_CANDIDATES["anthropic"] in
       ``packages/ai/brain_config.py`` (rule 4 — copies must stay reconciled).

  2. CI invariant: routing candidates must be declared in the LLM catalog.

     Added ``TestCandidatesAreDeclaredInLlmCatalog`` — a cross-file consistency
     invariant that catches the class of bug where a model id is added to
     ``config/models.yaml`` candidates without a matching ``config/llm/models.yaml``
     entry (results in silent routing failures for capability-gated decisions).
     Requested in NEXT_ACTION.md 2026-09-23.

Sandbox note: ``packages.ai.brain_config`` requires pydantic and cannot be
imported here.  Tests verify config files directly as text/YAML, which catches
the most common regression (forgetting to update one file when another is changed).
"""
from __future__ import annotations

import ast
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent

_MODEL_ID = "claude-opus-5-5"
_MODEL_ID_VERSIONED = "claude-opus-5-5-20260922"

# Expected pricing: $4 input / $20 output per MTok (stored as per-MTok floats)
_EXPECTED_INPUT = 4.0
_EXPECTED_OUTPUT = 20.0


def _routing_candidates() -> dict[str, list[str]]:
    """Parse config/models.yaml — no pydantic dependency."""
    data = yaml.safe_load((_ROOT / "config" / "models.yaml").read_text())
    result: dict[str, list[str]] = {}
    for pid, pdata in (data.get("providers") or {}).items():
        result[pid] = list(pdata.get("candidates") or [])
    return result


def _routing_presets() -> dict[str, dict[str, str]]:
    """Parse role_presets from config/models.yaml."""
    data = yaml.safe_load((_ROOT / "config" / "models.yaml").read_text())
    result: dict[str, dict[str, str]] = {}
    for pid, pdata in (data.get("providers") or {}).items():
        presets = pdata.get("role_presets") or {}
        if presets:
            result[pid] = dict(presets)
    return result


def _llm_catalog() -> dict[str, dict]:
    """Parse config/llm/models.yaml — capabilities catalog."""
    data = yaml.safe_load((_ROOT / "config" / "llm" / "models.yaml").read_text())
    return dict(data.get("models") or {})


def _cost_tracker_source() -> str:
    return (_ROOT / "packages" / "ai" / "cost_tracker.py").read_text()


def _brain_config_source() -> str:
    return (_ROOT / "packages" / "ai" / "brain_config.py").read_text()


def _get_cost_tracker_price(mid: str) -> tuple[float, float] | None:
    """Extract (input, output) tuple for model id from cost_tracker.py via AST."""
    src = _cost_tracker_source()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == mid:
                    if isinstance(v, ast.Tuple) and len(v.elts) == 2:
                        try:
                            inp = ast.literal_eval(v.elts[0])
                            out = ast.literal_eval(v.elts[1])
                            return (float(inp), float(out))
                        except ValueError:
                            return None
    return None


# ── 1a. Claude Opus 5.5 — catalog entry ────────────────────────────────────

class TestClaudeOpus55CatalogEntry:
    """claude-opus-5-5 must appear in the LLM catalog with correct flags."""

    def test_model_in_catalog(self) -> None:
        catalog = _llm_catalog()
        assert _MODEL_ID in catalog, (
            f"{_MODEL_ID} missing from config/llm/models.yaml"
        )

    def test_versioned_model_in_catalog(self) -> None:
        catalog = _llm_catalog()
        assert _MODEL_ID_VERSIONED in catalog, (
            f"{_MODEL_ID_VERSIONED} missing from config/llm/models.yaml"
        )

    def test_provider_is_anthropic(self) -> None:
        entry = _llm_catalog().get(_MODEL_ID, {})
        assert entry.get("provider") == "anthropic", (
            f"{_MODEL_ID} must declare provider: anthropic"
        )

    def test_context_window_is_1m(self) -> None:
        entry = _llm_catalog().get(_MODEL_ID, {})
        assert entry.get("context_window") == 1048576, (
            f"{_MODEL_ID} context_window must be 1048576 (1M tokens)"
        )

    def test_max_output_tokens(self) -> None:
        entry = _llm_catalog().get(_MODEL_ID, {})
        assert entry.get("max_output_tokens") == 131072, (
            f"{_MODEL_ID} max_output_tokens must be 131072 (128K)"
        )

    def test_supports_tools(self) -> None:
        entry = _llm_catalog().get(_MODEL_ID, {})
        assert entry.get("supports_tools") is True, (
            f"{_MODEL_ID} must declare supports_tools: true"
        )

    def test_supports_images(self) -> None:
        entry = _llm_catalog().get(_MODEL_ID, {})
        assert entry.get("supports_images") is True, (
            f"{_MODEL_ID} must declare supports_images: true"
        )

    def test_supports_reasoning(self) -> None:
        entry = _llm_catalog().get(_MODEL_ID, {})
        assert entry.get("supports_reasoning") is True, (
            f"{_MODEL_ID} must declare supports_reasoning: true"
        )

    def test_input_cost_per_1m(self) -> None:
        entry = _llm_catalog().get(_MODEL_ID, {})
        assert entry.get("input_cost_per_1m") == _EXPECTED_INPUT, (
            f"{_MODEL_ID} input_cost_per_1m must be {_EXPECTED_INPUT} ($4/MTok)"
        )

    def test_output_cost_per_1m(self) -> None:
        entry = _llm_catalog().get(_MODEL_ID, {})
        assert entry.get("output_cost_per_1m") == _EXPECTED_OUTPUT, (
            f"{_MODEL_ID} output_cost_per_1m must be {_EXPECTED_OUTPUT} ($20/MTok)"
        )

    def test_cheaper_than_opus_5(self) -> None:
        catalog = _llm_catalog()
        opus5 = catalog.get("claude-opus-5", {})
        opus55 = catalog.get(_MODEL_ID, {})
        assert opus55.get("input_cost_per_1m", 99) < opus5.get("input_cost_per_1m", 0), (
            f"{_MODEL_ID} must cost less input than claude-opus-5"
        )
        assert opus55.get("output_cost_per_1m", 99) < opus5.get("output_cost_per_1m", 0), (
            f"{_MODEL_ID} must cost less output than claude-opus-5"
        )


# ── 1b. Claude Opus 5.5 — cost_tracker entries ─────────────────────────────

class TestClaudeOpus55CostTracker:
    """cost_tracker.py must contain correct pricing for both model IDs."""

    def test_base_id_in_cost_tracker(self) -> None:
        src = _cost_tracker_source()
        assert f'"{_MODEL_ID}"' in src, (
            f"{_MODEL_ID} missing from packages/ai/cost_tracker.py"
        )

    def test_versioned_id_in_cost_tracker(self) -> None:
        src = _cost_tracker_source()
        assert f'"{_MODEL_ID_VERSIONED}"' in src, (
            f"{_MODEL_ID_VERSIONED} missing from packages/ai/cost_tracker.py"
        )

    def test_base_id_price_is_correct(self) -> None:
        price = _get_cost_tracker_price(_MODEL_ID)
        assert price is not None, f"Could not parse price for {_MODEL_ID}"
        assert price == (_EXPECTED_INPUT, _EXPECTED_OUTPUT), (
            f"{_MODEL_ID} cost_tracker price {price} != expected ({_EXPECTED_INPUT}, {_EXPECTED_OUTPUT})"
        )

    def test_versioned_id_price_is_correct(self) -> None:
        price = _get_cost_tracker_price(_MODEL_ID_VERSIONED)
        assert price is not None, f"Could not parse price for {_MODEL_ID_VERSIONED}"
        assert price == (_EXPECTED_INPUT, _EXPECTED_OUTPUT), (
            f"{_MODEL_ID_VERSIONED} cost_tracker price {price} != expected ({_EXPECTED_INPUT}, {_EXPECTED_OUTPUT})"
        )

    def test_both_ids_match_each_other(self) -> None:
        """Base and versioned IDs must have identical pricing."""
        p1 = _get_cost_tracker_price(_MODEL_ID)
        p2 = _get_cost_tracker_price(_MODEL_ID_VERSIONED)
        assert p1 == p2, (
            f"Price mismatch: {_MODEL_ID}={p1} vs {_MODEL_ID_VERSIONED}={p2}"
        )


# ── 1c. Claude Opus 5.5 — routing candidates ───────────────────────────────

class TestClaudeOpus55RoutingCandidates:
    """claude-opus-5-5 must be the first Anthropic routing candidate."""

    def test_in_anthropic_candidates(self) -> None:
        cands = _routing_candidates().get("anthropic", [])
        assert _MODEL_ID in cands, (
            f"{_MODEL_ID} missing from anthropic candidates in config/models.yaml"
        )

    def test_is_first_anthropic_candidate(self) -> None:
        cands = _routing_candidates().get("anthropic", [])
        assert cands and cands[0] == _MODEL_ID, (
            f"{_MODEL_ID} must be the first anthropic candidate; got {cands[0] if cands else 'empty'}"
        )

    def test_opus5_still_in_candidates(self) -> None:
        """Adding Opus 5.5 must not remove Opus 5 from the fallback chain."""
        cands = _routing_candidates().get("anthropic", [])
        assert "claude-opus-5" in cands, (
            "claude-opus-5 must remain in anthropic candidates as a fallback"
        )


# ── 1d. Claude Opus 5.5 — role presets ─────────────────────────────────────

class TestClaudeOpus55RolePresets:
    """Anthropic role_presets planner/judge must now point to claude-opus-5-5."""

    def test_anthropic_planner_preset(self) -> None:
        presets = _routing_presets().get("anthropic", {})
        assert presets.get("planner") == _MODEL_ID, (
            f"anthropic planner preset must be {_MODEL_ID}, got {presets.get('planner')}"
        )

    def test_anthropic_judge_preset(self) -> None:
        presets = _routing_presets().get("anthropic", {})
        assert presets.get("judge") == _MODEL_ID, (
            f"anthropic judge preset must be {_MODEL_ID}, got {presets.get('judge')}"
        )

    def test_anthropic_executor_preset_unchanged(self) -> None:
        """Executor should still use Sonnet 5 — only planner/judge upgraded."""
        presets = _routing_presets().get("anthropic", {})
        assert presets.get("executor") == "claude-sonnet-5", (
            f"anthropic executor preset must remain claude-sonnet-5"
        )


# ── 1e. Claude Opus 5.5 — brain_config.py mirror (rule 4) ──────────────────

class TestClaudeOpus55BrainConfigMirror:
    """brain_config.py must declare claude-opus-5-5 as the first Anthropic candidate."""

    def test_in_brain_config_anthropic(self) -> None:
        src = _brain_config_source()
        assert f'"{_MODEL_ID}"' in src, (
            f"{_MODEL_ID} missing from packages/ai/brain_config.py PROVIDER_CANDIDATES"
        )

    def test_first_anthropic_candidate_in_brain_config(self) -> None:
        """Verify claude-opus-5-5 appears before claude-opus-5 in PROVIDER_CANDIDATES["anthropic"]."""
        import re
        src = _brain_config_source()
        # Extract the anthropic block from PROVIDER_CANDIDATES (list literal after '"anthropic": [')
        m = re.search(r'"anthropic":\s*\[([^\]]+)\]', src, re.DOTALL)
        assert m is not None, 'PROVIDER_CANDIDATES["anthropic"] block not found in brain_config.py'
        block = m.group(1)
        idx_55 = block.find(f'"{_MODEL_ID}"')
        idx_5 = block.find('"claude-opus-5"')
        assert idx_55 != -1, f"{_MODEL_ID} not found in anthropic PROVIDER_CANDIDATES block"
        assert idx_5 != -1, "claude-opus-5 not found in anthropic PROVIDER_CANDIDATES block"
        assert idx_55 < idx_5, (
            f"{_MODEL_ID} must appear before claude-opus-5 in PROVIDER_CANDIDATES[anthropic] "
            f"(found at block offsets {idx_55} vs {idx_5})"
        )


# ── 2. CI invariant: all routing candidates must be in LLM catalog ──────────

class TestCandidatesAreDeclaredInLlmCatalog:
    """Routing candidates for direct API providers must be in the LLM catalog.

    This invariant catches the class of bug where a model is added to the routing
    candidate list but its capability flags (supports_tools, context_window, …)
    are never declared — causing silent routing misbehaviour.

    Excluded providers:
    - ``tokenin``, ``openrouter``, ``omniroute``, ``aerolink``: relay/gateway
      providers that proxy arbitrary model ids; their candidates are not owned
      by this repo and may include ids not in the catalog by design.
    - ``ollama``: local/dynamic model list; ids depend on what the operator has
      pulled and are not catalogued individually.

    Only direct API providers (anthropic, google, groq, cerebras, nvidia,
    deepseek, zhipu, moonshot, mistral, together, dashscope, openai) are checked.
    """

    # Relay/gateway/local providers whose candidates we do NOT own.
    _RELAY_PROVIDERS = frozenset({
        "tokenin", "openrouter", "omniroute", "aerolink", "ollama",
    })

    def test_direct_api_candidates_in_llm_catalog(self) -> None:
        catalog = _llm_catalog()
        candidates_map = _routing_candidates()
        missing: list[str] = []
        for provider, cands in candidates_map.items():
            if provider in self._RELAY_PROVIDERS:
                continue
            for mid in cands:
                if mid not in catalog:
                    missing.append(f"{provider}/{mid}")
        assert not missing, (
            "Model ids in routing candidates (direct API providers) are missing "
            "from config/llm/models.yaml:\n"
            + "\n".join(f"  {m}" for m in sorted(missing))
            + "\nAdd an entry to config/llm/models.yaml for each, or move the "
            "provider to _RELAY_PROVIDERS if it proxies dynamic model ids."
        )
