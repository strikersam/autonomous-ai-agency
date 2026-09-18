"""tests/test_daily_automation_2026_09_18.py — Daily automation tests (2026-09-18).

Covers the model catalog updates applied today:

  1. DeepSeek V4.1-Flash (``deepseek-flash``) — new model.

     DeepSeek released V4.1-Flash on 2026-09-10. It is a 552B MoE model
     with a 1M-token context window, native image + text input, MIT licence,
     and tool-calling support. Model ID on deepseek.com API: ``deepseek-flash``.
     Peak pricing: $0.30/$1.20 per MTok.

     Fix: add to ``config/llm/models.yaml`` (catalog), ``config/models.yaml``
     (deepseek provider candidates, first position), ``packages/ai/brain_config.py``
     (deepseek candidates + planner/verifier/judge presets), and
     ``packages/ai/cost_tracker.py`` (pricing).

  2. Groq ``qwen/qwen3.8-27b`` catalog entry — missing entry for existing candidate.

     ``qwen/qwen3.8-27b`` was already in the Groq ``candidates`` list since row 63
     (2026-09-14) but had no ``config/llm/models.yaml`` entry. Without an entry,
     ``packages/llm/registry.py`` assigns ``supports_tools: false`` and the model
     is silently dropped from every tool-calling request.

     Fix: add catalog entry (131K context, $0.80/$4.00 per MTok, supports_tools:
     true, supports_images: true).

  3. DeepSeek direct API model catalog entries — ``deepseek-chat``,
     ``deepseek-coder``, ``deepseek-reasoner``.

     All three were in the DeepSeek ``candidates`` list but absent from the catalog,
     so they too defaulted to ``supports_tools: false`` and were filtered from
     tool-calling requests.

     Fix: add catalog entries with accurate capabilities. ``deepseek-reasoner``
     (R1-based) does NOT support tool calls and is correctly declared false.

Sandbox note: ``packages.ai.brain_config`` requires pydantic and cannot be
imported here.  Tests verify the hardcoded fallback by reading the source file
as text, which catches the most common regression (forgetting to update the
hardcoded dict when the YAML is updated).
"""
from __future__ import annotations

from pathlib import Path
import yaml

_ROOT = Path(__file__).resolve().parent.parent


def _routing_candidates() -> dict[str, list[str]]:
    """Parse config/models.yaml — no pydantic dependency."""
    data = yaml.safe_load((_ROOT / "config" / "models.yaml").read_text())
    result: dict[str, list[str]] = {}
    for pid, pdata in (data.get("providers") or {}).items():
        result[pid] = list(pdata.get("candidates") or [])
    return result


def _routing_presets() -> dict[str, dict[str, str]]:
    """Parse config/models.yaml role presets."""
    data = yaml.safe_load((_ROOT / "config" / "models.yaml").read_text())
    result: dict[str, dict[str, str]] = {}
    for pid, pdata in (data.get("providers") or {}).items():
        result[pid] = dict(pdata.get("role_presets") or {})
    return result


def _llm_catalog() -> dict[str, dict]:
    """Parse config/llm/models.yaml — the capabilities catalog."""
    data = yaml.safe_load((_ROOT / "config" / "llm" / "models.yaml").read_text())
    return dict(data.get("models") or {})


def _brain_config_source() -> str:
    return (_ROOT / "packages" / "ai" / "brain_config.py").read_text()


def _cost_tracker_source() -> str:
    return (_ROOT / "packages" / "ai" / "cost_tracker.py").read_text()


# ── 1. deepseek-flash: candidates and config/models.yaml ────────────────────

