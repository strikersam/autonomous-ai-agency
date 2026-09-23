"""tests/test_daily_automation_2026_09_22.py — Daily automation tests (2026-09-22).

Covers the model catalog updates applied today:

  1. DeepSeek V4.1-Flash on NVIDIA NIM (``deepseek-ai/deepseek-v4.1-flash``).

     Research confirmed DeepSeek V4.1-Flash was added to the NVIDIA NIM catalogue
     on 2026-09-22. This is the same 552B MoE model already present as
     ``deepseek-flash`` on the DeepSeek direct API, now served via NIM with no
     per-token cost. Added to ``config/llm/models.yaml`` (conservative
     ``supports_tools: false`` until probed on this account), to the NVIDIA NIM
     ``candidates`` list in ``config/models.yaml`` (placed last as an unprobed
     fallback), and to ``packages/ai/cost_tracker.py`` at $0.00/$0.00.

  2. Kimi K2 pricing correction ($0.00 → $1.00/$3.00 per MTok).

     ``moonshotai/kimi-k2-instruct`` was priced at $0.00 in both
     ``packages/ai/cost_tracker.py`` and ``config/llm/models.yaml``. Research
     confirmed Groq charges $1.00 input / $3.00 output per million tokens on its
     self-serve plan — the most expensive self-serve model on Groq as of Sep 2026.
     Silent billing under-count corrected.

  3. Gemini Omni 1.1 Flash catalog entry (``gemini-omni-1.1-flash``).

     Google's video generation / editing model GA'd September 2026. Primary use
     case is video (extension, interpolation, resolution control 360p–4K) — it is
     NOT a standard text/code chat model and is therefore NOT added to the Google
     routing candidates. Catalog entry added for completeness with
     ``supports_tools: false`` and a clear comment. Pricing not yet published;
     tracked at $0.00 until confirmed.

Sandbox note: ``packages.ai.brain_config`` requires pydantic and cannot be
imported here.  Tests verify config files directly as text/YAML, which catches
the most common regression (forgetting to update one file when another is changed).
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


def _llm_catalog() -> dict[str, dict]:
    """Parse config/llm/models.yaml — capabilities catalog."""
    data = yaml.safe_load((_ROOT / "config" / "llm" / "models.yaml").read_text())
    return dict(data.get("models") or {})


def _cost_tracker_source() -> str:
    return (_ROOT / "packages" / "ai" / "cost_tracker.py").read_text()


# ── 1. deepseek-ai/deepseek-v4.1-flash: NVIDIA NIM ─────────────────────────

class TestDeepSeekNIMEntry:
    """deepseek-ai/deepseek-v4.1-flash must be in NIM catalog and candidates."""

    def test_nim_deepseek_flash_in_llm_catalog(self) -> None:
        catalog = _llm_catalog()
        assert "deepseek-ai/deepseek-v4.1-flash" in catalog, (
            "deepseek-ai/deepseek-v4.1-flash missing from config/llm/models.yaml"
        )

    def test_nim_deepseek_flash_provider_is_nvidia(self) -> None:
        catalog = _llm_catalog()
        entry = catalog.get("deepseek-ai/deepseek-v4.1-flash", {})
        assert entry.get("provider") == "nvidia", (
            "deepseek-ai/deepseek-v4.1-flash should declare provider: nvidia"
        )

    def test_nim_deepseek_flash_conservative_tools_flag(self) -> None:
        """Not yet probed on this NIM account — must default conservative."""
        catalog = _llm_catalog()
        entry = catalog.get("deepseek-ai/deepseek-v4.1-flash", {})
        assert entry.get("supports_tools") is False, (
            "deepseek-ai/deepseek-v4.1-flash: supports_tools must remain false "
            "until live-probed on this NIM account"
        )

    def test_nim_deepseek_flash_in_nvidia_candidates(self) -> None:
        cands = _routing_candidates().get("nvidia", [])
        assert "deepseek-ai/deepseek-v4.1-flash" in cands, (
            "deepseek-ai/deepseek-v4.1-flash missing from NVIDIA NIM candidates"
        )

    def test_nim_deepseek_flash_is_last_nvidia_candidate(self) -> None:
        """Unprobed model must sit at the end of the failover chain."""
        cands = _routing_candidates().get("nvidia", [])
        assert cands and cands[-1] == "deepseek-ai/deepseek-v4.1-flash", (
            f"deepseek-ai/deepseek-v4.1-flash should be the last NVIDIA candidate "
            f"(unprobed), got last={cands[-1] if cands else 'empty'}"
        )

    def test_nim_deepseek_flash_primary_candidate_unchanged(self) -> None:
        """Adding a new fallback must not displace the primary."""
        cands = _routing_candidates().get("nvidia", [])
        assert cands and cands[0] == "nvidia/nemotron-3-super-120b-a12b", (
            f"Primary NVIDIA candidate must still be nemotron-3-super-120b-a12b, "
            f"got {cands[0] if cands else 'empty'}"
        )

    def test_nim_deepseek_flash_supports_images(self) -> None:
        catalog = _llm_catalog()
        entry = catalog.get("deepseek-ai/deepseek-v4.1-flash", {})
        assert entry.get("supports_images") is True, (
            "deepseek-ai/deepseek-v4.1-flash must declare supports_images: true "
            "(same multimodal model as deepseek-flash)"
        )

    def test_nim_deepseek_flash_context_window(self) -> None:
        catalog = _llm_catalog()
        entry = catalog.get("deepseek-ai/deepseek-v4.1-flash", {})
        cw = entry.get("context_window")
        assert cw == 1000000, (
            f"deepseek-ai/deepseek-v4.1-flash context_window should be 1_000_000, got {cw}"
        )

    def test_nim_deepseek_flash_free_in_cost_tracker(self) -> None:
        src = _cost_tracker_source()
        assert '"deepseek-ai/deepseek-v4.1-flash"' in src, (
            "deepseek-ai/deepseek-v4.1-flash missing from packages/ai/cost_tracker.py"
        )
        # Free NIM model — must not be priced (would inflate billing dashboards)
        import ast
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values):
                    if isinstance(k, ast.Constant) and k.value == "deepseek-ai/deepseek-v4.1-flash":
                        if isinstance(v, ast.Tuple) and len(v.elts) == 2:
                            inp = ast.literal_eval(v.elts[0])
                            out = ast.literal_eval(v.elts[1])
                            assert inp == 0.0 and out == 0.0, (
                                f"deepseek-ai/deepseek-v4.1-flash is free on NIM; "
                                f"cost_tracker shows ({inp}, {out})"
                            )


# ── 2. Kimi K2 pricing correction ───────────────────────────────────────────

class TestKimiK2PricingCorrection:
    """moonshotai/kimi-k2-instruct must now be priced at $1.00/$3.00 per MTok."""

    def test_kimi_k2_cost_tracker_input_price(self) -> None:
        import ast
        src = _cost_tracker_source()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values):
                    if (isinstance(k, ast.Constant)
                            and k.value == "moonshotai/kimi-k2-instruct"):
                        if isinstance(v, ast.Tuple) and len(v.elts) == 2:
                            inp = ast.literal_eval(v.elts[0])
                            assert inp == 1.0, (
                                f"Kimi K2 input price should be 1.0 ($/MTok), got {inp}. "
                                f"Groq charges $1.00/MTok on self-serve (2026-09-22)."
                            )
                            return
        raise AssertionError(
            "moonshotai/kimi-k2-instruct not found in cost_tracker.py"
        )

    def test_kimi_k2_cost_tracker_output_price(self) -> None:
        import ast
        src = _cost_tracker_source()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values):
                    if (isinstance(k, ast.Constant)
                            and k.value == "moonshotai/kimi-k2-instruct"):
                        if isinstance(v, ast.Tuple) and len(v.elts) == 2:
                            out = ast.literal_eval(v.elts[1])
                            assert out == 3.0, (
                                f"Kimi K2 output price should be 3.0 ($/MTok), got {out}. "
                                f"Groq charges $3.00/MTok output on self-serve (2026-09-22)."
                            )
                            return
        raise AssertionError(
            "moonshotai/kimi-k2-instruct not found in cost_tracker.py"
        )

    def test_kimi_k2_catalog_input_cost_updated(self) -> None:
        catalog = _llm_catalog()
        entry = catalog.get("moonshotai/kimi-k2-instruct", {})
        inp = entry.get("input_cost_per_1m")
        assert inp == 1.0, (
            f"moonshotai/kimi-k2-instruct input_cost_per_1m should be 1.0, got {inp}"
        )

    def test_kimi_k2_catalog_output_cost_updated(self) -> None:
        catalog = _llm_catalog()
        entry = catalog.get("moonshotai/kimi-k2-instruct", {})
        out = entry.get("output_cost_per_1m")
        assert out == 3.0, (
            f"moonshotai/kimi-k2-instruct output_cost_per_1m should be 3.0, got {out}"
        )

    def test_kimi_k2_capabilities_unchanged(self) -> None:
        """Price correction must not alter capability flags."""
        catalog = _llm_catalog()
        entry = catalog.get("moonshotai/kimi-k2-instruct", {})
        assert entry.get("supports_tools") is True, "Kimi K2 supports_tools must still be true"
        assert entry.get("context_window") == 1000000, "Kimi K2 context_window must still be 1M"

    def test_kimi_k2_not_in_groq_candidates(self) -> None:
        """Kimi K2 is known-dead on Groq self-serve (HTTP 404); must not be a candidate.

        See tests/test_brain_migration_writes_a_live_model.py DEAD_GROQ denylist.
        """
        cands = _routing_candidates().get("groq", [])
        assert "moonshotai/kimi-k2-instruct" not in cands, (
            "moonshotai/kimi-k2-instruct should NOT be in Groq candidates "
            "(known-dead per DEAD_GROQ denylist)"
        )


# ── 3. gemini-omni-1.1-flash catalog entry ──────────────────────────────────

class TestGeminiOmniCatalogEntry:
    """gemini-omni-1.1-flash must be in the catalog but NOT in routing candidates."""

    def test_gemini_omni_in_llm_catalog(self) -> None:
        catalog = _llm_catalog()
        assert "gemini-omni-1.1-flash" in catalog, (
            "gemini-omni-1.1-flash missing from config/llm/models.yaml"
        )

    def test_gemini_omni_is_not_a_routing_candidate(self) -> None:
        """Video generation model must not appear in any provider's candidate list."""
        all_candidates: list[str] = []
        for cands in _routing_candidates().values():
            all_candidates.extend(cands)
        assert "gemini-omni-1.1-flash" not in all_candidates, (
            "gemini-omni-1.1-flash should NOT be a routing candidate — it is a "
            "video generation model incompatible with the chat/tool-call routing path"
        )

    def test_gemini_omni_supports_tools_false(self) -> None:
        """Video generation models do not support structured tool calling."""
        catalog = _llm_catalog()
        entry = catalog.get("gemini-omni-1.1-flash", {})
        assert entry.get("supports_tools") is False, (
            "gemini-omni-1.1-flash must declare supports_tools: false "
            "(video generation model)"
        )

    def test_gemini_omni_provider_is_google(self) -> None:
        catalog = _llm_catalog()
        entry = catalog.get("gemini-omni-1.1-flash", {})
        assert entry.get("provider") == "google", (
            "gemini-omni-1.1-flash must declare provider: google"
        )

    def test_gemini_omni_in_cost_tracker(self) -> None:
        src = _cost_tracker_source()
        assert '"gemini-omni-1.1-flash"' in src, (
            "gemini-omni-1.1-flash missing from packages/ai/cost_tracker.py"
        )

    def test_existing_google_candidates_preserved(self) -> None:
        """Adding a catalog-only entry must not disturb the active routing chain."""
        cands = _routing_candidates().get("google", [])
        for mid in ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3.8-flash"]:
            assert mid in cands, f"{mid} was unexpectedly removed from Google candidates"
