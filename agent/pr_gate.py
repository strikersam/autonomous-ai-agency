"""Checks an agent's changes must pass before it may open a pull request.

The first agent PRs to reach GitHub (2026-10-04, #1656–#1660) were all red or
empty: a test importing a module that was never written, three root-level
``async_queue.py`` files with no tests, no changelog entry. CI caught them only
after a PR existed. This gate runs the same basic checks in the agent's own
clone first, and its findings go back into the task so the next attempt can
fix them.

The second wave (2026-10-06/07) showed the gate itself had a blind spot: it
only looked at ``.py`` files. #1694 shipped invented URLs in a root
``llms.txt``; #1696, asked to add internal links, replaced ``App.js`` with a
placeholder and cut 1,490 lines of ``index.html``. Both passed with zero
blockers. The checks below cover every changed file, compare the change with
the plan, and record what actually ran so the PR can carry the evidence
(docs/intent/2026-10-08-agent-pr-quality.md).
"""

from __future__ import annotations

import fnmatch
import logging
import os
import re
import subprocess  # nosec B404 - fixed argv, list form, no shell
import sys
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("qwen-proxy")

_TEST_TIMEOUT_S = 300
_CHANGELOGS = ("CHANGELOG.md", "docs/changelog.md")
_PARITY_SCRIPT = "scripts/check_changelog_parity.py"

# Never changed by an agent PR: the security-sensitive modules of CLAUDE.md
# rule 15, the app shell, deploy/CI configuration, and this gate with its
# tests (an agent must not be able to weaken the check on its own work).
PROTECTED_PATHS: tuple[str, ...] = (
    "agent/tools.py", "agent/pr_gate.py", "tests/test_agent_pr_gate.py",
    "key_store.py", "proxy.py", "handlers/v3_auth.py", "packages/auth/*",
    "frontend/src/App.js", "frontend/src/AuthContext.js", "frontend/src/index.js",
    "frontend/public/index.html", "index.html",
    ".github/workflows/*", ".claude/hooks/*", ".claude/settings.json",
    "wrangler.jsonc", "netlify.toml", "render.yaml", "Dockerfile*",
)

# Paths whose change does not need a changelog entry.
_NO_CHANGELOG = ("docs/*", ".claude/state/*", "graphify-out/*", "*.md")
# Paths a plan does not have to name.
_SCOPE_EXEMPT = (*_CHANGELOGS, "graphify-out/*", ".claude/state/*", "docs/plans/agent/*")

# Suites that must pass whenever these paths change, whether or not the agent
# touched a test. The model catalogue tests are what caught #1695 and #1697
# re-adding retired model ids.
_GUARD_TESTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("config/models.yaml", "config/llm/*", "packages/ai/brain_config.py",
         "packages/ai/cost_tracker.py", "router/*"),
        ("tests/test_one_model_catalogue.py", "tests/test_nvidia_default_model.py",
         "tests/test_model_router.py"),
    ),
)

# A file is "gutted" when it loses at least this many lines and more than
# twice what it gains. From #1696: App.js -62/+26, index.html -1490/+51.
_GUT_MIN_DELETED = 40
_REMOVAL_WORDS = re.compile(r"\b(delete|remove|drop|rewrite|replace|deprecate)\b", re.I)
_JUDGE_REJECT = {"REJECTED", "BLOCKED"}


@dataclass
class GateReport:
    """Blockers stop the PR; evidence is every check that ran and how it ended."""

    blockers: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blockers


@dataclass
class _Ctx:
    root: Path
    changed: list[str]
    goal: str
    planned: list[str] | None
    base_ref: str | None
    report: GateReport


def _norm(path: str) -> str:
    return path.strip().replace("\\", "/").removeprefix("./").rstrip("/")


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def _is_test(path: str) -> bool:
    name = Path(path).name
    return name.startswith("test_") or "/tests/" in f"/{path}"


