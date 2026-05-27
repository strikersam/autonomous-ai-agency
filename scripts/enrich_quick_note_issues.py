#!/usr/bin/env python3
"""Add rich implementation context comments to open quick-note GitHub issues.

Usage:
  GITHUB_TOKEN=... python scripts/enrich_quick_note_issues.py
  python scripts/enrich_quick_note_issues.py --dry-run
"""
from __future__ import annotations

import argparse
import os
from textwrap import dedent
from urllib.parse import urlparse

import requests

OWNER = "strikersam"
REPO = "local-llm-server"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"


def _headers() -> dict[str, str]:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
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
        batch = [item for item in res.json() if "pull_request" not in item]
        if not batch:
            break
        issues.extend(batch)
        page += 1
    return issues


def _is_quick_note(issue: dict) -> bool:
    title = issue.get("title", "").lower()
    labels = [label["name"].lower() for label in issue.get("labels", [])]
    return title.startswith("quick-note:") or any("quick-note" in label for label in labels) or "quick note" in title


def _extract_source(issue: dict) -> str:
    title = issue.get("title", "").strip()
    if ":" in title and title.lower().startswith("quick-note"):
        return title.split(":", 1)[1].strip()
    body = (issue.get("body") or "").strip()
    if body:
        return body.splitlines()[0].strip()
    url = issue.get("html_url", "")
    if url and urlparse(url).scheme:
        return url
    return title


def _comment_body(issue: dict) -> str:
    source = _extract_source(issue)
    return dedent(
        f"""
        ## LLM Implementation Context (auto-added)

        Source artifact: `{source}`

        ### Goal
        Turn this quick-note into a **production-grade** change in `local-llm-server` with tests, docs, and safety checks.

        ### Repository constraints (must follow)
        - Read `CLAUDE.md` first and use relevant skills from `.claude/skills/`.
        - Run `pytest -x` before and after changes.
        - Update `docs/changelog.md` under `## [Unreleased]`.
        - Prefer minimal, verifiable changes over speculative large refactors.

        ### Expected implementation output
        1. Problem statement extracted from source with explicit assumptions.
        2. Concrete file-level plan with impacted modules.
        3. Implementation with type hints and logging (no secrets in logs).
        4. Tests added/updated in `tests/`.
        5. Changelog entry and short risk analysis.

        ### Quality bar
        - No placeholder TODO-only commits.
        - If source URL is unavailable/blocked, proceed using a best-effort summary and clearly state assumptions in PR.
        - Include rollback notes for risky paths (`admin_auth.py`, `key_store.py`, `agent/tools.py`, auth middleware in `proxy.py`).
        """
    ).strip()


def _has_existing_context(issue_number: int) -> bool:
    res = requests.get(f"{API}/issues/{issue_number}/comments", headers=_headers(), timeout=30)
    res.raise_for_status()
    for c in res.json():
        if "## LLM Implementation Context (auto-added)" in c.get("body", ""):
            return True
    return False


def _post_comment(issue_number: int, body: str, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] would comment on #{issue_number}")
        return
    res = requests.post(f"{API}/issues/{issue_number}/comments", headers=_headers(), json={"body": body}, timeout=30)
    res.raise_for_status()
    print(f"commented on #{issue_number}: {res.json().get('html_url')}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")):
        raise SystemExit("GITHUB_TOKEN or GH_TOKEN is required unless --dry-run is used")

    issues = [issue for issue in _fetch_open_issues() if _is_quick_note(issue)]
    print(f"found {len(issues)} quick-note issue(s)")

    for issue in issues:
        n = issue["number"]
        if _has_existing_context(n):
            print(f"skip #{n}: context already present")
            continue
        _post_comment(n, _comment_body(issue), args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
