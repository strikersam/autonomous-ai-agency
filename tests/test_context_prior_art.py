"""A quick-note reject must not contradict what the repository already has.

Two overnight quick notes on 2026-10-02 were rejected with analyses a human
reviewer had to correct:

* #1634 linked msitarzewski/agency-agents, which #1570 had already vendored
  (#1573). Nothing told the reviewer, so it called the source "not compatible"
  and claimed "no files in this codebase would be modified".
* #1632's reject cited ``handlers/telegram_bot.py``; the bot lives at
  ``telegram_bot.py`` in the repo root.

Fixed by R13 (prior art must be accounted for), R14 (paths cited in prose must
exist) and ``apply_review_gate``, which routes a reject failing either rule to
``needs-review`` instead of filing it.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".github" / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


sys.path.insert(0, str(SCRIPTS))
rules = _load("context_rules", SCRIPTS / "context_rules.py")
gen = _load("generate_context", SCRIPTS / "generate_context.py")
plan_gate = _load("context_plan_gate", REPO_ROOT / "scripts" / "context_plan_gate.py")

AGENCY_AGENTS = "https://github.com/msitarzewski/agency-agents"


def _reject(**fields: str) -> dict:
    return {"verdict": "reject", "verdict_reason": "", "notes": "", "prompt": "", **fields}


class TestSourceSlug:
    @pytest.mark.parametrize("url,slug", [
        (AGENCY_AGENTS, "msitarzewski/agency-agents"),
        ("https://github.com/Owner/Repo.git", "owner/repo"),
        ("https://github.com/a/b/tree/main/src/x.py", "a/b"),
        ("https://www.example.com/blog/post/", "example.com/blog/post"),
        ("https://example.com/", "example.com"),
    ])
    def test_slug(self, url: str, slug: str) -> None:
        assert rules.source_slug(url) == slug


class TestFindPriorArt:
    def _repo(self, tmp_path: Path) -> Path:
        files = {
            "agents/personas/README.md": "Source: <https://github.com/Msitarzewski/agency-agents>\n",
            "agent/registry.py": 'OWNER = "x"\n"repo": "msitarzewski/agency-agents",\n',
            "docs/context/issue-1.md": "msitarzewski/agency-agents\n",
            "tests/test_x.py": "msitarzewski/agency-agents\n",
            ".claude/state/log.md": "msitarzewski/agency-agents\n",
            ".github/workflows/w.yml": "# from msitarzewski/agency-agents\n",
            "unrelated.py": "print('hi')\n",
        }
        for rel, text in files.items():
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return tmp_path

    def test_finds_implementations_not_plans_tests_or_state(self, tmp_path: Path) -> None:
        found = rules.find_prior_art(AGENCY_AGENTS, self._repo(tmp_path))
        assert [p.path for p in found] == [
            ".github/workflows/w.yml",
            "agent/registry.py",
            "agents/personas/README.md",
        ]
        assert "agency-agents" in found[1].line

    def test_no_url_or_bare_host_finds_nothing(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        assert rules.find_prior_art(None, repo) == []
        assert rules.find_prior_art("https://example.com/", repo) == []

    def test_capped(self, tmp_path: Path) -> None:
        for i in range(rules.PRIOR_ART_MAX_FILES + 5):
            (tmp_path / f"f{i:02}.md").write_text("see a/b\n")
        assert len(rules.find_prior_art("https://github.com/a/b", tmp_path)) == rules.PRIOR_ART_MAX_FILES

    def test_real_repo_knows_agency_agents(self) -> None:
        paths = {p.path for p in rules.find_prior_art(AGENCY_AGENTS, REPO_ROOT)}
        assert "agents/personas/agency_agents/README.md" in paths


class TestR13PriorArt:
    ART = [rules.PriorArt("agents/persona_library.py", "...")]

    def test_ignoring_prior_art_is_a_violation(self) -> None:
        v = rules._check_prior_art(_reject(verdict_reason="Not compatible."), self.ART)
        assert [x.rule for x in v] == ["R13"]
        assert "agents/persona_library.py" in v[0].detail

    def test_naming_prior_art_passes(self) -> None:
        result = _reject(notes="Already shipped in agents/persona_library.py; nothing new upstream.")
        assert rules._check_prior_art(result, self.ART) == []

    def test_no_prior_art_no_rule(self) -> None:
        assert rules._check_prior_art(_reject(), []) == []


class TestR14ProsePaths:
    def test_missing_repo_path_flagged(self) -> None:
        result = _reject(notes="The bot (handlers/telegram_bot.py) uses agent/prompts.py.")
        v = rules._check_prose_paths(result, REPO_ROOT)
        assert [x.rule for x in v] == ["R14"]
        assert "handlers/telegram_bot.py" in v[0].detail
        assert "agent/prompts.py" not in v[0].detail

    @pytest.mark.parametrize("text", [
        "Upstream ships references/hig/buttons.md and scripts/pull-hig.mjs.",
        "See https://github.com/x/y/blob/main/agent/nope.py for details.",
        "Add agent/brand_new.py (new) beside the loop.",
        "The root file telegram_bot.py handles it.",
    ])
    def test_not_flagged(self, text: str) -> None:
        assert rules._check_prose_paths(_reject(prompt=text), REPO_ROOT) == []

    def test_applies_to_reject_through_validate(self) -> None:
        result = _reject(
            source_summary="x" * 200,
            verdict_reason="Different domain; see handlers/telegram_bot.py.",
        )
        found = rules.validate(result, source_fetched=True, repo_root=REPO_ROOT)
        assert "R14" in {v.rule for v in found}


class TestReviewGate:
    def test_contested_reject_needs_review(self) -> None:
        result = _reject(verdict_reason="Not compatible.")
        gated = rules.apply_review_gate(result, [rules.Violation("R13", "x")])
        assert gated["verdict"] == "needs-review"
        assert "R13" in gated["verdict_reason"]
        assert "Not compatible." in gated["verdict_reason"]
        assert result["verdict"] == "reject"

    def test_other_violations_keep_the_reject(self) -> None:
        result = _reject()
        assert rules.apply_review_gate(result, [rules.Violation("R6", "x")]) is result

    def test_non_reject_untouched(self) -> None:
        result = {"verdict": "adapt"}
        assert rules.apply_review_gate(result, [rules.Violation("R13", "x")]) is result

    def test_replay_1634(self) -> None:
        """The real #1634 reject, against the real repository."""
        result = _reject(
            source_summary=(
                "msitarzewski/agency-agents is a curated collection of Markdown files "
                "defining AI agent personalities, with install scripts for IDE agents."
            ),
            verdict_reason=(
                "The artifact is a prompt-template repository for IDE assistants. "
                "No executable capability transfers without a full rewrite."
            ),
            prompt="No implementation needed. Closing as no actionable feature transfer exists.",
            notes="No files in this codebase would be modified by adopting the artifact.",
        )
        prior = rules.find_prior_art(AGENCY_AGENTS, REPO_ROOT)
        found = rules.validate(result, source_fetched=True, repo_root=REPO_ROOT, prior_art=prior)
        assert "R13" in {v.rule for v in found}
        assert rules.apply_review_gate(result, found)["verdict"] == "needs-review"


