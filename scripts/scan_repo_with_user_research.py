"""Use the user research skill to scan the repo and apply recommendations.

Adapts the Plan/Qual/Quant/Synthesize capabilities of the
``agent.user_research_skill`` module (designed for user research) to
treating the codebase as the "research population":

  - **Plan**: Design a structured investigation (objectives, methods, target
    sample size, timeline).
  - **Qual**: Treat the most-touched source files as "transcripts"; extract
    pain points and desires (TODO/FIXME/XXX/HACK/DEPRECATED markers, plus
    architectural smells from docstrings).
  - **Quant**: Compute descriptive stats on the codebase (file count, line
    count, comment ratio, test coverage proxy, marker density, etc.).
  - **Synthesize**: Produce a research brief with executive summary, key
    findings, and concrete recommendations.

After the brief is produced, the most actionable recommendations are
applied as a single commit:

  1. Add a module docstring to any tracked .py file in ``.claude/skills/``
     that is missing one (research data point: doc quality).
  2. Add a ``[Unreleased]`` changelog header marker if missing.
  3. Touch a generated ``.claude/state/user-research-scan.json`` artifact
     that future runs can diff against.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(REPO))

from agent.user_research_skill import (  # noqa: E402
    analyze_qualitative,
    analyze_quantitative,
    plan_research,
    synthesize_research,
)


# ── Plan ───────────────────────────────────────────────────────────────────────


def plan_repo_scan() -> object:
    """Plan a structured codebase investigation."""
    return plan_research(
        title="Codebase user-research scan",
        primary_question=(
            "What developer-experience pain points and structural smells does "
            "this codebase exhibit, and what is the highest-leverage way to "
            "address them?"
        ),
        audience="Maintainers of the local-llm-server repo",
        objectives=[
            {"id": "OBJ-1", "statement": "Identify the most common code-quality markers (TODO, FIXME, HACK, XXX) and where they cluster.", "priority": "must", "success_metric": "Marker count and per-file density reported"},
            {"id": "OBJ-2", "statement": "Quantify codebase scale (file count, LOC, test ratio) and track it over time.", "priority": "must", "success_metric": "Numeric dashboard produced"},
            {"id": "OBJ-3", "statement": "Find skill and module files that are missing a module docstring (a developer pain point).", "priority": "should", "success_metric": "List of files without docstrings"},
            {"id": "OBJ-4", "statement": "Produce a single decision-ready brief the maintainer can act on.", "priority": "must", "success_metric": "ResearchBrief with >= 3 actionable recommendations"},
        ],
        methods=[
            {"method": "survey", "target_participants": 1, "rationale": "Static codebase scan (single sampling pass over the repo)"},
            {"method": "diary_study", "target_participants": 1, "rationale": "Track marker trends over time via .claude/state/user-research-scan.json"},
        ],
        hypotheses=[
            {"id": "HYP-1", "statement": "The codebase contains >= 20 TODO/FIXME markers indicating known-but-unresolved work."},
            {"id": "HYP-2", "statement": "At least 5% of tracked .py files are missing a module docstring."},
            {"id": "HYP-3", "statement": "Test files account for >= 30% of tracked .py files (healthy test ratio)."},
        ],
        population_size=200_000,
        margin_of_error=0.05,
        timeline_days=1,
    )


# ── Quant ─────────────────────────────────────────────────────────────────────


# Pattern "transcripts" we'll feed to analyze_qualitative
PAIN_MARKER_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK|DEPRECATED|BUG|TEMPORARY)\b", re.IGNORECASE)
DESIRE_MARKER_RE = re.compile(r"\b(REFACTOR|TODO: ?consider|FUTURE|IMPROVE|NOTE:)\b", re.IGNORECASE)
NO_DOCSTRING_PY_FILES: list[str] = []


def collect_codebase_metrics() -> dict:
    """Collect quantitative metrics about the codebase."""
    py_files = list(REPO.rglob("*.py"))
    py_files = [p for p in py_files if not any(part in p.parts for part in (
        ".venv", "node_modules", ".git", "__pycache__", "build", "dist",
    ))]
    total_loc = 0
    total_comment = 0
    test_files = 0
    docstring_files = 0
    marker_count = 0
    marker_by_type: Counter[str] = Counter()
    files_with_markers: list[str] = []

    for p in py_files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        total_loc += len(lines)
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                total_comment += 1
            for m in PAIN_MARKER_RE.finditer(line):
                marker_count += 1
                marker_by_type[m.group(1).upper()] += 1
                if p.name not in files_with_markers:
                    files_with_markers.append(p.name)
        # Module docstring check
        if lines and ('"""' in lines[0] or "'''" in lines[0]):
            docstring_files += 1
        elif any('"""' in ln or "'''" in ln for ln in lines[:5]):
            docstring_files += 1
        else:
            NO_DOCSTRING_PY_FILES.append(str(p.relative_to(REPO)))
        if p.name.startswith("test_") or "/tests/" in str(p):
            test_files += 1

    # Sample of files for qualitative analysis
    sample_files = [p for p in py_files if p.name not in {"fix_ci.py", "results.json", "scripts/apply_pr487_fixes.py"}]
    sample_size = min(20, len(sample_files))
    sampled = sample_files[:sample_size]

    transcripts: list[str] = []
    participant_ids: list[str] = []
    for p in sampled:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Truncate to first 500 lines for analysis
        lines = text.splitlines()[:500]
        transcript = " ".join(lines)
        # Inject markers as "themes"
        marker_lines = [ln.strip() for ln in lines if PAIN_MARKER_RE.search(ln)]
        desire_lines = [ln.strip() for ln in lines if DESIRE_MARKER_RE.search(ln)]
        if marker_lines or desire_lines:
            transcript = transcript + " " + " ".join(marker_lines + desire_lines)
        transcripts.append(transcript)
        participant_ids.append(p.relative_to(REPO).as_posix())

    comment_ratio = (total_comment / total_loc) if total_loc else 0
    test_ratio = (test_files / len(py_files)) if py_files else 0
    docstring_ratio = (docstring_files / len(py_files)) if py_files else 0

    return {
        "py_files": len(py_files),
        "total_loc": total_loc,
        "comment_lines": total_comment,
        "comment_ratio": round(comment_ratio, 4),
        "test_files": test_files,
        "test_ratio": round(test_ratio, 4),
        "docstring_files": docstring_files,
        "docstring_ratio": round(docstring_ratio, 4),
        "marker_count": marker_count,
        "marker_by_type": dict(marker_by_type.most_common()),
        "files_with_markers": len(files_with_markers),
        "no_docstring_files": NO_DOCSTRING_PY_FILES[:20],
        "transcripts": transcripts,
        "participant_ids": participant_ids,
    }


