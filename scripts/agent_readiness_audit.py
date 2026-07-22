"""scripts/agent_readiness_audit.py — score this repo's fitness for autonomous agent work.

Scores eight pillars (0-100 each), each pillar built from checks this repo
already has the machinery to answer — no new instrumentation, just reading
signals that already exist (test count, pre-commit config, changelog gates,
graphify presence, doctor script, CI workflow count, observability wiring,
loop registry). Mirrors the style of ``agent/loop_registry.py``'s
``loop_readiness()`` scorer (weighted dimensions -> 0-100 -> letter grade),
applied to the whole repo rather than just the loop fleet.

Usage::

    python scripts/agent_readiness_audit.py            # print report
    python scripts/agent_readiness_audit.py --check     # exit 1 if score < threshold
    python scripts/agent_readiness_audit.py --write     # also write docs/AGENT_READINESS.md
"""
from __future__ import annotations

import argparse
import subprocess  # nosec B404 - fixed argv, no shell, used for `git ls-files` only
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent

PILLARS = (
    "style_and_validation",
    "build_system",
    "testing",
    "documentation",
    "dev_environment",
    "observability",
    "security",
    "task_discovery",
)


@dataclass
class PillarResult:
    name: str
    score: int  # 0-100
    findings: list[str] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)


@dataclass
class ReadinessReport:
    pillars: list[PillarResult]
    score: int
    grade: str

    def as_markdown(self) -> str:
        lines = [
            "# Agent Readiness Report",
            "",
            f"**Overall score: {self.score}/100 (grade {self.grade})**",
            "",
            "Self-generated — run `python scripts/agent_readiness_audit.py` to refresh.",
            "",
            "> **Read this as a floor, not a ceiling.** Each pillar checks for the "
            "*presence* of specific infrastructure (a file, a Makefile target, a "
            "wired-in module) — it does not judge the quality of what it finds. A "
            "perfect score means the expected scaffolding exists, not that the "
            "codebase is flawless; treat drops in this score as real regressions, "
            "but treat a maxed score as \"nothing obviously missing,\" not \"done.\"",
            "",
        ]
        for pillar in self.pillars:
            lines.append(f"## {pillar.name.replace('_', ' ').title()} — {pillar.score}/100")
            lines.append("")
            for finding in pillar.findings:
                lines.append(f"- {finding}")
            if pillar.fixes:
                lines.append("")
                lines.append("**Suggested fixes:**")
                for fix in pillar.fixes:
                    lines.append(f"- {fix}")
            lines.append("")
        return "\n".join(lines)


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 45:
        return "D"
    return "F"


def _tracked_files(pattern: str) -> list[str]:
    try:
        out = subprocess.run(  # nosec B603,B607 - fixed argv, list form, no shell
            ["git", "ls-files", pattern], cwd=REPO_ROOT, capture_output=True, text=True, timeout=15,
        )
        return [line for line in out.stdout.splitlines() if line]
    except (subprocess.SubprocessError, OSError):
        return []


def score_style_and_validation() -> PillarResult:
    findings, fixes = [], []
    score = 40
    if (REPO_ROOT / ".pre-commit-config.yaml").exists():
        score += 30
        findings.append("`.pre-commit-config.yaml` present — fast local feedback before CI.")
    else:
        fixes.append("Add `.pre-commit-config.yaml` so agents get syntax/secret feedback in seconds, not CI minutes.")
    if (REPO_ROOT / ".claude" / "hooks" / "pre-commit").exists():
        score += 30
        findings.append("`.claude/hooks/pre-commit` guardrail hook present.")
    return PillarResult("style_and_validation", min(score, 100), findings, fixes)


def score_build_system() -> PillarResult:
    findings, fixes = [], []
    score = 20
    makefile = REPO_ROOT / "Makefile"
    if makefile.exists():
        text = makefile.read_text(errors="ignore")
        score += 20
        findings.append("Makefile present with named targets — agents don't need tribal-knowledge build steps.")
        for target in ("test", "lint", "doctor", "ci-parity"):
            if f"\n{target}:" in text or text.startswith(f"{target}:"):
                score += 15
                findings.append(f"`make {target}` target available.")
    return PillarResult("build_system", min(score, 100), findings, fixes)


def score_testing() -> PillarResult:
    findings, fixes = [], []
    py_tests = _tracked_files("tests/test_*.py")
    js_tests = _tracked_files("frontend/src/**/*.test.js*")
    score = 0
    if py_tests:
        score += 50
        findings.append(f"{len(py_tests)} Python test files under tests/.")
    else:
        fixes.append("Add tests/test_*.py coverage.")
    if js_tests:
        score += 20
        findings.append(f"{len(js_tests)} frontend test files.")
    if (REPO_ROOT / "agent" / "loop.py").exists():
        # AGENT_EMPIRICAL_VERIFY is the empirical (run-the-tests) verification gate.
        text = (REPO_ROOT / "agent" / "loop.py").read_text(errors="ignore")
        if "AGENT_EMPIRICAL_VERIFY" in text:
            score += 30
            findings.append("Agent loop can run empirical (compile + scoped pytest) verification on its own changes.")
        else:
            fixes.append("Have the agent loop run tests on its own changes, not just judge the diff.")
    return PillarResult("testing", min(score, 100), findings, fixes)


