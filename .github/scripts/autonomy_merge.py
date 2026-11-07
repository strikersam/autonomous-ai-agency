#!/usr/bin/env python3
"""Decide whether a PR may merge itself, and queue the merge when it may.

Operator decision (2026-11-07): the agency merges its own work once CI is green
and the independent verifier passed it. Called from two places, so a PR merges
whichever finishes last:

* auto-merge.yml, after the CI workflow succeeds;
* verifier-verdict.yml, after it publishes a passing "Verifier verdict" status.

The merge itself is ``gh pr merge --squash --auto --match-head-commit``: GitHub
still waits for every required check, and a later untested push never merges.
A PR touching a protected path (config/autonomy.yaml) is labelled needs-human
and left alone: spending, secrets and access, and data deletion stay human.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verifier_verdict import _FENCE_RE, last_verdict  # noqa: E402

log = logging.getLogger("qwen-proxy")

ROOT = Path(__file__).resolve().parents[2]
VERDICT_CONTEXT = "Verifier verdict"
_HEAD_RE = re.compile(r"^Verified-head:\s*([0-9a-f]{40})\s*$", re.MULTILINE)


@dataclass
class Gate:
    """Outcome for one PR."""

    merge: bool
    reason: str
    needs_human: bool = False


def load_policy(path: Path = ROOT / "config" / "autonomy.yaml") -> dict:
    """Read the autonomy policy."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def protected_hits(files: list[str], protected: list[str]) -> list[str]:
    """Changed files that fall under a protected path."""
    hits = []
    for name in files:
        low = name.lower()
        for entry in protected:
            prefix = entry.lower()
            if low == prefix.rstrip("/") or (prefix.endswith(("/", ".")) and low.startswith(prefix)):
                hits.append(name)
                break
    return hits


def bound_verdict(comments: list[dict], head_sha: str, trusted: set[str]) -> str | None:
    """The latest trusted verdict comment's verdict, if it names *head_sha*.

    Stricter than the "Verifier verdict" status, which also reads the PR body:
    for a self-merge the verdict must come from a comment (the implementing
    agent writes the body) and must name the exact commit it verified, so a
    push after verification never rides an old PASS.
    """
    for comment in reversed(comments):
        login = ((comment.get("user") or {}).get("login") or "").lower()
        body = comment.get("body") or ""
        verdict = last_verdict(body)
        if not verdict or not login or login not in trusted:
            continue
        heads = _HEAD_RE.findall(_FENCE_RE.sub("", body))
        return verdict if heads and heads[-1] == head_sha else None
    return None


def decide(pr: dict, files: list[str], verdict_state: str | None, policy: dict,
           bound: str | None = None) -> Gate:
    """Pure decision for a PR given its changed files and verdict status."""
    head = (pr.get("head") or {}).get("ref", "")
    labels = {lab.get("name", "") for lab in pr.get("labels") or []}
    if pr.get("state") != "open":
        return Gate(False, "PR is not open")
    if pr.get("draft") or "quick-note:planning" in labels:
        return Gate(False, "draft or planning PR")
    head_repo = ((pr.get("head") or {}).get("repo") or {}).get("full_name")
    base_repo = ((pr.get("base") or {}).get("repo") or {}).get("full_name")
    if head_repo != base_repo:
        # A fork author can write their own "Verdict: PASS"; only a human merges forks.
        return Gate(False, "PR comes from a fork", needs_human=True)
    if head.startswith("dependabot/"):
        return Gate(False, "Dependabot PRs are merged by dependabot-auto-merge.yml")
    if "verifier-exempt" in labels:
        # An exempt label passes the status without a verifier; only a human merges it.
        return Gate(False, "verifier-exempt PRs are merged by a human", needs_human=True)
    hits = protected_hits(files, policy.get("protected_paths") or [])
    if hits:
        return Gate(False, "touches protected paths: " + ", ".join(hits[:5]), needs_human=True)
    if verdict_state != "success":
        return Gate(False, f"verifier verdict is {verdict_state or 'missing'}")
    if bound not in ("PASS", "PASS+NOTES"):
        return Gate(False, "no passing verifier comment names the current head commit")
    return Gate(True, "CI and independent verifier passed; no protected paths")


def _gh(*args: str) -> str:
    # List argv, no shell; args come from this script and GitHub's own API.
    out = subprocess.run(["gh", *args], capture_output=True, text=True, check=True,  # nosec B603 B607
                         timeout=60)
    return out.stdout


def _verdict_state(repo: str, sha: str) -> str | None:
    data = json.loads(_gh("api", f"repos/{repo}/commits/{sha}/status"))
    for status in data.get("statuses", []):
        if status.get("context") == VERDICT_CONTEXT:
            return status.get("state")
    return None


def _changed_files(repo: str, number: str) -> list[str]:
    out = _gh("api", "--paginate", f"repos/{repo}/pulls/{number}/files", "--jq",
              ".[] | .filename, (.previous_filename // empty)")
    return [line for line in out.splitlines() if line]


def run(repo: str, number: str, sha: str | None) -> Gate:
    """Evaluate one PR and act on the decision."""
    pr = json.loads(_gh("api", f"repos/{repo}/pulls/{number}"))
    head_sha = pr["head"]["sha"]
    if sha and sha != head_sha:
        return Gate(False, "head moved since this run; the newer commit decides")
    policy = load_policy()
    comments = json.loads(_gh("api", "--paginate", "--slurp", f"repos/{repo}/issues/{number}/comments"))
    comments = [c for page in comments for c in page] if comments and isinstance(comments[0], list) else comments
    trusted = {repo.split("/")[0].lower(), "github-actions[bot]"}
    gate = decide(pr, _changed_files(repo, number), _verdict_state(repo, head_sha), policy,
                  bound_verdict(comments, head_sha, trusted))
    if gate.needs_human:
        label = policy.get("needs_human_label", "needs-human")
        _gh("pr", "edit", number, "--repo", repo, "--add-label", label)
    if gate.merge:
        _gh("pr", "merge", number, "--repo", repo, "--squash", "--auto",
            "--match-head-commit", head_sha)
    return gate


def main() -> int:
    """Entry point for the workflows."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    repo, number = os.environ["REPO"], os.environ["PR_NUMBER"]
    try:
        gate = run(repo, number, os.environ.get("HEAD_SHA") or None)
    except subprocess.CalledProcessError as exc:
        log.warning("Autonomy merge gate could not act on #%s: %s", number, (exc.stderr or "")[:300])
        return 0
    log.info("PR #%s: %s (%s)", number, "queued for merge" if gate.merge else "not merged", gate.reason)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"## Autonomy merge gate\nPR #{number}: {gate.reason}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
