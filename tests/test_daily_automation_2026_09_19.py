"""tests/test_daily_automation_2026_09_19.py — Daily automation tests (2026-09-19).

Covers the model catalog updates applied today:

  1. NVIDIA NIM: ``mistralai/mistral-nemotron`` and ``nvidia/nemotron-3-ultra-550b-a55b``

     Both model IDs appear in ``config/models.yaml``'s ``nvidia`` candidates list
     but had no ``config/llm/models.yaml`` entry.  Without an entry,
     ``packages/llm/registry.py`` assigns ``supports_tools: false`` and silently
     drops the model from every tool-calling request.

     Fix: add conservative catalog entries (``supports_tools: false`` — neither
     has been live-probed for tool calls on this account) so routing can at least
     attempt them for non-tool requests.

  2. Together AI: ``Llama-3.3-70B-Instruct-Turbo-Free`` and
     ``Mixtral-8x7B-Instruct-v0.1-Free``

     Both are in the ``together`` candidates list and were missing from the
     llm catalog.  LLaMA 3.3 70B supports tool calling (declared ``true``);
     Mixtral 8×7B v0.1 predates standardised tool support (declared ``false``).

  3. Google: ``gemini-1.5-flash`` and ``gemini-1.5-pro``

     Both appear in the ``google`` candidates list as fallbacks behind the 2.5/3.x
     models and had no llm catalog entry.  Both support tool calling per Google
     documentation; both are now declared with accurate context windows.

  4. Mistral API: ``mistral-large-latest``, ``mistral-small-latest``,
     ``codestral-latest``, ``mistral-nemo``

     All four are in the ``mistral`` candidates list and all were missing from the
     llm catalog.  All four support function calling per Mistral documentation.
     Cost tracking entries added for each.

  5. Cost tracking: pricing rows added for all new paid/free models.

Sandbox note: ``packages.ai.brain_config`` requires pydantic and cannot be
imported here.  Tests verify the YAML directly — the same approach used in
tests/test_daily_automation_2026_09_18.py.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent


def _llm_catalog() -> dict[str, dict]:
    """Parse config/llm/models.yaml models dict."""
    data = yaml.safe_load((_ROOT / "config" / "llm" / "models.yaml").read_text())
    return dict(data.get("models") or {})


def _routing_candidates() -> dict[str, list[str]]:
    """Parse config/models.yaml candidates per provider."""
    data = yaml.safe_load((_ROOT / "config" / "models.yaml").read_text())
    result: dict[str, list[str]] = {}
    for pid, pdata in (data.get("providers") or {}).items():
        result[pid] = list(pdata.get("candidates") or [])
    return result


def _cost_table_src() -> str:
    """Read cost_tracker.py source so we can grep for model ids."""
    return (_ROOT / "packages" / "ai" / "cost_tracker.py").read_text()


# ── NVIDIA NIM additions ──────────────────────────────────────────────────


class TestNvidiaNemotronEntries:
    """mistralai/mistral-nemotron and nvidia/nemotron-3-ultra-550b-a55b now have
    llm/models.yaml catalog entries."""

    def test_mistral_nemotron_in_nvidia_candidates(self):
        assert "mistralai/mistral-nemotron" in _routing_candidates().get("nvidia", [])

    def test_nemotron_ultra_in_nvidia_candidates(self):
        assert "nvidia/nemotron-3-ultra-550b-a55b" in _routing_candidates().get("nvidia", [])

    def test_mistral_nemotron_has_catalog_entry(self):
        catalog = _llm_catalog()
        assert "mistralai/mistral-nemotron" in catalog, (
            "mistralai/mistral-nemotron missing from config/llm/models.yaml; "
            "without an entry it defaults to supports_tools:false and is "
            "silently excluded from tool-calling requests"
        )

    def test_nemotron_ultra_has_catalog_entry(self):
        catalog = _llm_catalog()
        assert "nvidia/nemotron-3-ultra-550b-a55b" in catalog

    def test_mistral_nemotron_provider_is_nvidia(self):
        entry = _llm_catalog()["mistralai/mistral-nemotron"]
        assert entry.get("provider") == "nvidia"

    def test_nemotron_ultra_provider_is_nvidia(self):
        entry = _llm_catalog()["nvidia/nemotron-3-ultra-550b-a55b"]
        assert entry.get("provider") == "nvidia"


# ── Together AI additions ─────────────────────────────────────────────────


class TestTogetherAiEntries:
    """LLaMA 3.3 70B Turbo and Mixtral 8×7B v0.1 now have catalog entries."""

    LLAMA = "Llama-3.3-70B-Instruct-Turbo-Free"
    MIXTRAL = "Mixtral-8x7B-Instruct-v0.1-Free"

    def test_llama_in_together_candidates(self):
        assert self.LLAMA in _routing_candidates().get("together", [])

    def test_mixtral_in_together_candidates(self):
        assert self.MIXTRAL in _routing_candidates().get("together", [])

    def test_llama_has_catalog_entry(self):
        assert self.LLAMA in _llm_catalog()

    def test_mixtral_has_catalog_entry(self):
        assert self.MIXTRAL in _llm_catalog()

    def test_llama_provider_is_together(self):
        assert _llm_catalog()[self.LLAMA]["provider"] == "together"

    def test_mixtral_provider_is_together(self):
        assert _llm_catalog()[self.MIXTRAL]["provider"] == "together"

    def test_llama_supports_tools(self):
        assert _llm_catalog()[self.LLAMA].get("supports_tools") is True

    def test_mixtral_does_not_claim_tools(self):
        # v0.1 predates standardised tool support — conservative false.
        assert _llm_catalog()[self.MIXTRAL].get("supports_tools") is False

    def test_llama_context_window(self):
        assert _llm_catalog()[self.LLAMA].get("context_window") == 131072

    def test_mixtral_context_window(self):
        assert _llm_catalog()[self.MIXTRAL].get("context_window") == 32768

    def test_both_in_cost_tracker_as_free(self):
        src = _cost_table_src()
        assert self.LLAMA in src
        assert self.MIXTRAL in src
        # Both are free-tier — verify (0.0, 0.0) appears adjacent to each id
        for mid in (self.LLAMA, self.MIXTRAL):
            idx = src.index(f'"{mid}"')
            snippet = src[idx: idx + 60]
            assert "0.0, 0.0" in snippet, (
                f"{mid} should be a free-tier entry (0.0, 0.0) in cost_tracker"
            )


# ── Google Gemini 1.5 additions ───────────────────────────────────────────


class TestGemini15Entries:
    """gemini-1.5-flash and gemini-1.5-pro now have catalog entries."""

    def test_gemini_15_flash_in_google_candidates(self):
        assert "gemini-1.5-flash" in _routing_candidates().get("google", [])

    def test_gemini_15_pro_in_google_candidates(self):
        assert "gemini-1.5-pro" in _routing_candidates().get("google", [])

    def test_gemini_15_flash_has_catalog_entry(self):
        assert "gemini-1.5-flash" in _llm_catalog()

    def test_gemini_15_pro_has_catalog_entry(self):
        assert "gemini-1.5-pro" in _llm_catalog()

    def test_gemini_15_flash_provider(self):
        assert _llm_catalog()["gemini-1.5-flash"]["provider"] == "google"

    def test_gemini_15_pro_provider(self):
        assert _llm_catalog()["gemini-1.5-pro"]["provider"] == "google"

    def test_gemini_15_flash_supports_tools(self):
        assert _llm_catalog()["gemini-1.5-flash"].get("supports_tools") is True

    def test_gemini_15_pro_supports_tools(self):
        assert _llm_catalog()["gemini-1.5-pro"].get("supports_tools") is True

    def test_gemini_15_flash_context_window(self):
        assert _llm_catalog()["gemini-1.5-flash"]["context_window"] == 1048576

    def test_gemini_15_pro_context_window(self):
        # 2M tokens
        assert _llm_catalog()["gemini-1.5-pro"]["context_window"] == 2097152

    def test_gemini_15_flash_in_cost_tracker(self):
        assert '"gemini-1.5-flash"' in _cost_table_src()

    def test_gemini_15_pro_in_cost_tracker(self):
        assert '"gemini-1.5-pro"' in _cost_table_src()


# ── Mistral API additions ─────────────────────────────────────────────────


class TestMistralApiEntries:
    """All four Mistral API candidates now have catalog entries and cost rows."""

    MODELS = [
        "mistral-large-latest",
        "mistral-small-latest",
        "codestral-latest",
        "mistral-nemo",
    ]

    def test_mistral_candidates_are_present(self):
        cands = _routing_candidates().get("mistral", [])
        for mid in self.MODELS:
            assert mid in cands, f"{mid} missing from mistral candidates"

    def test_all_have_catalog_entries(self):
        catalog = _llm_catalog()
        for mid in self.MODELS:
            assert mid in catalog, (
                f"{mid} missing from config/llm/models.yaml — "
                "defaults to supports_tools:false without an entry"
            )

    def test_all_have_provider_mistral(self):
        catalog = _llm_catalog()
        for mid in self.MODELS:
            assert catalog[mid].get("provider") == "mistral", (
                f"{mid} should have provider:mistral"
            )

    def test_all_support_tools_except_reasoner(self):
        catalog = _llm_catalog()
        for mid in self.MODELS:
            assert catalog[mid].get("supports_tools") is True, (
                f"{mid} should declare supports_tools:true"
            )

    def test_context_windows_declared(self):
        catalog = _llm_catalog()
        assert catalog["mistral-large-latest"]["context_window"] == 131072
        assert catalog["mistral-small-latest"]["context_window"] == 131072
        assert catalog["codestral-latest"]["context_window"] == 262144
        assert catalog["mistral-nemo"]["context_window"] == 131072

    def test_all_have_cost_entries(self):
        src = _cost_table_src()
        for mid in self.MODELS:
            assert f'"{mid}"' in src, f"{mid} missing from cost_tracker.py"

    def test_large_is_most_expensive(self):
        """mistral-large should cost more than mistral-small."""
        src = _cost_table_src()
        # extract (input, output) per model
        import re

        def _price(model_id: str) -> tuple[float, float]:
            pattern = rf'"{re.escape(model_id)}"\s*:\s*\(([0-9.]+),\s*([0-9.]+)\)'
            m = re.search(pattern, src)
            assert m, f"Could not parse price for {model_id}"
            return float(m.group(1)), float(m.group(2))

        large_in, large_out = _price("mistral-large-latest")
        small_in, small_out = _price("mistral-small-latest")
        assert large_in > small_in, "large should cost more than small (input)"
        assert large_out > small_out, "large should cost more than small (output)"

    def test_codestral_has_largest_context(self):
        catalog = _llm_catalog()
        assert catalog["codestral-latest"]["context_window"] > catalog["mistral-large-latest"]["context_window"]


# ── Catalog total count ───────────────────────────────────────────────────


def test_catalog_consistency_script_passes():
    """The check_model_catalog_consistency.py gate reports no drift."""
    import subprocess
    # nosec - constant argv, list form (no shell). Bare `nosec` rather than the
    # `nosec B603,B607` form used elsewhere in this repo (e.g. agent/loop.py):
    # bandit 1.9.4's NOSEC_COMMENT_TESTS regex only registers the *last* code
    # in a comma-separated nosec list, so `# nosec B603,B607` suppresses B607
    # but leaves B603 firing (see tests/test_changelog_check_workflow.py).
    result = subprocess.run(  # nosec
        ["python", "scripts/check_model_catalog_consistency.py"],
        capture_output=True,
        text=True,
        cwd=str(_ROOT),
    )
    assert result.returncode == 0, (
        f"check_model_catalog_consistency.py failed:\n{result.stdout}\n{result.stderr}"
    )
    assert "CATALOGUE OK" in result.stdout


def test_declared_id_count_increased():
    """Catalog should have more entries than before today's run (was 36 direct keys)."""
    catalog = _llm_catalog()
    assert len(catalog) >= 46, (
        f"Expected at least 46 direct model keys after today's additions (+10), "
        f"got {len(catalog)}"
    )
