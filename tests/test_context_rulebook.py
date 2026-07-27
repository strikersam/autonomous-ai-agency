"""Tests for the quick-note context quality gate.

Covers three things:

1. **The rulebook and the gate stay in sync.** They are one artifact in two
   files (`docs/QUICK_NOTE_CONTEXT_RULEBOOK.md` and
   `.github/scripts/context_rules.py`); a rule enforced but undocumented, or
   documented but unenforced, is a defect.
2. **Each rule catches the sloppy output it was written for.** Every case below
   is drawn from real generated documents in `docs/context/`.
3. **Regression: `generate_context.py` has a working `__main__` entrypoint.**
   The file once ended in a truncated `ma` instead of `main()`. That is a
   NameError at runtime, not a SyntaxError, so `compileall` passed and the
   existing test suite passed too — it loads the module under a non-`__main__`
   name, which never evaluates the guarded line. Every context generation in
   production failed for as long as it was there.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".github" / "scripts"
RULEBOOK = REPO_ROOT / "docs" / "QUICK_NOTE_CONTEXT_RULEBOOK.md"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture(scope="module")
def rules():
    sys.path.insert(0, str(SCRIPTS))
    return _load("context_rules")


def _good_result() -> dict:
    """A result that satisfies every machine-checked rule."""
    return {
        "title": "feat: add YouTube transcript ingestion to the research agent",
        "source_summary": (
            "The linked gist is a Claude Code skill file, youtube-analyzer/SKILL.md. "
            "It takes a YouTube URL, pulls the transcript without an API key, and "
            "returns the video's structure, hook, and key moments as Markdown."
        ),
        "verdict": "adapt",
        "verdict_reason": "The transcript-to-structure step is useful; the skill packaging is not.",
        "prompt": "Extend the research agent so a YouTube URL resolves to a transcript summary.",
        "todos": [
            {
                "step": 1,
                "task": "Add a transcript fetcher to the research agent",
                "done_when": "agent/tools.py exposes fetch_transcript(url) returning plain text",
                "complexity": "M",
                "file": "agent/tools.py",
            }
        ],
        "relevant_files": ["agent/tools.py", "CLAUDE.md"],
        "risk_flags": ["agent/tools.py"],
        "notes": "Assuming the transcript endpoint stays unauthenticated — if wrong, a key is needed.",
    }


# ---------------------------------------------------------------------------
# 1. Rulebook / gate parity
# ---------------------------------------------------------------------------

def test_every_gate_rule_is_documented_in_the_rulebook(rules) -> None:
    """A rule the gate enforces must be explained where humans read."""
    source = (SCRIPTS / "context_rules.py").read_text()
    enforced = set(re.findall(r'Violation\(\s*"(R\d+)"', source))
    documented = set(re.findall(r"^### (R\d+) —", RULEBOOK.read_text(), re.MULTILINE))

    undocumented = enforced - documented
    assert not undocumented, (
        f"gate enforces {sorted(undocumented)} but the rulebook does not explain them"
    )


def test_every_documented_gate_rule_is_enforced(rules) -> None:
    """A rule documented as [gate] must actually be checked in code."""
    text = RULEBOOK.read_text()
    gate_rules = {
        rid
        for rid, marker in re.findall(r"^### (R\d+) —.*?\*\*\[(gate|review)\]\*\*", text, re.MULTILINE)
        if marker == "gate"
    }
    source = (SCRIPTS / "context_rules.py").read_text()
    enforced = set(re.findall(r'Violation\(\s*"(R\d+)"', source))

    unenforced = gate_rules - enforced
    assert not unenforced, (
        f"rulebook marks {sorted(unenforced)} as [gate] but nothing enforces them"
    )


def test_plan_only_rules_are_all_real_rules(rules) -> None:
    documented = set(re.findall(r"^### (R\d+) —", RULEBOOK.read_text(), re.MULTILINE))
    assert rules.PLAN_ONLY_RULES <= documented


# ---------------------------------------------------------------------------
# 2. Each rule catches its defect
# ---------------------------------------------------------------------------

def _rule_ids(violations) -> set[str]:
    return {v.rule for v in violations}


def test_clean_result_passes_the_gate(rules) -> None:
    violations = rules.validate(
        _good_result(), source_fetched=True, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert violations == [], [str(v) for v in violations]


def test_r1_flags_an_ungrounded_plan(rules) -> None:
    violations = rules.validate(
        _good_result(), source_fetched=False, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert "R1" in _rule_ids(violations)


def test_r2_flags_a_missing_source_summary(rules) -> None:
    result = _good_result() | {"source_summary": "A GitHub repo."}
    violations = rules.validate(
        result, source_fetched=True, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert "R2" in _rule_ids(violations)


def test_r3_flags_a_missing_verdict(rules) -> None:
    result = _good_result() | {"verdict": ""}
    violations = rules.validate(
        result, source_fetched=True, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert "R3" in _rule_ids(violations)


def test_r3_reject_verdict_is_a_complete_valid_outcome(rules) -> None:
    """Rejecting a source must not require inventing TODOs, files, or risks."""
    result = {
        "title": "docs: reject — no applicable feature",
        "source_summary": (
            "The linked gist is a Claude Code skill that summarises YouTube videos "
            "for content creators. It has no proxy, routing, agent, or observability "
            "surface and does not interact with an inference backend at all."
        ),
        "verdict": "reject",
        "verdict_reason": "Targets video summarisation; this repo has no video surface.",
        "prompt": "Considered and ruled out: nothing in the source maps onto this platform.",
        "todos": [],
        "relevant_files": [],
        "risk_flags": [],
        "notes": "",
    }
    violations = rules.validate(
        result, source_fetched=True, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert violations == [], [str(v) for v in violations]


def test_r4_flags_a_todo_with_no_done_condition(rules) -> None:
    result = _good_result()
    result["todos"] = [
        {"step": 1, "task": "Improve the endpoint", "done_when": "", "file": "agent/tools.py"}
    ]
    violations = rules.validate(
        result, source_fetched=True, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert "R4" in _rule_ids(violations)


def test_r5_flags_exploration_dressed_up_as_a_task(rules) -> None:
    """The real defect from docs/context/issue-820.md: 'Review the repository'."""
    result = _good_result()
    result["todos"] = [
        {
            "step": 1,
            "task": "Review the loop-engineering repository",
            "done_when": "the repository has been reviewed thoroughly",
            "file": None,
        }
    ]
    violations = rules.validate(
        result, source_fetched=True, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert "R5" in _rule_ids(violations)


def test_r5_allows_a_targeted_task_with_a_real_done_condition(rules) -> None:
    result = _good_result()
    result["todos"] = [
        {
            "step": 1,
            "task": "Identify every call site of _try_provider",
            "done_when": "packages/ai/router.py lists each caller in a module docstring",
            "file": "packages/ai/router.py",
        }
    ]
    result["risk_flags"] = ["packages/ai/router.py"]
    violations = rules.validate(
        result, source_fetched=True, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert "R5" not in _rule_ids(violations)


def test_r6_flags_hedged_guesses(rules) -> None:
    """The real defect: 'features such as improved model routing'."""
    result = _good_result() | {
        "prompt": "Integrate features such as improved routing, and update key_store.py if necessary."
    }
    violations = rules.validate(
        result, source_fetched=True, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert "R6" in _rule_ids(violations)


def test_r7_flags_unearned_risk_flags(rules) -> None:
    """The real defect: key_store.py flagged risky by a plan that never touches it."""
    result = _good_result() | {"risk_flags": ["agent/tools.py", "key_store.py"]}
    violations = rules.validate(
        result, source_fetched=True, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert "R7" in _rule_ids(violations)
    assert any("key_store.py" in v.detail for v in violations)


def test_r8_flags_fabricated_file_paths(rules) -> None:
    result = _good_result() | {
        "relevant_files": ["agent/tools.py", "packages/ai/totally_made_up.py"]
    }
    violations = rules.validate(
        result, source_fetched=True, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert "R8" in _rule_ids(violations)


def test_r8_allows_files_the_plan_intends_to_create(rules) -> None:
    result = _good_result() | {
        "relevant_files": ["agent/tools.py", "packages/ai/transcripts.py (new)"]
    }
    violations = rules.validate(
        result, source_fetched=True, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert "R8" not in _rule_ids(violations)


def test_r9_flags_restating_the_repository_constitution(rules) -> None:
    result = _good_result() | {
        "prompt": "Run pytest -x before and after changes. Use type annotations on all public functions."
    }
    violations = rules.validate(
        result, source_fetched=True, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert "R9" in _rule_ids(violations)


def test_r10_flags_the_former_project_name(rules) -> None:
    result = _good_result() | {"prompt": "Implement this in the local-llm-server project."}
    violations = rules.validate(
        result, source_fetched=True, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert "R10" in _rule_ids(violations)


def test_r11_flags_a_plan_with_no_existing_integration_point(rules) -> None:
    result = _good_result() | {"relevant_files": ["packages/ai/brand_new.py (new)"]}
    violations = rules.validate(
        result, source_fetched=True, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert "R11" in _rule_ids(violations)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def test_violations_are_reported_to_humans_and_to_the_model(rules) -> None:
    result = _good_result() | {"risk_flags": ["key_store.py"]}
    violations = rules.validate(
        result, source_fetched=True, repo_root=REPO_ROOT, title="quick-note:x"
    )
    assert violations

    human = rules.format_violations(violations)
    assert "Quality Gate" in human and "R7" in human

    model = rules.repair_instruction(violations)
    assert "R7" in model and "reject" in model


def test_a_clean_result_still_renders_a_quality_gate_section(rules) -> None:
    assert "✅" in rules.format_violations([])


# ---------------------------------------------------------------------------
# 3. Regression: the entrypoint must actually call main()
# ---------------------------------------------------------------------------

def _guard_statements(path: Path) -> list[ast.stmt]:
    """Return the body of the module's `if __name__ == "__main__":` guard."""
    body: list[ast.stmt] = []
    for node in ast.parse(path.read_text()).body:
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ):
            body.extend(node.body)
    return body