def _run(argv: list[str], root: Path, env: dict[str, str] | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(  # nosec B603 - fixed interpreter argv, list form
            argv, cwd=root, capture_output=True, text=True, timeout=_TEST_TIMEOUT_S, env=env,
        )
    except subprocess.TimeoutExpired:
        return 1, f"timed out after {_TEST_TIMEOUT_S}s"
    except OSError as exc:
        return 127, f"could not run {argv[0]}: {exc}"
    return proc.returncode, (proc.stdout + proc.stderr)[-2000:]


def _last_line(out: str) -> str:
    lines = [ln.strip() for ln in out.strip().splitlines() if ln.strip()]
    return lines[-1][:200] if lines else "no output"


def _check_protected(ctx: _Ctx) -> None:
    hit = [f for f in ctx.changed if _matches(f, PROTECTED_PATHS)]
    if hit:
        ctx.report.blockers.append(
            "Protected paths changed: " + ", ".join(hit) + ". An agent PR may not change "
            "auth, the app shell, deploy/CI config or this gate; leave them untouched and "
            "say in the task result what a human needs to change there."
        )
    else:
        ctx.report.evidence.append("protected paths: none touched")


def _check_scope(ctx: _Ctx) -> None:
    if not ctx.planned:
        ctx.report.evidence.append("scope: plan named no files, not checked")
        return
    planned = set(ctx.planned)

    def in_plan(path: str) -> bool:
        return any(path == p or path.startswith(p + "/") for p in planned)

    stray = [f for f in ctx.changed
             if not in_plan(f) and not _is_test(f) and not _matches(f, _SCOPE_EXEMPT)]
    if stray:
        ctx.report.blockers.append(
            "Changed files the plan did not name: " + ", ".join(stray[:10])
            + ". Revert them, or re-plan so the change is reviewed against what it touches."
        )
    else:
        ctx.report.evidence.append(f"scope: all changes inside the {len(planned)} planned path(s)")


def _numstat(ctx: _Ctx) -> dict[str, tuple[int, int]] | None:
    rc, out = _run(["git", "diff", "--numstat", ctx.base_ref or "", "--", *ctx.changed], ctx.root)
    if rc != 0:
        return None
    stats: dict[str, tuple[int, int]] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            stats[parts[2]] = (int(parts[0]), int(parts[1]))
    return stats


def _check_destructive(ctx: _Ctx) -> None:
    if not ctx.base_ref:
        return
    stats = _numstat(ctx)
    if stats is None:
        ctx.report.blockers.append(f"Could not diff against {ctx.base_ref}, so the size of the change is unknown.")
        return
    removal_asked = bool(_REMOVAL_WORDS.search(ctx.goal))
    gutted = []
    for path, (added, deleted) in sorted(stats.items()):
        deleted_file = not (ctx.root / path).exists()
        if deleted_file or (deleted >= _GUT_MIN_DELETED and deleted > 2 * added):
            if removal_asked and path in (ctx.planned or []):
                continue
            gutted.append(f"{path} (-{deleted}/+{added}{', deleted' if deleted_file else ''})")
    if gutted:
        ctx.report.blockers.append(
            "Change removes far more than it adds: " + ", ".join(gutted)
            + ". The goal did not ask for this removal; restore the existing code and make an additive change."
        )
    else:
        added = sum(a for a, _ in stats.values())
        deleted = sum(d for _, d in stats.values())
        ctx.report.evidence.append(f"size: +{added}/-{deleted} across {len(stats)} file(s), nothing gutted")


_SKIP_MARKERS = re.compile(
    r"pytest\.mark\.(skip|xfail)|pytest\.(skip|xfail)\(|unittest\.skip|"
    r"\b(it|test|describe)\.skip\(|\bx(it|describe|test)\("
)
_ASSERTION = re.compile(r"^\s*(assert\b|self\.assert|expect\()")


def _check_tests_not_weakened(ctx: _Ctx) -> None:
    """An agent must not weaken the checks on its own work (playbook: protect the loop)."""
    if not ctx.base_ref:
        return
    weakened: list[str] = []
    for path in (f for f in ctx.changed if _is_test(f) or ".test." in f):
        if _run(["git", "cat-file", "-e", f"{ctx.base_ref}:{path}"], ctx.root)[0] != 0:
            continue  # a new test file cannot weaken an existing check
        rc, out = _run(["git", "diff", "-U0", ctx.base_ref, "--", path], ctx.root)
        if rc != 0:
            continue
        lines = [ln for ln in out.splitlines() if ln[:1] in "+-" and ln[:3] not in ("+++", "---")]
        lost = sum(bool(_ASSERTION.match(ln[1:])) for ln in lines if ln[0] == "-")
        gained = sum(bool(_ASSERTION.match(ln[1:])) for ln in lines if ln[0] == "+")
        skips = sum(bool(_SKIP_MARKERS.search(ln)) for ln in lines if ln[0] == "+")
        if lost > gained or skips:
            weakened.append(f"{path} (assertions -{lost}/+{gained}, skips added: {skips})")
    if weakened:
        ctx.report.blockers.append(
            "Existing tests were weakened: " + ", ".join(weakened)
            + ". Fix the code, not the test; add new tests instead of loosening old ones."
        )


def _check_changelog(ctx: _Ctx) -> None:
    needs = [f for f in ctx.changed if not _is_test(f) and not _matches(f, _NO_CHANGELOG)
             and f not in _CHANGELOGS]
    if not needs:
        return
    missing = [c for c in _CHANGELOGS if c not in ctx.changed]
    if missing:
        ctx.report.blockers.append(
            "Behaviour change without a changelog entry: add the same entry under "
            f"'## [Unreleased]' in {' and '.join(_CHANGELOGS)} (missing: {', '.join(missing)})."
        )
        return
    if (ctx.root / _PARITY_SCRIPT).exists():
        rc, out = _run([sys.executable, _PARITY_SCRIPT], ctx.root)
        if rc != 0:
            ctx.report.blockers.append(f"Changelog files differ (they must be byte-identical):\n{out}")
            return
    ctx.report.evidence.append("changelog: entry present in both files")


def _guard_tests(ctx: _Ctx) -> list[str]:
    picked: list[str] = []
    for paths, tests in _GUARD_TESTS:
        if any(_matches(f, paths) for f in ctx.changed):
            picked += [t for t in tests if (ctx.root / t).exists() and t not in picked]
    return picked


def _check_python(ctx: _Ctx) -> bool:
    """py_compile, then tests: the agent's own plus the guard suites. False stops the gate."""
    py = [f for f in ctx.changed if f.endswith(".py") and (ctx.root / f).exists()]
    source = [f for f in py if not _is_test(f)]
    tests = [f for f in py if _is_test(f)]
    if py:
        rc, out = _run([sys.executable, "-m", "py_compile", *py], ctx.root)
        if rc != 0:
            ctx.report.blockers.append(f"Changed files do not compile:\n{out}")
            return False
        ctx.report.evidence.append(f"py_compile: {len(py)} file(s) OK")
    if source and not tests:
        ctx.report.blockers.append(
            "Code changed without tests: add or update tests/test_<module>.py "
            f"covering {', '.join(source[:5])}."
        )
    to_run = tests + [t for t in _guard_tests(ctx) if t not in tests]
    if to_run:
        rc, out = _run([sys.executable, "-m", "pytest", "-x", "-q", *to_run], ctx.root)
        if rc != 0:
            ctx.report.blockers.append(f"Tests fail:\n{out}")
        else:
            ctx.report.evidence.append(f"pytest {' '.join(to_run)}: {_last_line(out)}")
    return True


def _check_frontend(ctx: _Ctx) -> None:
    src = [f for f in ctx.changed if f.startswith("frontend/src/") and f.endswith((".js", ".jsx"))
           and (ctx.root / f).exists()]
    if not src:
        return
    frontend = ctx.root / "frontend"
    if not (frontend / "node_modules").is_dir():
        ctx.report.evidence.append(
            f"frontend: tests and build NOT run for {len(src)} file(s) (no frontend/node_modules in this clone)"
        )
        return
    env = {**os.environ, "CI": "true"}
    rel = [f.removeprefix("frontend/") for f in src]
    rc, out = _run(["npx", "react-scripts", "test", "--watchAll=false", "--passWithNoTests",
                    "--findRelatedTests", *rel], frontend, env)
    if rc != 0:
        ctx.report.blockers.append(f"Frontend tests fail:\n{out}")
        return
    ctx.report.evidence.append(f"frontend tests (related to {len(src)} file(s)): passed")
    rc, out = _run(["npm", "run", "build"], frontend, env)
    if rc != 0:
        ctx.report.blockers.append(f"Frontend build fails:\n{out}")
    else:
        ctx.report.evidence.append("frontend build: succeeded")


def run_pr_gate(
    root: str | Path,
    changed_files: list[str],
    *,
    goal: str = "",
    planned_files: list[str] | None = None,
    base_ref: str | None = None,
) -> GateReport:
    """Run every pre-PR check over ``changed_files`` and report blockers and evidence.

    ``planned_files`` enables the scope check and ``base_ref`` the size check;
    callers that pass neither get the original file-level checks only.
    """
    changed = sorted({_norm(f) for f in changed_files if f.strip()})
    planned = sorted({_norm(f) for f in planned_files if f.strip()}) if planned_files else None
    ctx = _Ctx(Path(root), changed, goal, planned, base_ref, GateReport())
    if not changed:
        return ctx.report
    _check_protected(ctx)
    _check_scope(ctx)
    _check_destructive(ctx)
    _check_tests_not_weakened(ctx)
    if _check_python(ctx):
        _check_frontend(ctx)
        _check_changelog(ctx)
    if ctx.report.blockers:
        log.info("pr_gate: %d blocker(s) for %d changed file(s)", len(ctx.report.blockers), len(changed))
    return ctx.report


def pr_blockers(root: str | Path, changed_files: list[str], **kwargs: object) -> list[str]:
    """Reasons the change is not ready for a PR; empty when it may open one."""
    return run_pr_gate(root, changed_files, **kwargs).blockers  # type: ignore[arg-type]


def judge_blockers(judge: dict | None) -> list[str]:
    """A judge that rejected the diff, could not answer, or failed correctness blocks the PR."""
    if not judge:
        return []
    verdict = str(judge.get("verdict", "")).upper()
    failed = [k for k in ("correctness", "security") if str(judge.get(k, "")).upper() == "FAIL"]
    if verdict in _JUDGE_REJECT or failed:
        why = verdict if verdict in _JUDGE_REJECT else "FAIL on " + ", ".join(failed)
        return [f"The judge did not approve the diff ({why}): {str(judge.get('notes', ''))[:500]}"]
    return []


def resolve_base(root: str | Path, base_branch: str, n_commits: int) -> str | None:
    """The commit the agent's work started from: merge-base with origin/<base>, else HEAD~n."""
    root = Path(root)
    rc, head = _run(["git", "rev-parse", "HEAD"], root)
    if rc != 0:
        return None
    rc, mb = _run(["git", "merge-base", "HEAD", f"origin/{base_branch}"], root)
    if rc == 0 and mb.strip() and mb.strip() != head.strip():
        return mb.strip()
    if n_commits > 0:
        rc, sha = _run(["git", "rev-parse", "--verify", f"HEAD~{n_commits}"], root)
        if rc == 0:
            return sha.strip()
    return None


def review_diff(root: str | Path, base_ref: str | None, max_chars: int = 12000) -> str:
    """The unified diff the judge reviews, truncated to ``max_chars``."""
    if not base_ref:
        return ""
    rc, _ = _run(["git", "rev-parse", "--verify", base_ref], Path(root))
    if rc != 0:
        return ""
    try:
        proc = subprocess.run(  # nosec B603 B607 - fixed git argv, list form
            ["git", "diff", "--stat", "--patch", base_ref], cwd=root,
            capture_output=True, text=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    out = proc.stdout
    return out if len(out) <= max_chars else out[:max_chars] + f"\n… diff truncated ({len(out)} chars total)"


def render_pr_body(
    goal: str,
    plan: object | None,
    report: GateReport | None,
    judge: dict | None,
    commits: list[str],
) -> str:
    """PR description carrying the evidence a reviewer needs: plan, checks run, verdict."""
    out = ["🤖 Automated PR created by AI Agent.", "", "## Goal", goal or "(none recorded)", ""]
    steps = list(getattr(plan, "steps", None) or [])
    if steps:
        out += ["## Plan"]
        for s in steps:
            files = f" — `{'`, `'.join(s.files)}`" if s.files else ""
            check = f" (done when: {s.acceptance})" if getattr(s, "acceptance", "") else ""
            out.append(f"{s.id}. {s.description}{files}{check}")
        out.append("")
    out += ["## Pre-PR checks (run in the agent's clone)"]
    out += [f"- {e}" for e in (report.evidence if report else [])] or ["- (no checks recorded)"]
    if judge:
        out += ["", "## Judge", f"- verdict: {judge.get('verdict', '?')}, correctness: "
                f"{judge.get('correctness', '?')}, security: {judge.get('security', '?')}"]
        if judge.get("notes"):
            out.append(f"- notes: {str(judge['notes'])[:800]}")
    out += ["", "## Commits"] + [f"- `{c[:7]}`" for c in commits]
    return "\n".join(out)


def review_policy(root: str | Path, max_chars: int = 4000) -> str:
    """The target repository's REVIEW.md, if it has one, for the judge to review against."""
    path = Path(root) / "REVIEW.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return text if len(text) <= max_chars else text[:max_chars] + "\n… (truncated)"


PLAN_DIR = "docs/plans/agent"


def plan_artifact(plan: object, today: str) -> tuple[str, str]:
    """The plan as a committed file (playbook: plan.md joins the audit trail the PR is checked against)."""
    goal = str(getattr(plan, "goal", "") or "untitled")
    slug = re.sub(r"[^a-z0-9]+", "-", goal.lower()).strip("-")[:60].rstrip("-") or "plan"
    out = [f"# Plan: {goal}", "", f"Written by the agent on {today}; the PR is reviewed against it.", ""]
    steps = list(getattr(plan, "steps", None) or [])
    files = sorted({f for s in steps for f in s.files})
    out += ["## Files that change"] + ([f"- `{f}`" for f in files] or ["- (none named)"]) + [""]
    out += ["## Order of work"]
    for s in steps:
        done = f" Done when: {s.acceptance}" if getattr(s, "acceptance", "") else ""
        out.append(f"{s.id}. {s.description}{done}")
    risks = list(getattr(plan, "risks", None) or [])
    out += ["", "## Risks"] + ([f"- {r}" for r in risks] or ["- (none recorded)"])
    return f"{PLAN_DIR}/{today}-{slug}.md", "\n".join(out) + "\n"
