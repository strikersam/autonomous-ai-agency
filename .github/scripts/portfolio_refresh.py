#!/usr/bin/env python3
"""Scheduled portfolio intelligence sweep.

Run by `.github/workflows/portfolio-refresh.yml` on a cron. Builds the portfolio
from real signals (roadmap backlog, bug log, open GitHub PRs/issues via the
Actions token, optional research trends), writes a WSJF-ranked digest to the
job summary, and — if BACKEND_URL is set — pings the deployed backend so the
live dashboard re-sweeps.

Loads the portfolio modules directly (stubbing the `agents` package) so it only
needs httpx, not the full app dependency tree.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    pkg = types.ModuleType("agents")
    pkg.__path__ = [str(ROOT / "agents")]
    sys.modules["agents"] = pkg
    _load("agents.agile_sprints", "agents/agile_sprints.py")
    _load("agents.portfolio", "agents/portfolio.py")
    pi = _load("agents.portfolio_intelligence", "agents/portfolio_intelligence.py")

    repo = os.environ.get("PORTFOLIO_REPO", pi.DEFAULT_REPO)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT")
    want_research = os.environ.get("PORTFOLIO_RESEARCH", "0") == "1"

    intel = pi.PortfolioIntelligence(repo=repo, root=ROOT, github_token=token)
    mgr = intel.build(include_github=True, include_research=want_research)
    ranked = mgr.prioritized()
    metrics = mgr.metrics()

    lines = [
        f"### 🧭 Portfolio refresh — {len(ranked)} initiatives",
        "",
        f"**Sources:** " + ", ".join(f"{n} {s}" for s, n in intel.last_build.items()) or "none",
        f"**Avg WSJF:** {metrics.average_wsjf:.2f} · **Total Cost of Delay:** {metrics.total_cost_of_delay}",
        "",
        "| # | Initiative | Source | WSJF | CoD | Size |",
        "|---|------------|--------|------|-----|------|",
    ]
    for i, init in enumerate(ranked[:20], 1):
        title = init.title.replace("|", "\\|")[:70]
        lines.append(f"| {i} | {title} | {init.source} | {init.wsjf:.2f} | {init.cost_of_delay} | {init.job_size} |")

    summary = "\n".join(lines)
    print(summary)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(summary + "\n")

    # Bust the deployed backend cache so the live dashboard re-sweeps.
    backend = os.environ.get("BACKEND_URL", "").rstrip("/")
    if backend:
        try:
            import httpx
            r = httpx.post(f"{backend}/api/portfolio/refresh", timeout=30.0)
            print(f"Backend refresh: {r.status_code}")
        except Exception as exc:  # non-fatal
            print(f"Backend refresh failed (non-fatal): {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