def test_generate_context_has_a_working_main_entrypoint() -> None:
    """Regression for the truncated `ma` that silently broke every generation.

    Parsed from the AST rather than executed, so this asserts the guarded call
    is real without invoking the network path.
    """
    stmts = _guard_statements(SCRIPTS / "generate_context.py")
    assert stmts, "generate_context.py lost its __main__ guard"
    for stmt in stmts:
        assert isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call), (
            f"__main__ guard contains a bare {ast.unparse(stmt)!r}, not a call — "
            "this is the truncation bug that broke every context generation"
        )
    assert [s.value.func.id for s in stmts] == ["main"]


@pytest.mark.parametrize(
    "script",
    sorted(p.name for p in SCRIPTS.glob("*.py")),
)
def test_ci_script_entrypoint_is_not_truncated(script: str) -> None:
    """The `ma` truncation hit two scripts, so guard the whole class.

    `generate_context.py` and `apply_review.py` both ended in a bare `ma`
    instead of `main()`. Neither is a SyntaxError, so `compileall` — the only
    gate that reads these files in CI — passed both while every run of the
    quick-note pipeline died at its last line. Any bare name in a `__main__`
    guard is this bug.
    """
    for stmt in _guard_statements(SCRIPTS / script):
        assert not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Name)), (
            f"{script}: __main__ guard runs the bare name "
            f"{ast.unparse(stmt)!r} — a truncated call that raises NameError "
            "only when the script is actually executed"
        )


@pytest.mark.parametrize(
    "script",
    sorted(p.name for p in SCRIPTS.glob("*.py")),
)
def test_ci_script_ends_with_a_newline(script: str) -> None:
    """A missing trailing newline is how both truncations announced themselves."""
    assert (SCRIPTS / script).read_text().endswith("\n"), (
        f"{script} has no trailing newline — check its last line is complete"
    )


def test_generate_context_defines_every_name_its_guard_uses() -> None:
    """A truncated identifier in the guard would be a NameError at runtime only."""
    module = _load("generate_context")
    assert callable(module.main)
