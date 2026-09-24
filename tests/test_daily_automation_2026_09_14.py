"""tests/test_daily_automation_2026_09_14.py — Daily automation tests (2026-09-14).

Covers the routing-candidate updates applied today:

  1. Anthropic / Aerolink routing candidates: add claude-fable-5-1.

     ``claude-fable-5-1`` (Fable 5.1) is the current Fable revision. It was
     already in ``config/llm/models.yaml`` and ``cost_tracker.py`` but missing
     from the ``candidates`` list for both the ``anthropic`` and ``aerolink``
     providers, so the failover chain could not fall back to it.

     Fix: add ``claude-fable-5-1`` after ``claude-fable-5`` in both providers'
     ``candidates`` lists, and in the hardcoded brain_config fallback.

  2. Google routing candidates: add Gemini 3.x models.

     PR #1485 added ``gemini-3.8-flash``, ``gemini-3.7-flash``,
     ``gemini-3.5-flash-lite``, and ``gemini-3.1-pro`` to
     ``config/llm/models.yaml``. None were in the Google provider's
     ``candidates`` list, so the failover chain could not reach them.

     Fix: add all four after the existing Gemini 2.x entries in
     ``config/models.yaml`` (placed after proven 2.5 entries until live-probed).

Sandbox note: ``packages.ai.brain_config`` requires pydantic and cannot be
imported here.  Tests that verify the hardcoded fallback in brain_config.py
read the *source file as text* instead, which is sufficient to catch the most
common regression (forgetting to update the hardcoded dict when the YAML is
updated).
"""
from __future__ import annotations

from pathlib import Path
import yaml

try:
    import packages.llm  # noqa: F401
except Exception:
    pass  # expected in sandbox without full deps; packages.llm.config stays cached

_ROOT = Path(__file__).resolve().parent.parent


def _routing_candidates() -> dict[str, list[str]]:
    """Parse config/models.yaml directly — no pydantic dependency."""
    data = yaml.safe_load((_ROOT / "config" / "models.yaml").read_text())
    result: dict[str, list[str]] = {}
    for pid, pdata in (data.get("providers") or {}).items():
        result[pid] = list(pdata.get("candidates") or [])
    return result


def _brain_config_source() -> str:
    return (_ROOT / "packages" / "ai" / "brain_config.py").read_text()


def _llm_models():
    from packages.llm.config import load_config
    return load_config().models


# ── 1. Anthropic / Aerolink candidates: Fable 5.1 ───────────────────────────

class TestFable51CandidatesUpdated:
    """claude-fable-5-1 must be in the anthropic and aerolink failover candidates."""

    def test_fable51_in_anthropic_yaml_candidates(self) -> None:
        cands = _routing_candidates().get("anthropic", [])
        assert "claude-fable-5-1" in cands, (
            "claude-fable-5-1 missing from anthropic candidates in config/models.yaml"
        )

    def test_fable51_in_aerolink_yaml_candidates(self) -> None:
        cands = _routing_candidates().get("aerolink", [])
        assert "claude-fable-5-1" in cands, (
            "claude-fable-5-1 missing from aerolink candidates in config/models.yaml"
        )

    def test_fable51_in_brain_config_anthropic(self) -> None:
        src = _brain_config_source()
        assert '"claude-fable-5-1"' in src, (
            "claude-fable-5-1 missing from hardcoded PROVIDER_CANDIDATES in brain_config.py"
        )

    def test_fable5_before_fable51_anthropic(self) -> None:
        """Fable 5 stays before Fable 5.1 (5 is the proven entry)."""
        cands = _routing_candidates().get("anthropic", [])
        f5_idx = cands.index("claude-fable-5")
        f51_idx = cands.index("claude-fable-5-1")
        assert f5_idx < f51_idx, "claude-fable-5 must precede claude-fable-5-1"

    def test_fable5_before_fable51_aerolink(self) -> None:
        cands = _routing_candidates().get("aerolink", [])
        f5_idx = cands.index("claude-fable-5")
        f51_idx = cands.index("claude-fable-5-1")
        assert f5_idx < f51_idx, "claude-fable-5 must precede claude-fable-5-1 (aerolink)"

    def test_fable51_catalog_entry_present(self) -> None:
        assert "claude-fable-5-1" in _llm_models(), (
            "claude-fable-5-1 must be declared in config/llm/models.yaml"
        )

    def test_fable51_supports_tools(self) -> None:
        m = _llm_models()["claude-fable-5-1"]
        assert m.supports_tools is True, "claude-fable-5-1 must support tools"

    def test_anthropic_primary_candidates_preserved(self) -> None:
        """Primary presets (opus-5, sonnet-5) must still lead the list.

        2026-09-24: superseded — claude-opus-5-5 was added as the new first
        candidate (20% cheaper than opus-5, same capability tier), pushing
        claude-opus-5 to second and claude-sonnet-5 to third.
        """
        cands = _routing_candidates().get("anthropic", [])
        assert cands[0] == "claude-opus-5-5", "claude-opus-5-5 must be first"
        assert cands[1] == "claude-opus-5", "claude-opus-5 must remain second"
        assert cands[2] == "claude-sonnet-5", "claude-sonnet-5 must remain third"


