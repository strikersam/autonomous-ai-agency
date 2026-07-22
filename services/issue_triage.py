"""services/issue_triage.py — inbound GitHub issue triage.

Closes the intake gap left by the agency's outbound task generation (scanner,
trend watcher, improvement loop): those all *create* work, but nothing turns
an inbound bug report or feature request filed by a user into a routed agent
task. This module polls open, unlabeled issues on a configured repo,
classifies them with the existing task classifier, and registers them through
`agent.improvement_loop.ImprovementLoop.register_external_issue` — the same
dedup + fix-dispatch path scanner-detected issues use — then labels the issue
so it is never re-processed.

Disabled by default (Golden Rule): set ISSUE_TRIAGE_ENABLED=true to opt in.

Env vars (read here only):
    ISSUE_TRIAGE_ENABLED    default "false"
    ISSUE_TRIAGE_OWNER      default "strikersam"
    ISSUE_TRIAGE_REPO       default "autonomous-ai-agency"
    ISSUE_TRIAGE_MAX_ISSUES default "10" — issues processed per run
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("qwen-proxy")

TRIAGED_LABEL = "agency:triaged"

_FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "qa": ("test", "flaky", "coverage", "regression"),
    "security": ("vulnerability", "cve", "secret", "auth", "exploit"),
    "devops": ("ci", "deploy", "pipeline", "docker", "workflow"),
    "frontend": ("ui", "dashboard", "react", "frontend", "css"),
    "backend": ("api", "endpoint", "backend", "server", "database"),
    "docs": ("docs", "documentation", "readme", "changelog"),
    "ml": ("model", "inference", "embedding", "training"),
}


def triage_enabled() -> bool:
    return os.environ.get("ISSUE_TRIAGE_ENABLED", "false").strip().lower() in ("true", "1", "yes", "on")


def _match_family(title: str, body: str) -> str:
    text = f"{title} {body}".lower()
    for family, keywords in _FAMILY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return family
    return "engineering"


def _severity_for(issue: dict[str, Any]):
    from agent.improvement_loop import IssueSeverity
    labels = {lbl.get("name", "").lower() for lbl in issue.get("labels", [])}
    if labels & {"critical", "security", "p0"}:
        return IssueSeverity.CRITICAL
    if labels & {"bug", "high", "p1"}:
        return IssueSeverity.HIGH
    if labels & {"enhancement", "feature"}:
        return IssueSeverity.MEDIUM
    return IssueSeverity.LOW


async def triage_one(issue: dict[str, Any]) -> dict[str, Any]:
    """Classify a single GitHub issue payload and return the routing decision.

    Pure function of the issue payload (no network calls) so it can be unit
    tested without a live GitHub client.
    """
    from agent.improvement_loop import DetectedIssue, IssueCategory
    from router.classifier import classify_task

    title = issue.get("title", "")
    body = issue.get("body") or ""
    number = issue.get("number")

    category_hint = classify_task(messages=[{"role": "user", "content": f"{title}\n{body}"}])
    family = _match_family(title, body)
    severity = _severity_for(issue)

    detected = DetectedIssue(
        issue_id=f"gh-{number}",
        category=IssueCategory.FEATURE_REQUEST,
        severity=severity,
        title=f"[#{number}] {title}",
        description=body[:2000] or "(no description provided)",
    )
    return {
        "issue_number": number,
        "family": family,
        "task_category": category_hint,
        "severity": severity.value,
        "detected_issue": detected,
    }


async def run_triage_cycle() -> dict[str, Any]:
    """Fetch unlabeled open issues, triage each, and route them.

    Returns a summary dict: {"processed": int, "routed": int, "skipped": int}.
    Best-effort — network/config failures are logged and return zero counts
    rather than raising, so this can be wired into a scheduled loop safely.
    """
    if not triage_enabled():
        return {"processed": 0, "routed": 0, "skipped": 0, "reason": "disabled"}

    owner = os.environ.get("ISSUE_TRIAGE_OWNER", "strikersam")
    repo = os.environ.get("ISSUE_TRIAGE_REPO", "autonomous-ai-agency")
    max_issues = int(os.environ.get("ISSUE_TRIAGE_MAX_ISSUES", "10"))

    try:
        from agent.github_tools import GitHubTools
        # Autonomous loop, not a per-user request — reads the shared token
        # directly, matching agent/agency.py and agent/workflow.py.
        token = os.environ.get("GH_TOKEN") or os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")
        client = GitHubTools(token=token)
        issues = await client.list_issues(owner, repo, state="open", per_page=max_issues)
    except Exception as exc:
        log.warning("issue_triage: could not fetch issues: %s", exc)
        return {"processed": 0, "routed": 0, "skipped": 0, "reason": str(exc)}

    unlabeled = [
        i for i in issues
        if TRIAGED_LABEL not in {lbl.get("name") for lbl in i.get("labels", [])}
    ][:max_issues]

    from agent.improvement_loop import get_improvement_loop
    loop = get_improvement_loop()

    routed = 0
    for issue in unlabeled:
        decision = await triage_one(issue)
        if loop is not None:
            was_new = loop.register_external_issue(decision["detected_issue"])
            if was_new:
                routed += 1
        try:
            await client.add_labels(owner, repo, issue["number"], [TRIAGED_LABEL, f"family:{decision['family']}"])
        except Exception as exc:  # nosec B110 -- labeling is best-effort
            log.debug("issue_triage: could not label issue #%s: %s", issue.get("number"), exc)

    return {"processed": len(unlabeled), "routed": routed, "skipped": len(unlabeled) - routed}
