"""Read-only inventory for the /drill skill: what is open, how it is classified, what is red.

Phase 1 of `.claude/skills/drill/SKILL.md`. It never writes to GitHub: it lists
open PRs and issues, sorts each into the category whose handling rules the skill
spells out, reports CI and merge state per PR head, and names every workflow
whose latest run on master failed (step 4, "nothing else to fix").

Data comes from ``gh api`` (the GitHub CLI, or Claude Code's built-in client in
cloud sessions), so it runs wherever the skill does.

    python scripts/drill_inventory.py                # markdown report
    python scripts/drill_inventory.py --json         # machine-readable
"""
from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404 - fixed gh argv, list form
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

DEFAULT_REPO = "strikersam/autonomous-ai-agency"
# A PR pushed this recently on a branch the drill did not open may belong to a
# session that is still working on it; the skill reports it instead of touching it.
IN_FLIGHT_HOURS = 2
FAILING = {"failure", "timed_out", "cancelled", "action_required", "startup_failure"}
PENDING = {"queued", "in_progress", "waiting", "requested", "pending"}
AUTOMATION_PREFIXES = (
    "claude/daily-automation-", "claude/harness-scan-", "claude/context-issue-",
)


def gh_json(path: str) -> Any:
    """GET ``path`` from the GitHub API through ``gh api`` and decode the JSON."""
    out = subprocess.run(  # nosec B603 B607 - fixed argv, no shell
        ["gh", "api", path], check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out or "null")


def classify_pr(pr: dict[str, Any], own_branch: str = "") -> str:
    """Return the drill category for an open pull request.

    ``own_branch`` is the branch the drill itself works on: its PR is ``own``,
    never mistaken for another session's in-flight work.
    """
    ref = pr.get("head", {}).get("ref", "")
    author = pr.get("user", {}).get("login", "")
    if own_branch and ref == own_branch:
        return "own"
    if author == "dependabot[bot]" or ref.startswith("dependabot/"):
        return "dependabot"
    if ref.startswith("agent/"):
        return "agent"
    if ref.startswith(AUTOMATION_PREFIXES):
        return "automation"
    if ref.startswith("claude/"):
        return "session"
    return "human"


def classify_issue(issue: dict[str, Any]) -> str:
    """Return the drill category for an open issue."""
    labels = {lbl.get("name", "") for lbl in issue.get("labels", [])}
    title = issue.get("title", "")
    if "quick-note:rejected" in labels:
        return "quick-note-rejected"
    if title.startswith("quick-note:"):
        return "quick-note"
    if labels & {"routine-backlog", "trend-digest", "catalogue-drift"}:
        return "routine"
    if labels & {"agency-escalation", "auto-detected"} or "nightly regression" in title:
        return "automation-bug"
    if "bug" in labels:
        return "bug"
    return "other"


