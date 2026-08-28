"""Model ids belong in a catalogue, not in Python.

Four files in this repo each declare themselves authoritative:

* ``config/models.yaml`` — "Canonical model catalog … the single source of truth"
* ``config/llm/providers.yaml`` — "Adding a provider is an entry here. No Python changes"
* ``config/llm/models.yaml`` — "entries here always win"
* ``packages/ai/brain_config.py`` — a hardcoded copy "kept in sync with this file"

"Kept in sync" is a promise a comment cannot keep. When these tests were first
written, **11 of 17 providers disagreed** between the Python copy and the YAML
it claimed to mirror — and because the YAML wins at import, one of the
divergences was a model retired on 2026-08-26 sitting live in the NVIDIA
rotation, still being tried on every pass, while the Python copy that had been
"fixed" was never consulted.

These tests do not attempt the full consolidation. They stop the bleeding:
nothing new may be hardcoded, and the copies that exist may not drift further
apart without a test going red.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
BRAIN_CONFIG = REPO_ROOT / "packages/ai/brain_config.py"
AGENCY_CATALOGUE = REPO_ROOT / "config/models.yaml"
GATEWAY_CATALOGUE = REPO_ROOT / "config/llm/models.yaml"

# Imported, not copied: a second list of retired ids here would drift from
# the first, which is precisely the failure this module exists to catch.
from tests.test_nvidia_default_model import EXPECTED, RETIRED  # noqa: E402


def _hardcoded_candidates() -> dict[str, list[str]]:
    """``PROVIDER_CANDIDATES`` as written in the module, before YAML overrides.

    Read from source, not by import: importing gives the merged result, which is
    exactly what hid the drift.
    """
    source = BRAIN_CONFIG.read_text(encoding="utf-8")
    block = source[source.index("PROVIDER_CANDIDATES: dict"):]
    block = block[: block.index("\n}")]
    found: dict[str, list[str]] = {}
    current: str | None = None
    for line in block.splitlines():
        opened = re.match(r'^    "([^"]+)": \[', line)
        if opened:
            current = opened.group(1)
            found[current] = []
            continue
        entry = re.match(r'^        "([^"]+)",', line)
        if entry and current is not None:
            found[current].append(entry.group(1))
    return found


def _yaml_candidates() -> dict[str, list[str]]:
    data = yaml.safe_load(AGENCY_CATALOGUE.read_text(encoding="utf-8")) or {}
    providers = data.get("providers") or {}
    return {
        pid: list(entry.get("candidates") or [])
        for pid, entry in providers.items()
        if isinstance(entry, dict)
    }


class TestTheCatalogueIsWhatActuallyRuns:
    """The YAML wins at import. A fix applied only to the Python copy is a
    fix that never runs — which is what happened on 2026-08-28."""

    def test_the_python_copy_does_not_decide_the_rotation(self) -> None:
        from packages.ai.brain_config import PROVIDER_CANDIDATES

        live = PROVIDER_CANDIDATES.get("nvidia") or []
        assert live == _yaml_candidates().get("nvidia"), (
            "the imported rotation must come from the catalogue, not the literal"
        )

    @pytest.mark.parametrize(
        "retired",
        [
            "meta/llama-3.3-70b-instruct",
            "nvidia/llama-3.3-nemotron-super-49b-v1.5",
            "nvidia/llama-3.1-nemotron-ultra-253b-v1",
            "qwen/qwen3-coder-480b-a35b-instruct",
            "qwen/qwen2.5-coder-32b-instruct",
        ],
    )
    def test_no_retired_id_is_in_any_live_rotation(self, retired: str) -> None:
        """Checked against the catalogue that wins, not the copy that loses."""
        from packages.ai.brain_config import PROVIDER_CANDIDATES

        offenders = [
            pid for pid, models in PROVIDER_CANDIDATES.items() if retired in (models or [])
        ]
        assert not offenders, f"{retired} still rotates for: {offenders}"


class TestTheCopiesMayNotDriftFurther:
    """A frozen record of the divergence found on 2026-08-28.

    Reconciling these eleven is a behaviour change on the degraded path (the
    Python copy is only consulted when the YAML is missing or corrupt), so it is
    not done here. What is done: the set cannot grow. A twelfth divergence, or a
    new provider hardcoded without a catalogue entry, fails this test.
    """

    KNOWN_DIVERGENT = {
        "cerebras", "dashscope", "deepseek", "google", "groq",
        "moonshot", "ollama", "zai", "zhipu",
    }

    def _divergent(self) -> set[str]:
        hard, soft = _hardcoded_candidates(), _yaml_candidates()
        return {
            pid
            for pid in set(hard) | set(soft)
            if (hard.get(pid) or []) != (soft.get(pid) or [])
        }

    def test_the_divergence_does_not_grow(self) -> None:
        new = self._divergent() - self.KNOWN_DIVERGENT
        assert not new, (
            f"new drift between packages/ai/brain_config.py and "
            f"config/models.yaml: {sorted(new)}. Put the models in the "
            f"catalogue; the Python copy is a fallback, not a place to edit."
        )

    def test_nvidia_stays_reconciled(self) -> None:
        """NVIDIA is the one this work reconciled. It must not regress —
        that divergence is what put a retired model in production."""
        assert "nvidia" not in self._divergent()

    def test_the_known_list_is_not_stale(self) -> None:
        """A shrinking divergence is progress, but the list must be trimmed to
        match or it stops meaning anything."""
        fixed = self.KNOWN_DIVERGENT - self._divergent()
        assert not fixed, (
            f"these no longer diverge — remove them from KNOWN_DIVERGENT: {sorted(fixed)}"
        )


class TestBothCataloguesAgreeOnWhatExists:
    def test_the_gateway_catalogue_has_no_retired_nvidia_default(self) -> None:
        """``config/llm/models.yaml`` drives capability filtering. An entry for a
        retired id there is a routing option that can only fail."""
        data = yaml.safe_load(GATEWAY_CATALOGUE.read_text(encoding="utf-8")) or {}
        models = data.get("models") or {}
        assert "meta/llama-3.3-70b-instruct" not in models, (
            "retired model still declared in the gateway catalogue"
        )


class TestTheGatewayRegistryOffersOnlyLiveModels:
    """A sixth model source, found on 2026-08-28 while verifying a fix.

    ``packages/llm/registry.py::_seed_from_legacy`` imports
    ``packages/ai/registry.py`` and adds any model absent from the YAML
    catalogues. So removing a retired id from ``config/llm/models.yaml`` did
    nothing — it came straight back from the legacy registry, and kept being
    offered as a *tool-calling* candidate on the gateway path.

    This is the same defect as the rest of this file, one layer deeper: the
    removal looked correct and was inert, and only building the registry and
    asking it what it would route to revealed otherwise.
    """

    def _nvidia_candidates(self, require_tools: bool = False) -> list[str]:
        from packages.llm.config import reload_config
        from packages.llm.registry import ModelRegistry

        registry = ModelRegistry(reload_config())
        return [
            m.id
            for m in registry.candidates(provider_id="nvidia", require_tools=require_tools)
        ]

    def test_the_registry_offers_something(self) -> None:
        assert self._nvidia_candidates(), "no nvidia models; guards below would be vacuous"

    @pytest.mark.parametrize("retired", RETIRED)
    def test_no_retired_id_is_routable(self, retired: str) -> None:
        assert retired not in self._nvidia_candidates(), (
            f"{retired} is still routable via the gateway registry — check "
            f"packages/ai/registry.py, not just the YAML catalogues"
        )

    @pytest.mark.parametrize("retired", RETIRED)
    def test_no_retired_id_is_offered_for_tool_calls(self, retired: str) -> None:
        assert retired not in self._nvidia_candidates(require_tools=True)

    def test_the_default_can_serve_tool_calls(self) -> None:
        """The platform default must survive ``require_tools`` filtering.

        Undeclared models get ``supports_tools: false`` and are dropped from
        every tool-calling request — silently, since a shorter candidate list
        looks identical to a healthy one.
        """
        assert EXPECTED in self._nvidia_candidates(require_tools=True)