class TestRendering:
    def test_badge_is_read_back_as_blocking(self) -> None:
        badge = gen.VERDICT_BADGES["needs-review"]
        assert plan_gate.read_verdict(f"## Decision\n\n{badge}\n") == "needs-review"
        assert "needs-review" not in plan_gate.IMPLEMENTABLE_VERDICTS

    def test_prior_art_shown_to_model_and_reader(self) -> None:
        art = [rules.PriorArt("agent/skill_registry.py", '"repo": "agency-agents",')]
        msg = gen._build_user_message("1", "t", "b", [], "ctx", "article", art)
        assert "## Prior art in this repository" in msg
        assert "agent/skill_registry.py" in msg
        assert "Prior art" not in gen._build_user_message("1", "t", "b", [], "ctx", "article", [])
        cell = rules.prior_art_cell(["agent/skill_registry.py"])
        assert cell == "1 file(s): `agent/skill_registry.py`"
        assert rules.prior_art_cell([]) == "none found"


class TestWorkflows:
    def _steps(self, name: str) -> list[dict]:
        wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / name).read_text())
        return [s for job in wf["jobs"].values() for s in job.get("steps", [])]

    def test_needs_review_is_not_dispatched_and_is_labelled(self) -> None:
        steps = self._steps("issue-context-generator.yml")
        dispatch = next(s for s in steps if s.get("name", "").startswith("Comment + dispatch"))
        assert "verdict != 'needs-review'" in dispatch["if"]
        review = next(s for s in steps if "needs review" in s.get("name", ""))
        assert "verdict == 'needs-review'" in review["if"]
        assert "quick-note:needs-review" in review["run"]

    def test_sweep_skips_and_plan_gate_labels_needs_review(self) -> None:
        text = (REPO_ROOT / ".github" / "workflows" / "process-quick-note.yml").read_text()
        assert '"quick-note:needs-review"' in text
        assert 'LABEL="quick-note:needs-review"' in text
