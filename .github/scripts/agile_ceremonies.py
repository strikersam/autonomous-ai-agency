#!/usr/bin/env python3
"""Scheduled agile ceremonies digest.

Run by `.github/workflows/agile-ceremonies.yml` on a cron. Reads
`.claude/state/active-tasks.md` (the live cross-session task tracker) and
produces a daily standup, a weekly backlog retrospective, or a WSJF-allocated
sprint plan as a markdown digest written to the job summary.

Loads the agile/portfolio modules directly (stubbing the `agents` package) so
it only needs httpx, matching `.github/scripts/portfolio_refresh.py`.
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TASKS_FILE = ROOT / ".claude" / "state" / "active-tasks.md"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("qwen-proxy")


def _load(name: str, rel: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_summary(markdown: str) -> None:
    log.info(markdown)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ceremony", choices=["standup", "retro", "plan"])
    parser.add_argument(
        "--capacity",
        type=int,
        default=int(os.environ.get("AGILE_SPRINT_CAPACITY", "20")),
        help="Story-point capacity for the 'plan' ceremony (default: 20).",
    )
    args = parser.parse_args()

    pkg = types.ModuleType("agents")
    pkg.__path__ = [str(ROOT / "agents")]
    sys.modules["agents"] = pkg
    agile_sprints = _load("agents.agile_sprints", "agents/agile_sprints.py")
    _load("agents.portfolio", "agents/portfolio.py")
    pi = _load("agents.portfolio_intelligence", "agents/portfolio_intelligence.py")
    ac = _load("agents.agile_ceremonies", "agents/agile_ceremonies.py")

    tasks_md = TASKS_FILE.read_text(encoding="utf-8")

    if args.ceremony == "standup":
        report = ac.generate_standup(tasks_md)
        _write_summary(report.to_markdown())
    elif args.ceremony == "retro":
        retro = ac.generate_backlog_retro(tasks_md)
        _write_summary(ac.retrospective_to_markdown(retro, "Weekly Backlog Retro"))
    else:  # plan
        repo = os.environ.get("PORTFOLIO_REPO", pi.DEFAULT_REPO)
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT")
        want_research = os.environ.get("PORTFOLIO_RESEARCH", "0") == "1"

        intel = pi.PortfolioIntelligence(repo=repo, root=ROOT, github_token=token)
        portfolio = intel.build(include_github=True, include_research=want_research)
        agile = agile_sprints.AgileManager()

        sprint_name = f"Sprint {datetime.now(timezone.utc):%G-W%V}"
        plan = ac.plan_next_sprint(portfolio, agile, name=sprint_name, capacity=args.capacity)
        _write_summary(plan.to_markdown())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
