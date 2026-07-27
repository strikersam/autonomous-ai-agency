#!/usr/bin/env python3
"""Find quick-note issues that have no context document and queue real generation.

This script used to post a fixed Markdown template as a comment on every open
quick-note issue. That template was identical for every issue, was never
grounded in the linked URL, and named files it had no intention of touching —
so it read as analysis while carrying no information, and it buried the genuine
context document when one later arrived.

It now detects the gap and hands the work to the one component that can actually
fill it: `.github/workflows/bulk-issue-context.yml`, which fetches the linked
source, runs it through the LLM generator, and validates the result against
`docs/QUICK_NOTE_CONTEXT_RULEBOOK.md`. Detection lives here; generation lives
there. Nothing writes ungrounded context to an issue any more.

Usage:
  GITHUB_TOKEN=... python scripts/enrich_quick_note_issues.py
  python scripts/enrich_quick_note_issues.py --dry-run
  python scripts/enrich_quick_note_issues.py --max-dispatch 5
"""
from __future__ import annotations

import argparse
import logging
import os

import requests

OWNER = "strikersam"
REPO = "autonomous-ai-agency"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"

#: The workflow that owns context generation. Feeding it explicit issue numbers
#: bypasses its own discovery pass so we only pay for the gaps we found.
GENERATOR_WORKFLOW = "bulk-issue-context.yml"

#: Branch naming convention used by both context workflows. Its existence is the
#: authoritative "this issue already has a context document" signal.
CONTEXT_BRANCH_TEMPLATE = "claude/context-issue-{number}"

#: Generation costs provider tokens and opens a draft PR per issue, so an
#: unattended 4-hourly run is capped rather than allowed to stampede a backlog.
DEFAULT_MAX_DISPATCH = 10

log = logging.getLogger("enrich_quick_note_issues")


def _headers() -> dict[str, str]:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_PAT") or os.getenv("GH_TOKEN")
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _fetch_open_issues() -> list[dict]:
    issues: list[dict] = []
    page = 1
    while True:
        res = requests.get(
            f"{API}/issues",
            params={"state": "open", "per_page": 100, "page": page},
            headers=_headers(),
            timeout=30,
        )
        res.raise_for_status()
        payload = res.json()
        if not payload:
            break
        issues.extend(item for item in payload if "pull_request" not in item)
        page += 1
    return issues


def _is_quick_note(issue: dict) -> bool:
    title = issue.get("title", "").lower()
    labels = [label["name"].lower() for label in issue.get("labels", [])]
    return (
        title.startswith("quick-note:")
        or any("quick-note" in label for label in labels)
        or "quick note" in title
    )


def _has_context(issue_number: int) -> bool:
    """True when a context branch already exists for this issue.

    Checked against branches rather than comments: a comment can be posted by
    anything, whereas the branch is created only by a generator run that
    produced a document.
    """
    branch = CONTEXT_BRANCH_TEMPLATE.format(number=issue_number)
    res = requests.get(f"{API}/branches/{branch}", headers=_headers(), timeout=30)
    if res.status_code == 404:
        return False
    res.raise_for_status()
    return True


def _dispatch_generation(issue_numbers: list[int], dry_run: bool) -> None:
    """Ask the bulk context workflow to generate documents for these issues."""
    targets = ",".join(str(n) for n in issue_numbers)
    if dry_run:
        log.info("[dry-run] would dispatch %s for issues: %s", GENERATOR_WORKFLOW, targets)
        return

    res = requests.post(
        f"{API}/actions/workflows/{GENERATOR_WORKFLOW}/dispatches",
        headers=_headers(),
        json={
            "ref": "master",
            "inputs": {
                "issue_numbers": targets,
                "max_issues": str(len(issue_numbers)),
            },
        },
        timeout=30,
    )
    res.raise_for_status()
    log.info("dispatched %s for issues: %s", GENERATOR_WORKFLOW, targets)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--max-dispatch",
        type=int,
        default=DEFAULT_MAX_DISPATCH,
        help="Maximum issues queued for generation in one run.",
    )
    args = parser.parse_args()

    if not args.dry_run and not (
        os.getenv("GITHUB_TOKEN") or os.getenv("GH_PAT") or os.getenv("GH_TOKEN")
    ):
        raise SystemExit("GITHUB_TOKEN / GH_PAT / GH_TOKEN is required unless --dry-run is used")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    issues = [issue for issue in _fetch_open_issues() if _is_quick_note(issue)]
    log.info("found %s quick-note issue(s)", len(issues))

    missing: list[int] = []
    for issue in issues:
        number = issue["number"]
        if _has_context(number):
            log.info("skip #%s: context branch already exists", number)
            continue
        missing.append(number)

    if not missing:
        log.info("every open quick-note issue already has a context document")
        return 0

    batch = sorted(missing)[: args.max_dispatch]
    # An empty batch must return, not dispatch. bulk-issue-context.yml treats a
    # blank `issue_numbers` as "discover every open issue" and applies its cap
    # only `if max_n > 0`, so forwarding an empty batch with max_issues=0 would
    # process the entire backlog — the exact opposite of --max-dispatch 0.
    if not batch:
        log.info("max-dispatch=%s leaves nothing to queue this run", args.max_dispatch)
        return 0
    if len(missing) > len(batch):
        log.info(
            "%s issue(s) lack context; queuing %s this run (cap --max-dispatch=%s)",
            len(missing),
            len(batch),
            args.max_dispatch,
        )
    _dispatch_generation(batch, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
