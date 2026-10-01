"""scripts/prompt_audit.py — accuracy on the real CLAUDE.md / AGENTS.md shapes.

Run against the real files it reported 14 findings, 9 of them noise: a
backticked command read as one path, file paths matched as `provider/model`
ids, ids only checked against config/models.yaml, deliberate "deprecated"
mentions and a runtime lock file. The noise hid the five real ones — CLAUDE.md
named a scheduler module that moved and a per-role model default that was
wrong, AGENTS.md linked a doc that does not exist (#1611, item 4).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def audit():
    spec = importlib.util.spec_from_file_location("prompt_audit_t", ROOT / "scripts/prompt_audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


KNOWN = {"nvidia/nemotron-3-super-120b-a12b"}


class TestPaths:
    def test_a_command_is_checked_token_by_token(self, audit) -> None:
        text = "`python scripts/check_changelog_parity.py --check`"
        assert audit._check_file_paths(text, "X.md") == []

    def test_a_missing_path_inside_a_command_is_still_flagged(self, audit) -> None:
        findings = audit._check_file_paths("`python scripts/gone.py`", "X.md")
        assert findings == ["  X.md: path `scripts/gone.py` does not exist"]

    def test_runtime_files_are_not_drift(self, audit) -> None:
        assert audit._check_file_paths("`.claude/state/runner.lock`", "X.md") == []


class TestModels:
    @pytest.mark.parametrize("token", ["handlers/v3_auth.py", "tests/e2e/", "packages/ai/router.py"])
    def test_file_paths_are_not_model_ids(self, audit, token) -> None:
        assert audit._check_model_ids(f"see `{token}`", "X.md", KNOWN) == []

    def test_a_deliberate_deprecation_mention_is_not_drift(self, audit) -> None:
        line = "| Groq | `deepseek-r1-70b` deprecated self-serve Aug 2026 |"
        assert audit._check_model_ids(line, "X.md", KNOWN) == []

    def test_an_unknown_model_is_still_flagged(self, audit) -> None:
        findings = audit._check_model_ids("default `nvidia/made-up-99b`", "X.md", KNOWN)
        assert len(findings) == 1 and "made-up-99b" in findings[0]

    def test_the_full_catalogue_counts_as_known(self, audit) -> None:
        import yaml

        catalogue = set(yaml.safe_load((ROOT / "config/llm/models.yaml").read_text())["models"])
        assert catalogue and catalogue <= audit._load_model_ids()

    def test_a_deprecation_word_excuses_only_its_own_id(self, audit) -> None:
        line = "| Groq | `gpt-oss-120b`, `kimi-k2-gone` — `deepseek-r1-70b` deprecated Aug 2026 |"
        findings = audit._check_model_ids(line, "X.md", {"gpt-oss-120b"})
        assert len(findings) == 1 and "kimi-k2-gone" in findings[0]

