"""The migration that rescues a stale brain config must not write a dead model.

`backend/server.py` runs a startup migration whose stated job is to reset a
BrainConfig that "points at a provider/model that is known-broken". Until
2026-09-01 it reset to two hardcoded ids:

    fast_agent_model = "meta/llama-4-maverick-17b-128e-instruct"
    standard_model   = "z-ai/glm-5.2"

Both answer 410. Both were already listed as retired in
`tests/test_nvidia_default_model.py`. Neither was in the migration's own
`old_models` set, so a row it had poisoned could never trigger the reset that
would fix it — the rescue wrote the failure and then declined to notice.

That is why production kept calling `nvidia-nim/z-ai/glm-5.2` and logging
`410 Gone` every 30 minutes on 2026-09-01, four separate catalogue corrections
later: every fix landed in the catalogue, and this migration overwrote the
database from its own copy on each boot.

The existing retired-id guard did not catch it because it checks the
catalogues, and this is a third copy living in a request handler.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests"))

SERVER = REPO_ROOT / "backend/server.py"

# Groq ids the repo carried until 2026-09-01. None is in the account's
# 14-model catalogue; the three that were called answered 404/400 in
# catalogue-probe run 33483766556.
DEAD_GROQ = (
    "llama-3.3-70b-versatile",
    "deepseek-r1-distill-llama-70b",
    "llama-3.1-8b-instant",
    "moonshotai/kimi-k2-instruct",
    "qwen-qwq-32b",
)


def _retired_ids() -> list[str]:
    """The retired list this repo already maintains — imported, not copied."""
    from test_nvidia_default_model import RETIRED

    assert RETIRED, "the retired list is empty; these checks would pass vacuously"
    return list(RETIRED)


def _migration_block() -> str:
    """The body of the stale-BrainConfig startup migration."""
    source = SERVER.read_text(encoding="utf-8")
    start = source.find("known_good_providers")
    assert start != -1, "the migration's provider whitelist moved; update this locator"
    end = source.find("Brain config safe-default migration failed", start)
    assert end != -1, "the migration's except-clause moved; update this locator"
    return source[start:end]


class TestTheMigrationWritesOnlyLiveModels:
    @pytest.mark.parametrize("retired", _retired_ids())
    def test_no_retired_id_is_assigned_in_the_migration(self, retired: str) -> None:
        """A retired id may be *listed* as one to migrate off, never assigned.

        The distinction matters: `old_models` must name dead ids, and that is
        the only place they belong.
        """
        block = _migration_block()
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or retired not in stripped:
                continue
            assert re.search(r"=\s*[\"']" + re.escape(retired), stripped) is None, (
                f"the migration assigns the retired id {retired!r}: {stripped!r}"
            )

    def test_the_models_are_read_from_the_catalogue(self) -> None:
        """Not restated here. A third copy is what caused the outage."""
        block = _migration_block()
        assert "PROVIDER_PRESETS" in block, (
            "the migration must derive its target models from the catalogue, "
            "which is the one source the probe workflow verifies against the "
            "live provider"
        )

    def test_it_declines_to_write_when_the_catalogue_is_empty(self) -> None:
        """No preset means nothing proven to migrate *to*.

        Guessing is what produced the 410; leaving the row alone is
        recoverable, so the empty case must return rather than write.
        """
        block = _migration_block()
        assert "no nvidia role preset" in block, (
            "the migration must bail out when the catalogue yields no preset"
        )

    @pytest.mark.parametrize(
        "poisoned", ("z-ai/glm-5.2", "meta/llama-4-maverick-17b-128e-instruct")
    )
    def test_the_ids_it_used_to_write_are_migrated_off(self, poisoned: str) -> None:
        """Rows this migration poisoned must be able to recover.

        `needs_reset` is the only path that rewrites the model fields, so an
        id absent from `old_models` is an id that stays forever.
        """
        block = _migration_block()
        old_models = block[block.find("old_models") : block.find("slow_planner_models")]
        assert poisoned in old_models, (
            f"{poisoned!r} was written by this migration and answers 410; without "
            "it in old_models an already-poisoned config never self-corrects"
        )


class TestTheCatalogueNamesOnlyProbedGroqIds:
    """Groq's configured ids were not in the account's catalogue at all."""

    @pytest.mark.parametrize("dead", DEAD_GROQ)
    def test_no_dead_groq_id_remains(self, dead: str) -> None:
        from packages.ai.brain_config import PROVIDER_CANDIDATES, PROVIDER_PRESETS

        assert dead not in PROVIDER_CANDIDATES.get("groq", []), (
            f"{dead!r} is not served by this account (probe run 33483766556)"
        )
        assert dead not in set(PROVIDER_PRESETS.get("groq", {}).values()), (
            f"{dead!r} is a role preset but answers 404/400"
        )

    def test_the_preset_is_a_candidate(self) -> None:
        """A role preset the rotation cannot fall back to is a single point of failure."""
        from packages.ai.brain_config import PROVIDER_CANDIDATES, PROVIDER_PRESETS

        candidates = PROVIDER_CANDIDATES.get("groq", [])
        assert candidates, "no groq candidates; this check would pass vacuously"
        for role, model in PROVIDER_PRESETS.get("groq", {}).items():
            assert model in candidates, f"groq {role} preset {model!r} is not in the rotation"


class TestNoBrainConfigWriterHardcodesAModel:
    """The class-level guard. Four writers exist; two carried literals.

    Chasing instances found them one outage at a time:

    * `backend/server.py` — the startup migration, fixed 2026-09-01
    * `packages/ai/self_heal.py` (PR #1046 reset) — found *because the first
      fix did not work*: the migration corrected the row at boot and this
      healer overwrote it with `z-ai/glm-5.2` 32 seconds later, then saw the
      410s its own write caused and ran again
    * `packages/ai/self_heal.py` (failover persist) — always read the catalogue
    * `packages/ai/watchdog.py` — always read the catalogue

    Two of the four were already right, which is the point: the pattern was
    established in the same files that violated it. So this asserts the
    property directly rather than naming the offenders — a fifth writer added
    later fails here without anyone remembering why.

    Parsed with `ast`, not grep: a keyword argument's value is either a literal
    or it is not, and that distinction is exactly what is being enforced.
    """

    ROOTS = ("packages", "backend", "services", "agent", "agents", "handlers", "tasks")

    @staticmethod
    def _model_kwargs_with_literals(path: Path) -> list[str]:
        import ast

        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - not our concern here
            return []

        offenders: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name != "BrainConfigPatch":
                continue
            for keyword in node.keywords:
                if not keyword.arg or not keyword.arg.endswith("_model"):
                    continue
                value = keyword.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    offenders.append(
                        f"{path}:{value.lineno} {keyword.arg}={value.value!r}"
                    )
        return offenders

    def test_no_writer_assigns_a_literal_model_id(self) -> None:
        offenders: list[str] = []
        scanned = 0
        for root in self.ROOTS:
            for path in (REPO_ROOT / root).rglob("*.py"):
                if "test" in path.name:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                if "BrainConfigPatch(" not in text:
                    continue
                scanned += 1
                offenders.extend(self._model_kwargs_with_literals(path))

        assert scanned, "no BrainConfigPatch writers found; this guard would pass vacuously"
        assert not offenders, (
            "a brain-config writer hardcodes a model id. Every id in this repo "
            "has an expiry date nobody is told about, so a literal here becomes "
            "a 410 that survives every catalogue correction. Read the model from "
            "packages.ai.brain_config.PROVIDER_PRESETS, which the catalogue-probe "
            f"workflow checks against the live provider: {offenders}"
        )
