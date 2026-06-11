#!/usr/bin/env python3
"""scripts/generate_specialist_skill_matrix.py — Specialist × Skill matrix.

Generates docs/specialists-skills-matrix.md *from code* (truth-reconciliation
brief #7): for every specialist family it records the bound skills, the skill
categories it participates in, its default runtime, and whether a test in tests/
exercises that family. Run:

    python scripts/generate_specialist_skill_matrix.py            # write the doc
    python scripts/generate_specialist_skill_matrix.py --check    # CI: fail if stale

The matrix is derived, never hand-written, so it can't drift from the code.
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path
from typing import Any, get_args

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from models.company_graph import SpecialistFamily  # noqa: E402
from services.skill_bindings import get_skill_bindings  # noqa: E402
from services.specialist import SpecialistService  # noqa: E402

_DOC_PATH = _ROOT / "docs" / "specialists-skills-matrix.md"
_TESTS_DIR = _ROOT / "tests"


def _families() -> list[str]:
    return list(get_args(SpecialistFamily))


def _test_evidence_index() -> dict[str, list[str]]:
    """Map family -> sorted list of test files that mention it (quoted token)."""
    index: dict[str, list[str]] = {}
    families = _families()
    for path in sorted(_TESTS_DIR.rglob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for fam in families:
            # Match the family as a quoted literal so "data" doesn't match "metadata".
            if f'"{fam}"' in text or f"'{fam}'" in text:
                index.setdefault(fam, []).append(path.name)
    return index


def build_matrix() -> list[dict[str, Any]]:
    """Return one row per family, derived entirely from code."""
    svc = SpecialistService()
    bindings = get_skill_bindings()
    evidence = _test_evidence_index()

    rows: list[dict[str, Any]] = []
    for fam in _families():
        skills = [s for s in bindings.list_for_family(fam) if getattr(s, "is_enabled", True)]
        skill_ids = sorted(s.skill_id for s in skills)
        categories = sorted({
            getattr(s.category, "value", str(s.category)) for s in skills
        })
        rows.append({
            "family": fam,
            "capabilities": svc._get_default_capabilities(fam),
            "tools": svc._get_default_tools(fam),
            "runtime": svc._resolve_runtime(fam) or "internal_agent",
            "bound_skills": skill_ids,
            "skill_categories": categories,
            "test_files": evidence.get(fam, []),
        })
    return rows


def render_markdown(rows: list[dict[str, Any]]) -> str:
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(rows)
    bound = sum(1 for r in rows if r["bound_skills"])
    tested = sum(1 for r in rows if r["test_files"])
    lines = [
        "# Specialist × Skill Matrix",
        "",
        "> **Generated from code** by `scripts/generate_specialist_skill_matrix.py` — do not edit by hand.",
        f"> Last generated: {now}",
        "",
        f"**{total} specialist families** · {bound} with bound skills · {tested} with test evidence.",
        "",
        "| Family | Bound skills | Skill areas | Runtime | Capabilities | Test evidence |",
        "|--------|--------------|-------------|---------|--------------|---------------|",
    ]
    for r in rows:
        skills = ", ".join(f"`{s}`" for s in r["bound_skills"]) or "— **none**"
        areas = ", ".join(r["skill_categories"]) or "—"
        caps = ", ".join(r["capabilities"][:4]) + ("…" if len(r["capabilities"]) > 4 else "")
        tests = ", ".join(f"`{t}`" for t in r["test_files"]) or "— **none**"
        lines.append(
            f"| `{r['family']}` | {skills} | {areas} | `{r['runtime']}` | {caps} | {tests} |"
        )
    lines.append("")
    lines.append(
        "_Test evidence = a file under `tests/` references the family as a quoted "
        "literal. Authoritative pass/fail is the CI run for the commit that updated "
        "this file._"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the doc is stale")
    args = ap.parse_args()

    content = render_markdown(build_matrix())
    if args.check:
        existing = _DOC_PATH.read_text(encoding="utf-8") if _DOC_PATH.exists() else ""
        # Compare ignoring the volatile "Last generated" line.
        def _strip_ts(s: str) -> str:
            return "\n".join(l for l in s.splitlines() if not l.startswith("> Last generated:"))
        if _strip_ts(existing) != _strip_ts(content):
            print("specialists-skills-matrix.md is stale — run the generator.", file=sys.stderr)
            return 1
        print("specialists-skills-matrix.md is up to date.")
        return 0

    _DOC_PATH.write_text(content, encoding="utf-8")
    print(f"Wrote {_DOC_PATH.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
