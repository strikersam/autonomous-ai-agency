#!/usr/bin/env python3
"""scripts/classify_dependabot_update.py

Decide whether a Dependabot PR is a major (breaking) upgrade, using only what
the PR itself carries.

Why this exists
---------------
``dependabot/fetch-metadata`` is the authority on update type, but it needs the
``pull_request`` event payload. The recovery sweep in
``.github/workflows/dependabot-auto-merge.yml`` runs on schedule/dispatch and
has no such payload, and the event-driven job that does is guarded by
``github.actor == 'dependabot[bot]'`` — so once the sweep updates a stale branch
with ``GH_PAT``, the actor is a real user and that job **skips**. Verified on
PR #1336: run 32936415712, actor ``strikersam``, conclusion ``skipped``.

That left the sweep about to arm auto-merge on `anthropic >=0.122.0 → >=1.0.0`
with nothing in the loop to object, which rule 40 reserves for a human. So the
sweep needs a verdict it owns.

What it reads
-------------
Dependabot writes a compare link into the commit message body:

    - [Commits](https://github.com/anthropics/anthropic-sdk-python/compare/v0.122.0...v1.0.0)

Both versions are right there, which beats parsing pip range syntax out of a
title like ``from <6,>=5.0.0 to >=5.0.1,<6``.

Grouped PRs carry no single compare link, and do not need one: the groups in
``.github/dependabot.yml`` are declared ``update-types: ["minor", "patch"]``, so
a grouped PR cannot contain a major bump by construction.

Anything it cannot read confidently is ``unknown``, which the sweep treats like
``major`` — left for a human. Guessing in the permissive direction here means
merging a breaking upgrade unattended.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

__all__ = [
    "classify",
    "classify_pull_request",
    "is_auto_mergeable",
    "parse_version",
    "MAJOR",
    "UNKNOWN",
]

MAJOR = "major"
MINOR = "minor"
PATCH = "patch"
GROUP = "group"
UNKNOWN = "unknown"

#: Groups declared in .github/dependabot.yml, all constrained to minor/patch.
_GROUP_BRANCH = re.compile(r"/(all-patches|security-patches)-[0-9a-f]+$")

_COMPARE = re.compile(r"/compare/(\S+?)\.\.\.(\S+?)[)\s]")

# Dependabot prefixes the ref with a tag style that varies by project:
# "v1.2.3", "lxml-6.1.1", "livekit-agents@1.7.0", or a bare "1.43.71".
_VERSION_IN_REF = re.compile(r"(\d+(?:\.\d+)*)\s*$")

_AUTO_MERGEABLE = frozenset({GROUP, MINOR, PATCH})


def parse_version(ref: str) -> tuple[int, ...] | None:
    """Pull a numeric version tuple out of a Dependabot compare ref."""
    match = _VERSION_IN_REF.search(ref.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def _component(version: tuple[int, ...], index: int) -> int:
    return version[index] if index < len(version) else 0


def compare_versions(old: tuple[int, ...], new: tuple[int, ...]) -> str:
    """Classify old→new by semver, treating 0.x as unstable.

    Below 1.0.0 a minor bump is conventionally allowed to break, so it is
    reported as major rather than waved through.
    """
    if _component(old, 0) != _component(new, 0):
        return MAJOR
    if _component(new, 0) == 0 and _component(old, 1) != _component(new, 1):
        return MAJOR
    if _component(old, 1) != _component(new, 1):
        return MINOR
    return PATCH


def classify(branch: str, commit_message: str) -> str:
    """Return the update type for a Dependabot PR.

    *branch* is ``headRefName``; *commit_message* is the head commit's message.
    """
    if _GROUP_BRANCH.search(branch.strip()):
        return GROUP

    match = _COMPARE.search(commit_message + "\n")
    if not match:
        return UNKNOWN

    old, new = parse_version(match.group(1)), parse_version(match.group(2))
    if old is None or new is None:
        return UNKNOWN
    return compare_versions(old, new)


def classify_pull_request(pr: dict) -> str:
    """Classify a PR from ``gh pr view --json headRefName,commits`` output.

    Reads *every* commit, not just the newest. The sweep's own
    ``gh pr update-branch`` appends "Merge branch 'master' into ..." commits,
    which carry no compare link — so looking only at the head commit returns
    ``unknown`` for a PR the sweep had itself updated, and ``unknown`` is not
    auto-mergeable. That would leave the recovery path unable to arm anything
    it touched, and would say so in a log line that reads like a deliberate
    safety decision. Confirmed on PR #1342: boto3 1.43.71 -> 1.43.77, a patch,
    read as ``unknown`` under three merge commits.
    """
    commits = pr.get("commits") or []
    message = "\n".join(
        f"{c.get('messageHeadline', '')}\n{c.get('messageBody', '')}" for c in commits
    )
    return classify(pr.get("headRefName", ""), message)


def is_auto_mergeable(update_type: str) -> bool:
    """Only a verdict we actually reached permits an unattended merge."""
    return update_type in _AUTO_MERGEABLE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "pr_json",
        help="`gh pr view --json headRefName,commits` output, or '-' for stdin",
    )
    args = parser.parse_args(argv)

    raw = sys.stdin.read() if args.pr_json == "-" else Path(args.pr_json).read_text(
        encoding="utf-8"
    )
    print(classify_pull_request(json.loads(raw)))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