def summarize_checks(check_runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse check runs into ``{state, failing, pending}``.

    A check name can appear more than once (re-runs); the newest run of each name
    decides its state, so a failure that was re-run green does not count.
    """
    latest: dict[str, dict[str, Any]] = {}
    for run in check_runs:
        name = run.get("name", "")
        if name not in latest or (run.get("started_at") or "") > (latest[name].get("started_at") or ""):
            latest[name] = run
    failing = sorted(n for n, r in latest.items() if r.get("conclusion") in FAILING)
    pending = sorted(n for n, r in latest.items()
                     if r.get("conclusion") is None and r.get("status") in PENDING)
    state = "red" if failing else "pending" if pending else "green"
    return {"state": state, "failing": failing, "pending": pending}


def still_red_workflows(runs: list[dict[str, Any]]) -> list[str]:
    """Workflows whose most recent finished run on the branch failed.

    A cancelled run is skipped, not counted: on master it is almost always a
    run superseded by a newer push (concurrency cancel), which says nothing
    about whether the workflow is broken. The newest run that actually
    finished decides.
    """
    newest: dict[str, dict[str, Any]] = {}
    for run in runs:
        if run.get("status") != "completed" or run.get("conclusion") == "cancelled":
            continue
        name = run.get("name", "")
        if name not in newest or run.get("created_at", "") > newest[name].get("created_at", ""):
            newest[name] = run
    return sorted(n for n, r in newest.items() if r.get("conclusion") in FAILING)


def is_in_flight(pr: dict[str, Any], category: str, now: datetime) -> bool:
    """True for a session PR updated within IN_FLIGHT_HOURS — another session may own it."""
    if category != "session":
        return False
    updated = datetime.fromisoformat(pr.get("updated_at", "1970-01-01T00:00:00Z").replace("Z", "+00:00"))
    return now - updated < timedelta(hours=IN_FLIGHT_HOURS)


def current_branch() -> str:
    """The checked-out git branch, or "" outside a work tree."""
    proc = subprocess.run(  # nosec B603 B607 - fixed argv, no shell
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def collect(repo: str, now: datetime, own_branch: str = "") -> dict[str, Any]:
    """Gather the inventory from GitHub (read-only)."""
    prs = []
    for pr in gh_json(f"repos/{repo}/pulls?state=open&per_page=100") or []:
        full = gh_json(f"repos/{repo}/pulls/{pr['number']}")
        runs = gh_json(f"repos/{repo}/commits/{pr['head']['sha']}/check-runs?per_page=100")
        category = classify_pr(pr, own_branch)
        prs.append({
            "number": pr["number"], "title": pr["title"], "branch": pr["head"]["ref"],
            "draft": pr.get("draft", False), "category": category,
            "mergeable_state": full.get("mergeable_state"),
            "ci": summarize_checks((runs or {}).get("check_runs", [])),
            "in_flight": is_in_flight(pr, category, now),
        })
    issues = [
        {"number": i["number"], "title": i["title"], "category": classify_issue(i),
         "labels": sorted(lbl["name"] for lbl in i.get("labels", []))}
        for i in gh_json(f"repos/{repo}/issues?state=open&per_page=100") or []
        if "pull_request" not in i
    ]
    master_runs = gh_json(f"repos/{repo}/commits/master/check-runs?per_page=100") or {}
    wf_runs = gh_json(f"repos/{repo}/actions/runs?branch=master&per_page=100") or {}
    return {
        "repo": repo, "generated_at": now.isoformat(timespec="seconds"),
        "prs": prs, "issues": issues,
        "master_ci": summarize_checks(master_runs.get("check_runs", [])),
        "red_workflows": still_red_workflows(wf_runs.get("workflow_runs", [])),
    }


def render(inv: dict[str, Any]) -> str:
    """Render the inventory as the markdown table the skill's phase 1 reports."""
    lines = [f"# Drill inventory — {inv['repo']} at {inv['generated_at']}", ""]
    lines.append(f"Master CI: **{inv['master_ci']['state']}**"
                 + (f" (failing: {', '.join(inv['master_ci']['failing'])})" if inv["master_ci"]["failing"] else ""))
    lines.append("Red scheduled/branch workflows on master: "
                 + (", ".join(inv["red_workflows"]) or "none"))
    lines += ["", "| # | Kind | Category | CI | Merge state | Notes | Title |", "|---|---|---|---|---|---|---|"]
    for pr in inv["prs"]:
        notes = [n for n, on in (("draft", pr["draft"]), ("IN FLIGHT — report, don't touch", pr["in_flight"])) if on]
        if pr["ci"]["failing"]:
            notes.append("failing: " + ", ".join(pr["ci"]["failing"]))
        lines.append(f"| #{pr['number']} | PR | {pr['category']} | {pr['ci']['state']} | "
                     f"{pr['mergeable_state']} | {'; '.join(notes)} | {pr['title'][:70]} |")
    for issue in inv["issues"]:
        lines.append(f"| #{issue['number']} | issue | {issue['category']} | | | "
                     f"{', '.join(issue['labels'])} | {issue['title'][:70]} |")
    total = len(inv["prs"]) + len(inv["issues"])
    lines += ["", f"Open items: {total} ({len(inv['prs'])} PRs, {len(inv['issues'])} issues)."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    parser.add_argument("--own-branch", default=None,
                        help="the drill's own branch (default: the checked-out branch)")
    args = parser.parse_args(argv)
    own = current_branch() if args.own_branch is None else args.own_branch
    inv = collect(args.repo, datetime.now(timezone.utc), own)
    print(json.dumps(inv, indent=2) if args.json else render(inv))
    return 0


if __name__ == "__main__":
    sys.exit(main())