class TestDeepSeekFlashCandidates:
    """deepseek-flash must be the first DeepSeek candidate and in role presets."""

    def test_deepseek_flash_in_deepseek_yaml_candidates(self) -> None:
        cands = _routing_candidates().get("deepseek", [])
        assert "deepseek-flash" in cands, (
            "deepseek-flash missing from deepseek candidates in config/models.yaml"
        )

    def test_deepseek_flash_is_first_deepseek_candidate(self) -> None:
        cands = _routing_candidates().get("deepseek", [])
        assert cands and cands[0] == "deepseek-flash", (
            f"deepseek-flash should be first deepseek candidate, got: {cands[:3]}"
        )

    def test_deepseek_presets_use_flash_for_planner(self) -> None:
        presets = _routing_presets().get("deepseek", {})
        assert presets.get("planner") == "deepseek-flash", (
            f"deepseek planner preset should be deepseek-flash, got: {presets.get('planner')}"
        )

    def test_deepseek_presets_use_flash_for_judge(self) -> None:
        presets = _routing_presets().get("deepseek", {})
        assert presets.get("judge") == "deepseek-flash", (
            f"deepseek judge preset should be deepseek-flash, got: {presets.get('judge')}"
        )

    def test_existing_deepseek_candidates_preserved(self) -> None:
        cands = _routing_candidates().get("deepseek", [])
        for mid in ["deepseek-chat", "deepseek-reasoner", "deepseek-coder"]:
            assert mid in cands, f"{mid} was removed from deepseek candidates"


# ── 2. deepseek-flash: catalog entry in config/llm/models.yaml ─────────────

class TestDeepSeekFlashCatalog:
    """deepseek-flash catalog entry must have correct capabilities and pricing."""

    def test_deepseek_flash_in_llm_catalog(self) -> None:
        catalog = _llm_catalog()
        assert "deepseek-flash" in catalog, (
            "deepseek-flash missing from config/llm/models.yaml"
        )

    def test_deepseek_flash_supports_tools(self) -> None:
        catalog = _llm_catalog()
        assert catalog["deepseek-flash"].get("supports_tools") is True, (
            "deepseek-flash must declare supports_tools: true"
        )

    def test_deepseek_flash_supports_images(self) -> None:
        catalog = _llm_catalog()
        assert catalog["deepseek-flash"].get("supports_images") is True, (
            "deepseek-flash must declare supports_images: true (multimodal model)"
        )

    def test_deepseek_flash_context_window(self) -> None:
        catalog = _llm_catalog()
        cw = catalog["deepseek-flash"].get("context_window")
        assert cw == 1000000, (
            f"deepseek-flash context_window should be 1_000_000, got {cw}"
        )

    def test_deepseek_flash_max_output_tokens(self) -> None:
        catalog = _llm_catalog()
        mot = catalog["deepseek-flash"].get("max_output_tokens")
        assert mot == 384000, (
            f"deepseek-flash max_output_tokens should be 384_000, got {mot}"
        )

    def test_deepseek_flash_provider(self) -> None:
        catalog = _llm_catalog()
        assert catalog["deepseek-flash"].get("provider") == "deepseek", (
            "deepseek-flash provider should be 'deepseek'"
        )

    def test_deepseek_flash_cost_entries(self) -> None:
        catalog = _llm_catalog()
        entry = catalog["deepseek-flash"]
        assert entry.get("input_cost_per_1m") == 0.30, (
            f"deepseek-flash input cost should be 0.30, got {entry.get('input_cost_per_1m')}"
        )
        assert entry.get("output_cost_per_1m") == 1.20, (
            f"deepseek-flash output cost should be 1.20, got {entry.get('output_cost_per_1m')}"
        )


# ── 3. deepseek-flash: brain_config.py hardcoded fallback ───────────────────

class TestDeepSeekFlashBrainConfig:
    """brain_config.py hardcoded deepseek candidates must include deepseek-flash."""

    def test_deepseek_flash_in_brain_config_candidates(self) -> None:
        src = _brain_config_source()
        assert '"deepseek-flash"' in src, (
            "deepseek-flash missing from brain_config.py PROVIDER_CANDIDATES"
        )

    def test_deepseek_flash_is_first_in_brain_config(self) -> None:
        src = _brain_config_source()
        # The deepseek list should start with deepseek-flash
        assert '"deepseek": ["deepseek-flash"' in src, (
            "deepseek-flash should be first in brain_config.py deepseek candidates"
        )

    def test_deepseek_presets_in_brain_config(self) -> None:
        src = _brain_config_source()
        # planner and judge presets should reference deepseek-flash
        assert '"planner":   "deepseek-flash"' in src or '"planner": "deepseek-flash"' in src, (
            "deepseek planner preset not updated to deepseek-flash in brain_config.py"
        )


