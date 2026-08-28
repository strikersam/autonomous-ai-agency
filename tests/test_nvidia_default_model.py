"""The platform-wide NVIDIA default must not be a retired model.

`ProviderRouter`'s NVIDIA entry and `packages/config/settings.py` both carried
`meta/llama-3.3-70b-instruct` as the fallback when `NVIDIA_DEFAULT_MODEL` is
unset. That model reached end-of-life on 2026-08-26 and answers `410 Gone`, so
every caller relying on the default — not just the agent scripts — was handed a
dead id.

The replacement was supplied by the account owner, who can see the live
catalogue; it is not a guess from this repo. These tests pin that no *retired*
id can return as a default, which is the property that kept lapsing.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTER = REPO_ROOT / "packages/ai/router.py"
SETTINGS = REPO_ROOT / "packages/config/settings.py"

# Observed returning 410/404 in the 2026-08-27 implementer logs.
RETIRED = [
    "meta/llama-3.3-70b-instruct",
    # Listed in NVIDIA's catalogue and returns 404 when called. It was briefly
    # the default here on the strength of the listing alone — which is the
    # mistake this file exists to prevent, made inside the fix for it.
    "nvidia/nemotron-3-ultra-550b-a55b",
    "z-ai/glm-5.2",
    "z-ai/glm-5.1",
    "meta/llama-4-maverick-17b-128e-instruct",
    "meta/llama-4-scout-17b-16e-instruct",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "qwen/qwen3-coder-480b-a35b-instruct",
    "qwen/qwen2.5-coder-32b-instruct",
]

# The one NVIDIA id proven to answer a live completion (2026-08-28,
# catalogue-probe run 33192841180). Not "the one the docs name" — the one
# that returned HTTP 200 with text.
EXPECTED = "nvidia/nemotron-3-super-120b-a12b"


def _nvidia_default(source: str, anchor: str) -> str:
    """The literal fallback used when NVIDIA_DEFAULT_MODEL is unset."""
    window = source[source.index(anchor):][:400]
    match = re.search(r'or\s+"([^"]+)"|NVIDIA_DEFAULT_MODEL",\s*"([^"]+)"', window)
    assert match, f"no literal default found near {anchor!r}"
    return match.group(1) or match.group(2)


class TestTheDefaultIsNotDead:
    def test_router_nvidia_default(self) -> None:
        got = _nvidia_default(ROUTER.read_text(encoding="utf-8"), 'NVIDIA_DEFAULT_MODEL')
        assert got == EXPECTED
        assert got not in RETIRED

    def test_settings_nvidia_default(self) -> None:
        got = _nvidia_default(SETTINGS.read_text(encoding="utf-8"), 'NVIDIA_DEFAULT_MODEL')
        assert got == EXPECTED
        assert got not in RETIRED

    @pytest.mark.parametrize("model_id", RETIRED)
    def test_no_retired_id_is_the_router_default(self, model_id: str) -> None:
        """A retired id may still appear elsewhere (cost tables, per-role maps);
        what must never recur is one being handed out as *the* default."""
        source = ROUTER.read_text(encoding="utf-8")
        window = source[source.index("NVIDIA_DEFAULT_MODEL"):][:400]
        assert model_id not in window


class TestTheStaticFloorLeadsWithVerifiedIds:
    """The floor is only reached when discovery cannot run — which is exactly
    when getting the order wrong is unrecoverable, since nothing else will
    correct it. Both ids were read off the live catalogue by the account owner.
    """

    FLOOR = REPO_ROOT / ".github/scripts/nvidia_models.py"
    FALLBACK = "mistralai/mistral-nemotron"

    def _floor_ids(self) -> list[str]:
        source = self.FLOOR.read_text(encoding="utf-8")
        block = source[source.index("NVIDIA_CANDIDATE_MODELS: list"):]
        block = block[block.index("= [") :]
        return re.findall(r'\(\s*"([^"]+)"', block[: block.index("\n]")])

    def test_the_default_is_tried_first(self) -> None:
        assert self._floor_ids()[0] == EXPECTED

    def test_the_fallback_is_tried_second(self) -> None:
        assert self._floor_ids()[1] == self.FALLBACK

    def test_no_retired_id_survives_in_the_floor(self) -> None:
        assert not set(self._floor_ids()) & set(RETIRED)


class TestNoNvidiaFallbackIsRetired:
    """The defect was never confined to one file.

    Eight modules independently spelled out "the NVIDIA model to use when
    ``NVIDIA_DEFAULT_MODEL`` is unset", and a single retirement invalidated all
    of them at once while each looked locally reasonable. This sweeps the source
    tree so the next retirement is caught here rather than in a 410 at run time.
    """

    SEARCH_ROOTS = (
        "packages", "agent", "backend", "webui", "setup", "runtimes",
        "services", "voice", ".github/scripts",
    )

    def _fallback_literals(self) -> list[tuple[str, str]]:
        """``(path, model_id)`` for every literal used as the env-var fallback."""
        found: list[tuple[str, str]] = []
        pattern = re.compile(
            r'NVIDIA_DEFAULT_MODEL"[^"]{0,160}?(?:or|,)\s+"([^"]+)"', re.S
        )
        for root in self.SEARCH_ROOTS:
            for path in sorted((REPO_ROOT / root).rglob("*.py")):
                for model_id in pattern.findall(path.read_text(encoding="utf-8")):
                    found.append((str(path.relative_to(REPO_ROOT)), model_id))
        return found

    def test_the_sweep_actually_finds_something(self) -> None:
        """A regex that silently matched nothing would pass every assertion."""
        assert len(self._fallback_literals()) >= 4

    def test_no_fallback_is_a_retired_id(self) -> None:
        offenders = [pair for pair in self._fallback_literals() if pair[1] in RETIRED]
        assert not offenders, f"retired ids used as NVIDIA fallbacks: {offenders}"

    def test_no_retired_id_remains_in_the_hardcoded_nvidia_rotation(self) -> None:
        """``PROVIDER_CANDIDATES['nvidia']`` is tried in order, so a dead entry
        is a wasted call on every rotation through it.

        Asserted against the module literal, not the imported dict: at import
        time ``config/llm/models.yaml`` overrides it, and the YAML catalog is a
        separate surface with its own specs. The literal is the fallback used
        when the catalog is missing or corrupt — the degraded path, where a dead
        entry is least affordable.
        """
        source = (REPO_ROOT / "packages/ai/brain_config.py").read_text(encoding="utf-8")
        block = source[source.index('PROVIDER_CANDIDATES: dict'):]
        nvidia = block[block.index('"nvidia": ['): block.index("],")]
        for model_id in RETIRED:
            assert model_id not in nvidia, f"retired id in the rotation: {model_id}"

    def test_the_agent_role_defaults_are_not_retired(self) -> None:
        """Planner/executor/verifier fall back to a literal when no
        ``AGENT_*_MODEL`` is set — the path a fresh install takes."""
        source = (REPO_ROOT / "agent/loop.py").read_text(encoding="utf-8")
        block = source[source.index("DEFAULT_PLANNER_MODEL = ("):]
        block = block[: block.index("DEFAULT_JUDGE_MODEL")]
        for model_id in RETIRED:
            assert model_id not in block, f"agent role default is retired: {model_id}"