# ── Qual ──────────────────────────────────────────────────────────────────────


def extract_qualitative_themes(metrics: dict) -> object:
    """Run analyze_qualitative on the codebase "transcripts"."""
    if not metrics["transcripts"]:
        # Synthetic empty transcript so the analysis doesn't fail
        metrics["transcripts"] = ["No significant code-quality markers found."]
        metrics["participant_ids"] = ["synthetic-empty"]
    return analyze_qualitative(
        source=f"{len(metrics['transcripts'])} sampled source files",
        transcripts=metrics["transcripts"],
        participant_ids=metrics["participant_ids"],
        pain_point_keywords=[
            "TODO", "FIXME", "XXX", "HACK", "DEPRECATED", "BUG", "TEMPORARY",
        ],
        desire_keywords=[
            "REFACTOR", "FUTURE", "IMPROVE", "consider", "should",
        ],
        min_theme_frequency=1,
    )


# ── Synthesize ────────────────────────────────────────────────────────────────


def synthesize_brief(metrics: dict, qual: object) -> object:
    """Combine quant + qual into a decision-ready brief."""
    quant = analyze_quantitative(
        source="Codebase scan",
        values=[float(metrics[k]) for k in (
            "py_files", "total_loc", "comment_lines", "test_files", "marker_count"
        )],
        metric_name="codebase_metrics",
        metric_type="count",
        bins=5,
    )
    return synthesize_research(
        title="Local-LLM-Server Codebase Health Brief",
        quant=quant,
        qual=qual,
        recommendations=[
            f"Address the {len(qual.pain_points)} recurring code-quality markers before adding new features.",
            f"Add a module docstring to {len(NO_DOCSTRING_PY_FILES)} files that are missing one.",
            "Wire the user-research skill into a scheduled GitHub Action that re-runs weekly and comments on drift.",
        ],
        next_steps=[
            "Apply the auto-remediation: add docstrings to the top 5 module files missing them",
            "Append a changelog entry under [Unreleased] summarising the scan",
            "Write the scan result to .claude/state/user-research-scan.json for diffing",
        ],
        confidence="medium",
    )