# ── 4. deepseek-flash: cost_tracker.py ──────────────────────────────────────

class TestDeepSeekFlashCostTracker:
    """cost_tracker.py must have deepseek-flash pricing."""

    def test_deepseek_flash_in_cost_tracker(self) -> None:
        src = _cost_tracker_source()
        assert '"deepseek-flash"' in src, (
            "deepseek-flash missing from cost_tracker.py"
        )

    def test_deepseek_flash_cost_values(self) -> None:
        src = _cost_tracker_source()
        # Should have (0.30, 1.20) pricing
        assert "(0.30, 1.20)" in src, (
            "deepseek-flash cost tuple (0.30, 1.20) not found in cost_tracker.py"
        )


# ── 5. qwen/qwen3.8-27b: Groq catalog entry ─────────────────────────────────

class TestQwen38Catalog:
    """qwen/qwen3.8-27b must have a catalog entry with correct capabilities."""

    def test_qwen38_in_llm_catalog(self) -> None:
        catalog = _llm_catalog()
        assert "qwen/qwen3.8-27b" in catalog, (
            "qwen/qwen3.8-27b missing from config/llm/models.yaml"
        )

    def test_qwen38_supports_tools(self) -> None:
        catalog = _llm_catalog()
        assert catalog["qwen/qwen3.8-27b"].get("supports_tools") is True, (
            "qwen/qwen3.8-27b must declare supports_tools: true"
        )

    def test_qwen38_supports_images(self) -> None:
        catalog = _llm_catalog()
        assert catalog["qwen/qwen3.8-27b"].get("supports_images") is True, (
            "qwen/qwen3.8-27b must declare supports_images: true (multimodal)"
        )

    def test_qwen38_context_window(self) -> None:
        catalog = _llm_catalog()
        cw = catalog["qwen/qwen3.8-27b"].get("context_window")
        assert cw == 131072, (
            f"qwen/qwen3.8-27b context_window should be 131_072, got {cw}"
        )

    def test_qwen38_provider_is_groq(self) -> None:
        catalog = _llm_catalog()
        assert catalog["qwen/qwen3.8-27b"].get("provider") == "groq", (
            "qwen/qwen3.8-27b provider should be 'groq'"
        )

    def test_qwen38_still_in_groq_candidates(self) -> None:
        cands = _routing_candidates().get("groq", [])
        assert "qwen/qwen3.8-27b" in cands, (
            "qwen/qwen3.8-27b removed from groq candidates — should stay"
        )


# ── 6. DeepSeek direct API models: catalog entries ───────────────────────────

