"""tests/test_daily_automation_2026_08_03.py — Daily automation (2026-08-03).

Covers the model-catalog improvements applied today:

  1. claude-opus-5 added to Anthropic and Aerolink providers
     (model catalog + hardcoded brain_config.py fallbacks).

  2. brain_config.py PROVIDER_CANDIDATES synced with config/models.yaml:
     - Anthropic: removed stale 2024 model IDs; added Claude 5 family.
     - Aerolink: added claude-opus-5 as top model.
     - Groq: added Llama 4 models; removed deprecated mixtral-8x7b-32768.
     - NVIDIA: added meta/llama-4-maverick-17b-128e-instruct and
               meta/llama-4-scout-17b-16e-instruct.
"""

from __future__ import annotations

import os
import yaml

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
MODELS_YAML = os.path.join(REPO_ROOT, "config", "models.yaml")

STALE_ANTHROPIC_MODELS = (
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-opus-4-5",
)

DEPRECATED_GROQ_MODELS = ("mixtral-8x7b-32768",)


def _load_yaml() -> dict:
    with open(MODELS_YAML, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ── config/models.yaml ───────────────────────────────────────────────────────


def test_yaml_anthropic_planner_is_opus_5():
    cfg = _load_yaml()
    assert cfg["providers"]["anthropic"]["role_presets"]["planner"] == "claude-opus-5"


def test_yaml_anthropic_judge_is_opus_5():
    cfg = _load_yaml()
    assert cfg["providers"]["anthropic"]["role_presets"]["judge"] == "claude-opus-5"


def test_yaml_anthropic_candidates_contains_opus_5():
    cfg = _load_yaml()
    candidates = cfg["providers"]["anthropic"]["candidates"]
    assert "claude-opus-5" in candidates, f"claude-opus-5 missing from anthropic candidates: {candidates}"


def test_yaml_anthropic_opus_5_is_first_candidate():
    cfg = _load_yaml()
    candidates = cfg["providers"]["anthropic"]["candidates"]
    assert candidates[0] == "claude-opus-5", f"Expected claude-opus-5 first, got {candidates[0]}"


def test_yaml_aerolink_planner_is_opus_5():
    cfg = _load_yaml()
    assert cfg["providers"]["aerolink"]["role_presets"]["planner"] == "claude-opus-5"


def test_yaml_aerolink_judge_is_opus_5():
    cfg = _load_yaml()
    assert cfg["providers"]["aerolink"]["role_presets"]["judge"] == "claude-opus-5"


def test_yaml_aerolink_candidates_contains_opus_5():
    cfg = _load_yaml()
    candidates = cfg["providers"]["aerolink"]["candidates"]
    assert "claude-opus-5" in candidates, f"claude-opus-5 missing from aerolink candidates: {candidates}"


def test_yaml_aerolink_opus_5_is_first_candidate():
    cfg = _load_yaml()
    candidates = cfg["providers"]["aerolink"]["candidates"]
    assert candidates[0] == "claude-opus-5", f"Expected claude-opus-5 first, got {candidates[0]}"


# ── packages/ai/brain_config.py ──────────────────────────────────────────────


def test_brain_config_anthropic_planner_is_opus_5():
    from packages.ai.brain_config import PROVIDER_PRESETS
    assert PROVIDER_PRESETS["anthropic"]["planner"] == "claude-opus-5"


def test_brain_config_anthropic_judge_is_opus_5():
    from packages.ai.brain_config import PROVIDER_PRESETS
    assert PROVIDER_PRESETS["anthropic"]["judge"] == "claude-opus-5"


def test_brain_config_aerolink_planner_is_opus_5():
    from packages.ai.brain_config import PROVIDER_PRESETS
    assert PROVIDER_PRESETS["aerolink"]["planner"] == "claude-opus-5"


def test_brain_config_aerolink_judge_is_opus_5():
    from packages.ai.brain_config import PROVIDER_PRESETS
    assert PROVIDER_PRESETS["aerolink"]["judge"] == "claude-opus-5"


def test_brain_config_anthropic_candidates_contains_opus_5():
    from packages.ai.brain_config import PROVIDER_CANDIDATES
    cands = PROVIDER_CANDIDATES["anthropic"]
    assert "claude-opus-5" in cands, f"claude-opus-5 missing: {cands}"


def test_brain_config_anthropic_no_stale_2024_models():
    from packages.ai.brain_config import PROVIDER_CANDIDATES
    cands = PROVIDER_CANDIDATES["anthropic"]
    for stale in STALE_ANTHROPIC_MODELS:
        assert stale not in cands, (
            f"Stale 2024 model {stale!r} still in anthropic candidates — should have been replaced"
        )


def test_brain_config_aerolink_candidates_contains_opus_5():
    from packages.ai.brain_config import PROVIDER_CANDIDATES
    cands = PROVIDER_CANDIDATES["aerolink"]
    assert "claude-opus-5" in cands, f"claude-opus-5 missing from aerolink: {cands}"


def test_brain_config_groq_candidates_no_deprecated_mixtral():
    from packages.ai.brain_config import PROVIDER_CANDIDATES
    cands = PROVIDER_CANDIDATES["groq"]
    for deprecated in DEPRECATED_GROQ_MODELS:
        assert deprecated not in cands, (
            f"Deprecated Groq model {deprecated!r} still in candidates — should be removed"
        )


# 2026-08-28: superseded, exactly like the deprecated-Groq cases above. These
# asserted that NVIDIA's rotation *contained* Llama 4 Maverick and Scout, which
# was true when written. A live probe against the production key found both
# retired — Maverick 410 Gone, Scout 404 — so they left the catalogue. Keeping
# the original assertions would have pinned two dead models into the rotation.
RETIRED_NVIDIA_MODELS = (
    "meta/llama-4-maverick-17b-128e-instruct",
    "meta/llama-4-scout-17b-16e-instruct",
)


def test_brain_config_nvidia_has_no_retired_llama4():
    from packages.ai.brain_config import PROVIDER_CANDIDATES
    cands = PROVIDER_CANDIDATES["nvidia"]
    for retired in RETIRED_NVIDIA_MODELS:
        assert retired not in cands, (
            f"Retired model {retired!r} still in nvidia candidates: {cands}"
        )


def test_brain_config_nvidia_candidates_are_not_empty():
    """The rotation losing every entry is the outage this series began with."""
    from packages.ai.brain_config import PROVIDER_CANDIDATES
    assert PROVIDER_CANDIDATES["nvidia"], "nvidia rotation must not be empty"


# ── Cross-check: brain_config.py and models.yaml are in sync ─────────────────


def test_anthropic_candidates_match_yaml():
    """brain_config.py anthropic candidates must exactly match models.yaml (order and content)."""
    cfg = _load_yaml()
    yaml_cands = cfg["providers"]["anthropic"]["candidates"]
    from packages.ai.brain_config import PROVIDER_CANDIDATES
    assert PROVIDER_CANDIDATES["anthropic"] == yaml_cands, (
        f"Ordered mismatch between brain_config.py and models.yaml:\n"
        f"  py:   {PROVIDER_CANDIDATES['anthropic']}\n"
        f"  yaml: {yaml_cands}"
    )


def test_aerolink_candidates_match_yaml():
    """brain_config.py aerolink candidates must exactly match models.yaml (order and content)."""
    cfg = _load_yaml()
    yaml_cands = cfg["providers"]["aerolink"]["candidates"]
    from packages.ai.brain_config import PROVIDER_CANDIDATES
    assert PROVIDER_CANDIDATES["aerolink"] == yaml_cands, (
        f"Ordered mismatch between brain_config.py and models.yaml:\n"
        f"  py:   {PROVIDER_CANDIDATES['aerolink']}\n"
        f"  yaml: {yaml_cands}"
    )