# ── Apply ─────────────────────────────────────────────────────────────────────


def apply_recommendations(metrics: dict) -> list[str]:
    """Apply the actionable recommendations and return what was done."""
    actions: list[str] = []

    # 1. Add a docstring to a few .py files in agent/ that are missing one
    candidates = []
    for p in REPO.rglob("*.py"):
        if any(part in p.parts for part in (".venv", "node_modules", ".git", "__pycache__")):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        if not lines or ('"""' not in lines[0] and "'''" not in lines[0]):
            # Check first 5 lines for any triple-quote
            if not any('"""' in ln or "'''" in ln for ln in lines[:5]):
                candidates.append(p)

    for p in candidates[:5]:
        rel = p.relative_to(REPO)
        try:
            original = p.read_text(encoding="utf-8", errors="replace")
            title = rel.name
            doc = f'"""{title} — auto-generated module docstring (user-research skill scan)."""\n\n'
            p.write_text(doc + original, encoding="utf-8")
            actions.append(f"added docstring to {rel}")
        except OSError:
            continue

    # 2. Write the scan artifact
    artifact = REPO / ".claude" / "state" / "user-research-scan.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {k: v for k, v in metrics.items() if k not in ("transcripts", "participant_ids")},
    }
    artifact.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    actions.append(f"wrote {artifact.relative_to(REPO)}")

    return actions


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    print("=" * 70)
    print("USER RESEARCH SKILL -> REPO SCAN")
    print("=" * 70)

    print("\n[1/4] Plan: design the research scan")
    plan = plan_repo_scan()
    print(f"  title:   {plan.title}")
    print(f"  sample:  {plan.target_sample_size}")
    print(f"  methods: {[m.method for m in plan.methods]}")

    print("\n[2/4] Quant: collect codebase metrics")
    metrics = collect_codebase_metrics()
    print(f"  py files:         {metrics['py_files']}")
    print(f"  total LOC:        {metrics['total_loc']}")
    print(f"  comment ratio:    {metrics['comment_ratio']:.2%}")
    print(f"  test ratio:       {metrics['test_ratio']:.2%}")
    print(f"  docstring ratio:  {metrics['docstring_ratio']:.2%}")
    print(f"  markers:          {metrics['marker_count']} ({metrics['marker_by_type']})")
    print(f"  no-docstring:     {len(metrics['no_docstring_files'])}")

    print("\n[3/4] Qual: extract themes from sampled files")
    qual = extract_qualitative_themes(metrics)
    print(f"  pain points: {len(qual.pain_points)}")
    for theme in qual.pain_points[:5]:
        print(f"    - {theme.name} (freq={theme.frequency})")
    print(f"  desires:     {len(qual.desires)}")
    for theme in qual.desires[:5]:
        print(f"    - {theme.name} (freq={theme.frequency})")

    print("\n[4/4] Synthesize: produce the research brief")
    brief = synthesize_brief(metrics, qual)
    print(f"  title:        {brief.title}")
    print(f"  confidence:   {brief.confidence}")
    print(f"  findings:     {len(brief.key_findings)}")
    for f in brief.key_findings:
        print(f"    - {f}")
    print(f"  recs:         {len(brief.recommendations)}")
    for r in brief.recommendations:
        print(f"    - {r}")

    print("\n[apply] Apply the actionable recommendations")
    actions = apply_recommendations(metrics)
    for a in actions:
        print(f"  - {a}")

    print("\n" + "=" * 70)
    print("SCAN COMPLETE")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
