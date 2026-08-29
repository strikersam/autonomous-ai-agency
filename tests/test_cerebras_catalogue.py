"""The first link of the failover chain was pointed at models that do not exist.

`CEREBRAS_API_KEY` reached GitHub Actions on 2026-08-29, and the catalogue
probe was pointed at the provider for the first time. The account's
`/v1/models` returns exactly two ids — `gpt-oss-120b` and `gemma-4-31b`. Every
id this repository had configured for Cerebras answered **404**:

* `qwen-3-coder-480b` — the provider default, and the id `CLAUDE.md` named
* `llama-3.3-70b` — the `verifier`/`judge` preset, and `ProviderRouter`'s default
* `llama-3.1-8b` — the third rotation candidate
* `qwen-3-235b-a22b-instruct-2507` — proposed by PR #1378 at `priority: 9`

Runs 33259277329, 33259307270 and 33259357211.

Rule 4 makes Cerebras the first provider tried on every call. It had no working
entry at all, and nothing said so: a 404 on the first link simply moved traffic
to the second, which is indistinguishable from a healthy chain until the second
also fails. That is the same silent degradation the NVIDIA work unwound.

Neither replacement has answered a completion either — both return **402
Payment Required**, which is an account state, not a model state, and no code
change fixes it. The distinction matters and is the reason these are separate
assertions: a 404 means "this repository is wrong", a 402 means "the account
is". Only the first is ours to fix.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

# Read off the account's own catalogue on 2026-08-29. Not from vendor
# documentation, which is what put an id that 404s in front of the chain.
SERVED = ("gpt-oss-120b", "gemma-4-31b")

# Probed and answered 404 — absent from this account, not merely retired.
ABSENT = (
    "qwen-3-coder-480b",
    "llama-3.3-70b",
    "llama-3.1-8b",
    "qwen-3-235b-a22b-instruct-2507",
)

# Files that name a Cerebras model id and are therefore able to reintroduce one.
# `llama-3.3-70b` is a substring of Groq's `llama-3.3-70b-versatile`, so every
# check below matches whole ids, never substrings.
CARRIERS = (
    "config/models.yaml",
    "config/llm/models.yaml",
    "config/llm/providers.yaml",
    "packages/ai/brain_config.py",
    "packages/ai/registry.py",
    "packages/ai/router.py",
    "packages/ai/cost_tracker.py",
    "CLAUDE.md",
)


def _agency_catalogue() -> dict:
    return yaml.safe_load((REPO_ROOT / "config/models.yaml").read_text(encoding="utf-8"))


def _cerebras_block() -> dict:
    providers = _agency_catalogue().get("providers") or _agency_catalogue()
    return providers["cerebras"]


class TestOnlyWhatTheAccountServesIsConfigured:
    def test_every_candidate_is_one_the_account_lists(self) -> None:
        candidates = _cerebras_block()["candidates"]
        assert candidates, "an empty rotation would pass every other test vacuously"
        assert set(candidates) <= set(SERVED), (
            f"these are not in the account's catalogue and answer 404: "
            f"{sorted(set(candidates) - set(SERVED))}"
        )

    def test_every_role_preset_is_one_the_account_lists(self) -> None:
        presets = _cerebras_block()["role_presets"]
        assert set(presets.values()) <= set(SERVED), (
            f"a role is routed to a model that does not exist: "
            f"{sorted(set(presets.values()) - set(SERVED))}"
        )

    def test_the_gateway_default_is_one_the_account_lists(self) -> None:
        text = (REPO_ROOT / "config/llm/providers.yaml").read_text(encoding="utf-8")
        line = next(
            l for l in text.splitlines()
            if "CEREBRAS_DEFAULT_MODEL" in l
        )
        assert any(model in line for model in SERVED), (
            f"the provider default is an id the account does not serve: {line.strip()}"
        )


class TestTheAbsentIdsCannotComeBack:
    """A 404 id is worse than a missing one: it looks like a configured provider."""

    @pytest.mark.parametrize("model_id", ABSENT)
    @pytest.mark.parametrize("relative", CARRIERS)
    def test_no_file_names_an_absent_id_as_a_value(self, relative: str, model_id: str) -> None:
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        offenders = [
            f"{relative}:{number}"
            for number, line in enumerate(text.splitlines(), 1)
            # Comments are where the record of *why* these are gone lives, and
            # that record is the point — only live values are the defect.
            if not line.lstrip().startswith(("#", "*", "-", "|"))
            and _names_exactly(line, model_id)
        ]
        assert not offenders, (
            f"{model_id} answers 404 on this account; naming it here routes "
            f"traffic to nothing: {offenders}"
        )


def _names_exactly(line: str, model_id: str) -> bool:
    """Whole-id match. ``llama-3.3-70b`` must not match Groq's ``-versatile``."""
    index = line.find(model_id)
    while index != -1:
        after = line[index + len(model_id):index + len(model_id) + 1]
        if after not in ("-", "_") and not after.isalnum():
            return True
        index = line.find(model_id, index + 1)
    return False


class TestTheTwoCopiesAgree:
    """`config/models.yaml` wins at import, so a stale Python copy is invisible."""

    def test_the_python_candidates_match_the_catalogue(self) -> None:
        from packages.ai import brain_config

        source = (REPO_ROOT / "packages/ai/brain_config.py").read_text(encoding="utf-8")
        block = source[source.index('"cerebras": ['):]
        block = block[: block.index("],")]
        hardcoded = [
            line.strip().strip('",')
            for line in block.splitlines()[1:]
            if line.strip().startswith('"')
        ]
        assert hardcoded == list(_cerebras_block()["candidates"]), (
            "the Python fallback and the catalogue disagree; the catalogue wins "
            "at import, so this drift is invisible until the fallback is used"
        )
        assert brain_config  # imported to prove the module still loads


class TestCapabilitiesAreNotClaimedWithoutEvidence:
    """402 means nothing was measured. Undeclared capability must read as false.

    `packages/llm/registry.py` filters tool-calling requests on `supports_tools`.
    Declaring it true from a model's family name — which is what PR #1378 did —
    routes tool work to a model that may silently drop it.
    """

    def _gateway(self) -> dict:
        data = yaml.safe_load(
            (REPO_ROOT / "config/llm/models.yaml").read_text(encoding="utf-8")
        )
        return data["models"]

    @pytest.mark.parametrize("model_id", SERVED)
    def test_the_served_models_have_a_gateway_entry(self, model_id: str) -> None:
        assert model_id in self._gateway(), (
            "without an entry here the model has no context window and no "
            "capability flags, and is silently excluded from tool-calling"
        )

    @pytest.mark.parametrize("model_id", SERVED)
    def test_tool_support_is_not_claimed(self, model_id: str) -> None:
        entry = self._gateway()[model_id]
        assert entry.get("supports_tools") is False, (
            "no probe has seen a tool_call from this model — the account "
            "returns 402. Raise this when one has, not before"
        )

    @pytest.mark.parametrize("model_id", ABSENT)
    def test_no_absent_id_has_a_gateway_entry(self, model_id: str) -> None:
        assert model_id not in self._gateway()
