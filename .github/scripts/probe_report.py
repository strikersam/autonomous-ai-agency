#!/usr/bin/env python3
"""probe_report.py — turn a catalogue-probe run into one tracking issue.

The scheduled ``catalogue-probe.yml`` writes a machine-readable summary
(``probe_catalogues.py --json``) of what every configured provider actually
served. This script reads that summary and, when a provider is unreachable or
a named model would not answer, opens *one* tracking issue naming the provider,
the model id, and the status code it answered with — or updates the existing
open one instead of filing a duplicate. A clean run touches nothing.

It is deliberately dependency-injected: :func:`run` takes the three GitHub
operations (list / create / update) as callables so the create-vs-update
branching can be unit-tested without a network. :func:`main` wires the real
``httpx``-backed operations against the Actions ``GITHUB_TOKEN``.

Read-only against the providers; the only write is the single tracking issue.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Callable

# Stable marker so the tracker issue is found again on the next run, even if a
# human edits its title. Kept in the body, backed by a label for the API query.
MARKER = "<!-- catalogue-probe-drift-tracker -->"
DEFAULT_LABEL = "catalogue-drift"
TITLE = "Provider catalogue drift: a configured model is not serving"

ListIssues = Callable[[], list[dict]]
CreateIssue = Callable[[str, str, str], dict]  # (title, body, label) -> issue
UpdateIssue = Callable[[int, str, str], dict]  # (number, title, body) -> issue


def _failures(summary: dict) -> tuple[list[str], list[dict]]:
    """Split a probe summary into (unreachable providers, unservable models).

    ``unlistable`` is intentionally excluded: a provider that answered a
    completion but would not list is reachable, not drifted.
    """
    unreachable = list(summary.get("unreachable") or [])
    detail = summary.get("unservable_detail")
    if detail:
        unservable = list(detail)
    else:
        # Older summaries carried only the bare "provider:model" ids.
        unservable = [{"id": i, "detail": "unknown"} for i in summary.get("unservable") or []]
    return unreachable, unservable


def build_body(summary: dict, *, now: str | None = None) -> str:
    """Render the tracking-issue body from a probe summary."""
    unreachable, unservable = _failures(summary)
    stamp = now or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        MARKER,
        "",
        "The scheduled provider catalogue probe found a configured provider or "
        "model that is no longer serving. This is the drift the probe exists to "
        "catch before it surfaces as a production `410`/`404`/`402`.",
        "",
        f"_Last updated by `catalogue-probe.yml` at {stamp}._",
        "",
    ]
    if unservable:
        lines.append("### Named but would not answer")
        for item in unservable:
            lines.append(f"- `{item.get('id', '?')}` — {item.get('detail', 'unknown')}")
        lines.append("")
    if unreachable:
        lines.append("### Unreachable providers")
        for pid in unreachable:
            lines.append(f"- `{pid}` — no route / listing refused")
        lines.append("")
    lines.append(
        "Re-run `Provider catalogue probe` manually (workflow_dispatch) to "
        "reproduce, then fix the id in `config/models.yaml` / "
        "`config/llm/models.yaml` or clear the provider's failover switch. This "
        "issue updates itself on each scheduled run and can be closed once green."
    )
    return "\n".join(lines)


def find_tracking_issue(issues: list[dict]) -> dict | None:
    """Return the existing open tracking issue, if any (marker match wins)."""
    for issue in issues:
        if "pull_request" in issue:
            continue
        if MARKER in (issue.get("body") or ""):
            return issue
    return None


def run(
    summary: dict,
    *,
    list_issues: ListIssues,
    create_issue: CreateIssue,
    update_issue: UpdateIssue,
    label: str = DEFAULT_LABEL,
) -> str:
    """Reconcile the probe summary to exactly one tracking issue.

    Returns an action token: ``"noop"``, ``"created:#N"``, or ``"updated:#N"``.
    A passing run (``ok``/no failures) performs no API write at all.
    """
    unreachable, unservable = _failures(summary)
    if summary.get("ok") or (not unreachable and not unservable):
        print("catalogue probe is green — no drift issue to file or update.")
        return "noop"

    body = build_body(summary)
    existing = find_tracking_issue(list_issues())
    if existing is not None:
        number = existing["number"]
        update_issue(number, TITLE, body)
        print(f"updated existing drift tracker #{number}")
        return f"updated:#{number}"

    issue = create_issue(TITLE, body, label)
    number = issue.get("number", "?")
    print(f"opened drift tracker #{number}")
    return f"created:#{number}"


# ---------------------------------------------------------------------------
# httpx-backed GitHub operations (only reached from main()).
# ---------------------------------------------------------------------------

def _gh_ops(repo: str, token: str):
    import httpx

    base = f"https://api.github.com/repos/{repo}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    def list_issues() -> list[dict]:
        resp = httpx.get(
            f"{base}/issues",
            params={"state": "open", "labels": DEFAULT_LABEL, "per_page": "100"},
            headers=headers,
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()

    def create_issue(title: str, body: str, label: str) -> dict:
        resp = httpx.post(
            f"{base}/issues",
            json={"title": title, "body": body, "labels": [label]},
            headers=headers,
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()

    def update_issue(number: int, title: str, body: str) -> dict:
        resp = httpx.patch(
            f"{base}/issues/{number}",
            json={"title": title, "body": body},
            headers=headers,
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()

    return list_issues, create_issue, update_issue


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", required=True, metavar="PATH", help="probe summary file")
    args = parser.parse_args(argv)

    try:
        with open(args.json, encoding="utf-8") as fh:
            summary = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"could not read probe summary {args.json!r}: {exc}")
        return 0  # nothing to report — do not fail the workflow on a missing file

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    repo = os.environ.get("GITHUB_REPOSITORY") or os.environ.get("REPO") or ""
    if not token or not repo:
        print("no GITHUB_TOKEN/GITHUB_REPOSITORY in the environment — cannot file an issue.")
        return 0

    list_issues, create_issue, update_issue = _gh_ops(repo, token)
    try:
        run(
            summary,
            list_issues=list_issues,
            create_issue=create_issue,
            update_issue=update_issue,
        )
    except Exception as exc:  # noqa: BLE001 - issue-filing must not fail the job
        print(f"drift-report step could not reach the GitHub API: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