def score_documentation() -> PillarResult:
    findings, fixes = [], []
    score = 0
    for doc, points in (("CLAUDE.md", 25), ("AGENTS.md", 20), ("ARCHITECTURE.md", 15),
                        ("ENGINEERING_STANDARDS.md", 15), ("CONTRIBUTING.md", 10), ("CHANGELOG.md", 15)):
        if (REPO_ROOT / doc).exists():
            score += points
            findings.append(f"`{doc}` present.")
        else:
            fixes.append(f"Add `{doc}`.")
    return PillarResult("documentation", min(score, 100), findings, fixes)


def score_dev_environment() -> PillarResult:
    findings, fixes = [], []
    score = 20
    if (REPO_ROOT / "requirements.txt").exists():
        score += 20
        findings.append("`requirements.txt` pins the Python dependency surface.")
    if (REPO_ROOT / "frontend" / "package-lock.json").exists():
        score += 20
        findings.append("Frontend has a committed lockfile.")
    if (REPO_ROOT / ".devcontainer").exists():
        score += 20
        findings.append(".devcontainer present — reproducible dev environment.")
    if (REPO_ROOT / "agent" / "doctor.py").exists():
        score += 20
        findings.append("`agent/doctor.py` gives agents a programmatic environment diagnostic.")
    return PillarResult("dev_environment", min(score, 100), findings, fixes)


def score_observability() -> PillarResult:
    findings, fixes = [], []
    score = 10
    if (REPO_ROOT / "langfuse_obs.py").exists():
        score += 40
        findings.append("Langfuse tracing wired in (`langfuse_obs.py`).")
    if (REPO_ROOT / "services" / "otel_tracing.py").exists():
        score += 30
        findings.append("OpenTelemetry tracing wired in (`services/otel_tracing.py`).")
    if (REPO_ROOT / "packages" / "ai" / "cost_tracker.py").exists():
        text = (REPO_ROOT / "packages" / "ai" / "cost_tracker.py").read_text(errors="ignore")
        if "by_tag" in text:
            score += 20
            findings.append("Cost attribution breaks spend down by task type, not just by model.")
    return PillarResult("observability", min(score, 100), findings, fixes)


def score_security() -> PillarResult:
    findings, fixes = [], []
    score = 20
    if (REPO_ROOT / ".github" / "workflows" / "security-scan.yml").exists():
        score += 30
        findings.append("Dedicated security-scan CI workflow present.")
    if any((REPO_ROOT / ".claude" / "skills" / name).exists()
           for name in ("risky-module-review", "security-review")):
        score += 25
        findings.append("Risky-module-review discipline codified as a skill.")
    if (REPO_ROOT / "agent" / "verification_strategies.py").exists():
        score += 25
        findings.append("Independent cross-verification available for changes touching risky modules.")
    return PillarResult("security", min(score, 100), findings, fixes)


def score_task_discovery() -> PillarResult:
    findings, fixes = [], []
    score = 20
    if (REPO_ROOT / "agent" / "improvement_loop.py").exists():
        score += 25
        findings.append("Automated scanner turns failing tests/FIXMEs into scheduled fix tasks.")
    if (REPO_ROOT / "services" / "issue_triage.py").exists():
        score += 30
        findings.append("Inbound GitHub issues can be auto-classified and routed (opt-in).")
    else:
        fixes.append("Add inbound issue triage so bug reports become routed tasks automatically.")
    if (REPO_ROOT / "services" / "session_retro.py").exists():
        score += 25
        findings.append("Session retrospective mining surfaces recurring agent friction as issues.")
    else:
        fixes.append("Mine past agent sessions for recurring friction, not just live signals.")
    return PillarResult("task_discovery", min(score, 100), findings, fixes)


_SCORERS: dict[str, Callable[[], PillarResult]] = {
    "style_and_validation": score_style_and_validation,
    "build_system": score_build_system,
    "testing": score_testing,
    "documentation": score_documentation,
    "dev_environment": score_dev_environment,
    "observability": score_observability,
    "security": score_security,
    "task_discovery": score_task_discovery,
}


def run_audit() -> ReadinessReport:
    pillars = [_SCORERS[name]() for name in PILLARS]
    overall = round(sum(p.score for p in pillars) / len(pillars))
    return ReadinessReport(pillars=pillars, score=overall, grade=_grade(overall))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit 1 if score is below --threshold.")
    parser.add_argument("--threshold", type=int, default=60)
    parser.add_argument("--write", action="store_true", help="Write docs/AGENT_READINESS.md.")
    args = parser.parse_args()

    report = run_audit()
    print(f"Agent Readiness: {report.score}/100 (grade {report.grade})")
    for pillar in report.pillars:
        print(f"  {pillar.name}: {pillar.score}/100")

    if args.write:
        out_path = REPO_ROOT / "docs" / "AGENT_READINESS.md"
        out_path.write_text(report.as_markdown())
        print(f"Wrote {out_path}")

    if args.check and report.score < args.threshold:
        print(f"FAIL: score {report.score} below threshold {args.threshold}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