# ── 2. Google candidates: Gemini 3.x models ─────────────────────────────────

class TestGemini3xCandidatesUpdated:
    """Gemini 3.x models must be in the Google provider failover candidates."""

    def test_gemini38_flash_in_google_candidates(self) -> None:
        cands = _routing_candidates().get("google", [])
        assert "gemini-3.8-flash" in cands, (
            "gemini-3.8-flash missing from google candidates in config/models.yaml"
        )

    def test_gemini37_flash_in_google_candidates(self) -> None:
        cands = _routing_candidates().get("google", [])
        assert "gemini-3.7-flash" in cands

    def test_gemini35_flash_lite_in_google_candidates(self) -> None:
        cands = _routing_candidates().get("google", [])
        assert "gemini-3.5-flash-lite" in cands

    def test_gemini31_pro_in_google_candidates(self) -> None:
        cands = _routing_candidates().get("google", [])
        assert "gemini-3.1-pro" in cands

    def test_gemini3x_catalog_entries_present(self) -> None:
        """Each 3.x candidate must also be in config/llm/models.yaml."""
        models = _llm_models()
        for mid in ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite", "gemini-3.1-pro"):
            assert mid in models, (
                f"{mid} candidate added to config/models.yaml but missing from "
                "config/llm/models.yaml — dangling candidate"
            )

    def test_gemini25_flash_still_first_google_candidate(self) -> None:
        """gemini-2.5-flash must remain the primary (probed, role preset)."""
        cands = _routing_candidates().get("google", [])
        assert cands[0] == "gemini-2.5-flash", (
            "gemini-2.5-flash must remain the first Google candidate "
            "(it is the executor/verifier role preset)"
        )

    def test_gemini25_before_gemini3x_flash(self) -> None:
        """Proven 2.5 models must precede unprobed 3.x ones."""
        cands = _routing_candidates().get("google", [])
        g25_idx = cands.index("gemini-2.5-flash")
        g38_idx = cands.index("gemini-3.8-flash")
        assert g25_idx < g38_idx, (
            "gemini-2.5-flash must precede gemini-3.8-flash until the 3.x "
            "models are live-probed"
        )

    def test_all_gemini3x_support_tools(self) -> None:
        models = _llm_models()
        for mid in ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite", "gemini-3.1-pro"):
            assert models[mid].supports_tools is True, (
                f"{mid}: supports_tools must be True"
            )


# ── 3. No dangling candidates (cross-check) ──────────────────────────────────

class TestNoDanglingCandidates:
    """Every newly-added candidate must also be declared in the LLM catalog."""

    def test_all_new_candidates_in_llm_catalog(self) -> None:
        all_models = set(_llm_models().keys())
        new_cands = {
            "claude-fable-5-1",
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-pro",
        }
        missing = new_cands - all_models
        assert not missing, (
            f"These newly-added candidates are missing from config/llm/models.yaml: "
            f"{sorted(missing)}"
        )
