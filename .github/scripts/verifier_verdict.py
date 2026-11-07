#!/usr/bin/env python3
"""Merge gate for CLAUDE.md rule 49: a PR needs an independent verifier verdict.

Reads the PR body and its comments and passes only when the most recent
verdict line from a trusted author is ``PASS`` or ``PASS+NOTES``. A later
``FAIL`` overrides an earlier pass, so a re-verification that breaks the
change blocks it again.

A verdict line looks like ``Verdict: PASS+NOTES`` (bold markers and a
leading ``**`` are tolerated). Trusted authors are the PR author's body, the
repository owner, and GitHub Actions; a drive-by commenter cannot clear the
gate. Dependabot PRs and PRs labelled ``verifier-exempt`` are exempt.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass

log = logging.getLogger("qwen-proxy")

VERDICT_RE = re.compile(
    r"^[ \t*_\-]*verdict\W{0,4}[:\-]\W{0,4}(PASS\+NOTES|PASS|FAIL)\b",
    re.IGNORECASE | re.MULTILINE,
)
EXEMPT_AUTHORS = frozenset({"dependabot[bot]"})
EXEMPT_LABEL = "verifier-exempt"
TRUSTED_BOTS = frozenset({"github-actions[bot]"})


@dataclass
class Decision:
    """Outcome of the gate."""

    ok: bool
    reason: str


def last_verdict(text: str) -> str | None:
    """The last verdict named in *text*, upper-cased, or None."""
    found = VERDICT_RE.findall(text or "")
    return found[-1].upper() if found else None


def decide(pr: dict, comments: list[dict], owner: str) -> Decision:
    """Apply the gate to a PR payload and its issue comments (oldest first)."""
    author = (pr.get("user") or {}).get("login", "")
    labels = {lab.get("name", "") for lab in pr.get("labels") or []}
    if author in EXEMPT_AUTHORS:
        return Decision(True, f"exempt: authored by {author}")
    if EXEMPT_LABEL in labels:
        return Decision(True, f"exempt: labelled {EXEMPT_LABEL}")

    trusted = {x for x in (owner.lower(), author.lower(), *TRUSTED_BOTS) if x}
    verdict = last_verdict(pr.get("body") or "")
    for comment in comments:
        login = ((comment.get("user") or {}).get("login") or "").lower()
        if login not in trusted:
            continue
        found = last_verdict(comment.get("body") or "")
        if found:
            verdict = found
    if verdict in {"PASS", "PASS+NOTES"}:
        return Decision(True, f"independent verifier verdict: {verdict}")
    if verdict == "FAIL":
        return Decision(False, "latest verifier verdict is FAIL: fix the defects and re-verify")
    return Decision(
        False,
        "no verifier verdict found. Add a line 'Verdict: PASS' or 'Verdict: PASS+NOTES' "
        "from an independent verifier to the PR body or a comment (CLAUDE.md rule 49)",
    )


def _get(url: str, token: str) -> object:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310 - fixed api.github.com host
        return json.loads(resp.read())


def _post_status(base: str, sha: str, token: str, decision: Decision) -> None:
    """Publish the gate as the commit status "Verifier verdict" on the PR head."""
    body = json.dumps({
        "state": "success" if decision.ok else "failure",
        "context": "Verifier verdict",
        "description": decision.reason[:140],
    }).encode()
    req = urllib.request.Request(f"{base}/statuses/{sha}", data=body, method="POST", headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req, timeout=30):  # nosec B310 - fixed api.github.com host
        pass


def main() -> int:
    """Entry point for the workflow."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    repo, number, token = os.environ["REPO"], os.environ["PR_NUMBER"], os.environ["GH_TOKEN"]
    base = f"https://api.github.com/repos/{repo}"
    try:
        return _run(base, number, token, repo)
    except urllib.error.URLError as exc:
        log.error("Verifier verdict could not read or update the PR: %s", exc)
        return 1


def _run(base: str, number: str, token: str, repo: str) -> int:
    pr = _get(f"{base}/pulls/{number}", token)
    comments: list[dict] = []
    page = 1
    while True:
        batch = _get(f"{base}/issues/{number}/comments?per_page=100&page={page}", token)
        comments.extend(batch)  # type: ignore[arg-type]
        if len(batch) < 100:  # type: ignore[arg-type]
            break
        page += 1
    decision = decide(pr, comments, repo.split("/")[0])  # type: ignore[arg-type]
    log.info("%s: %s", "PASS" if decision.ok else "BLOCKED", decision.reason)
    _post_status(base, pr["head"]["sha"], token, decision)  # type: ignore[index]
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"## Verifier verdict\n{decision.reason}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