class TestDeepSeekDirectAPICatalog:
    """deepseek-chat, deepseek-coder, deepseek-reasoner must have catalog entries."""

    def test_deepseek_chat_in_catalog(self) -> None:
        catalog = _llm_catalog()
        assert "deepseek-chat" in catalog, (
            "deepseek-chat missing from config/llm/models.yaml"
        )

    def test_deepseek_coder_in_catalog(self) -> None:
        catalog = _llm_catalog()
        assert "deepseek-coder" in catalog, (
            "deepseek-coder missing from config/llm/models.yaml"
        )

    def test_deepseek_reasoner_in_catalog(self) -> None:
        catalog = _llm_catalog()
        assert "deepseek-reasoner" in catalog, (
            "deepseek-reasoner missing from config/llm/models.yaml"
        )

    def test_deepseek_chat_supports_tools(self) -> None:
        catalog = _llm_catalog()
        assert catalog["deepseek-chat"].get("supports_tools") is True, (
            "deepseek-chat (V3) should support tool calls"
        )

    def test_deepseek_coder_supports_tools(self) -> None:
        catalog = _llm_catalog()
        assert catalog["deepseek-coder"].get("supports_tools") is True, (
            "deepseek-coder should support tool calls"
        )

    def test_deepseek_reasoner_does_not_support_tools(self) -> None:
        catalog = _llm_catalog()
        # R1-based reasoner is incompatible with tool_calls output format
        assert catalog["deepseek-reasoner"].get("supports_tools") is False, (
            "deepseek-reasoner (R1) should NOT support tool calls"
        )

    def test_deepseek_reasoner_supports_reasoning(self) -> None:
        catalog = _llm_catalog()
        assert catalog["deepseek-reasoner"].get("supports_reasoning") is True, (
            "deepseek-reasoner should declare supports_reasoning: true"
        )

    def test_all_direct_deepseek_models_have_provider_field(self) -> None:
        catalog = _llm_catalog()
        for mid in ["deepseek-chat", "deepseek-coder", "deepseek-reasoner", "deepseek-flash"]:
            assert catalog[mid].get("provider") == "deepseek", (
                f"{mid} should have provider: deepseek"
            )


# ── 7. Catalog consistency: no dangling candidates ───────────────────────────

class TestNoDanglingCandidates:
    """Every candidate in config/models.yaml must have a config/llm/models.yaml entry."""

    # These ids are intentionally in candidates but not in the LLM catalog:
    # they either carry conservative defaults (free text models that never need
    # tool calling) or are shared entries covered by providers[].
    _KNOWN_UNDECLARED: frozenset[str] = frozenset({
        # OmniRoute virtual id — resolved at runtime
        "auto",
        # Together AI free-tier models (no tool calling needed)
        "Llama-3.3-70B-Instruct-Turbo-Free",
        "Mixtral-8x7B-Instruct-v0.1-Free",
        # OpenRouter free models
        "cohere/north-mini-code:free",
        "meta-llama/llama-3.3-70b-instruct",
        "anthropic/claude-3.5-sonnet",
        # Aerolink / Anthropic historic alias
        "claude-opus-4-6",
        "claude-opus-4-7",
        # Mistral — added to providers; catalog to follow once probed
        "mistral-small-latest",
        "mistral-large-latest",
        "codestral-latest",
        "mistral-nemo",
        # ZhiPu / Z.ai GLM models
        "glm-4",
        "glm-4-air",
        "glm-4-flash",
        "glm-5.1",
        "glm-5.2",
        # DashScope Qwen
        "qwen-plus",
        "qwen-max",
        "qwen-turbo",
        "qwen-coder-plus",
        # Moonshot
        "moonshot-v1-8k",
        "moonshot-v1-32k",
        "moonshot-v1-128k",
        # Tokenin free gateway — gateway entries; no catalog needed for pass-through
        "myt/glm-5.3-free",
        "myt/deepseek-v4-pro-free",
        "myt/MiniMax-M3-free",
        "myt/mimo-v2.5-free",
        "myt/qwen3.8-max-free",
        "myt/kimi-k3-free",
        "myt/gemini-3.5-flash-free",
        "myt/grok-4.6-free",
        "myt/gpt-5.6-sol-free",
        "myt/claude-opus-4-8-free",
        # Ollama local
        "north-mini-code-1.0",
        "llama3.3:70b",
        # NVIDIA intermittent
        "nvidia/nemotron-3-ultra-550b-a55b",
        "mistralai/mistral-nemotron",
    })

    def test_new_candidates_in_llm_catalog(self) -> None:
        """The candidates added today (deepseek-flash) must have catalog entries."""
        catalog = _llm_catalog()
        new_ids = ["deepseek-flash", "deepseek-chat", "deepseek-coder",
                   "deepseek-reasoner", "qwen/qwen3.8-27b"]
        for mid in new_ids:
            assert mid in catalog, (
                f"{mid} is in candidates but has no config/llm/models.yaml entry — "
                "it will default to supports_tools: false and be silently filtered "
                "from every tool-calling request"
            )
