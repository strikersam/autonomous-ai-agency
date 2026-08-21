"""scripts/refresh_agent_built_proof.py

Root-cause fix for the "agent-built proof" numbers going stale: they used to
be prose, hand-typed into three files whenever someone remembered to. This
re-runs the same three GitHub search queries the docs cite
(``is:pr is:merged``, ``+ head:claude/``, ``+ head:codex/``) against the live
API and rewrites the counts in place — only when they've actually drifted
from what the docs currently say.

Rewrites, in order:

- ``proof/agent-built.md`` — the "As of <date>:" line, the three table rows,
  and the "N of M merged PRs (X%)" summary sentence.
- ``proof/README.md`` — the "N of the M merged pull requests" mention in the
  artifact table.
- ``README.md`` — the same "N of the M merged pull requests" mention.

The methodology sentence, the caveats, and the sample-PR table are left
untouched; only the numbers move.

Usage
-----
::

    python scripts/refresh_agent_built_proof.py            # rewrite if drifted
    python scripts/refresh_agent_built_proof.py --check     # exit 1 if stale, no writes
    python scripts/refresh_agent_built_proof.py --dry-run   # report drift, no writes

A ``GITHUB_TOKEN``/``GH_TOKEN`` env var is used for the search API if set
(higher rate limit); unauthenticated calls work too, just at a lower limit.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO = "strikersam/autonomous-ai-agency"
SEARCH_API = "https://api.github.com/search/issues"

_ROOT = Path(__file__).resolve().parent.parent
AGENT_BUILT_PATH = _ROOT / "proof" / "agent-built.md"
PROOF_README_PATH = _ROOT / "proof" / "README.md"
ROOT_README_PATH = _ROOT / "README.md"

_AS_OF_RE = re.compile(r"(?<=^As of )\d{4}-\d{2}-\d{2}(?=:$)", re.MULTILINE)
_TOTAL_ROW_RE = re.compile(r"(?<=Merged pull requests, total \| \*\*)(\d+)(?=\*\* \|)")
_CLAUDE_ROW_RE = re.compile(
    r"(?<=`claude/\*` head branches\) \| \*\*)(\d+)(?=\*\* \|)"
)
_CODEX_ROW_RE = re.compile(
    r"(?<=`codex/\*` head branches\) \| \*\*)(\d+)(?=\*\* \|)"
)
_SUMMARY_SENTENCE_RE = re.compile(
    r"\*\*\d+ of \d+ merged PRs \(\d+%\) were opened by AI agent sessions\*\*"
)
_N_OF_M_RE = re.compile(r"\*\*\d+ of the \d+ merged pull requests\*\*")


@dataclass(frozen=True)
class ProofCounts:
    total_merged: int
    claude_merged: int
    codex_merged: int

    @property
    def agent_merged(self) -> int:
        return self.claude_merged + self.codex_merged

    @property
    def agent_pct(self) -> int:
        if self.total_merged == 0:
            return 0
        return round(self.agent_merged * 100 / self.total_merged)


def _search_count(query: str, token: str | None) -> int:
    url = f"{SEARCH_API}?q={urllib.parse.quote(query)}&per_page=1"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    return int(data["total_count"])


def fetch_counts(repo: str = REPO, token: str | None = None) -> ProofCounts:
    """Re-run the three live GitHub search queries the proof docs cite."""
    base = f"repo:{repo} is:pr is:merged"
    total = _search_count(base, token)
    claude = _search_count(f"{base} head:claude/", token)
    codex = _search_count(f"{base} head:codex/", token)
    return ProofCounts(total_merged=total, claude_merged=claude, codex_merged=codex)


def extract_counts(agent_built_text: str) -> ProofCounts:
    """Parse the counts currently committed in proof/agent-built.md's table."""
    total_match = _TOTAL_ROW_RE.search(agent_built_text)
    claude_match = _CLAUDE_ROW_RE.search(agent_built_text)
    codex_match = _CODEX_ROW_RE.search(agent_built_text)
    if not (total_match and claude_match and codex_match):
        raise ValueError("could not find one or more count fields in agent-built.md")
    return ProofCounts(
        total_merged=int(total_match.group(1)),
        claude_merged=int(claude_match.group(1)),
        codex_merged=int(codex_match.group(1)),
    )


def rewrite_agent_built(text: str, counts: ProofCounts, as_of: date) -> str:
    """Rewrite the "As of", table rows, and summary sentence in agent-built.md."""
    text = _AS_OF_RE.sub(as_of.isoformat(), text, count=1)
    text = _TOTAL_ROW_RE.sub(str(counts.total_merged), text, count=1)
    text = _CLAUDE_ROW_RE.sub(str(counts.claude_merged), text, count=1)
    text = _CODEX_ROW_RE.sub(str(counts.codex_merged), text, count=1)
    text = _SUMMARY_SENTENCE_RE.sub(
        f"**{counts.agent_merged} of {counts.total_merged} merged PRs "
        f"({counts.agent_pct}%) were opened by AI agent sessions**",
        text,
        count=1,
    )
    return text


def rewrite_n_of_m(text: str, counts: ProofCounts) -> str:
    """Rewrite every "**N of the M merged pull requests**" mention in text."""
    return _N_OF_M_RE.sub(
        f"**{counts.agent_merged} of the {counts.total_merged} merged pull requests**",
        text,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the docs are stale relative to the live counts; never writes.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report drift without writing any files.",
    )
    parser.add_argument("--repo", default=REPO, help="owner/repo to query (default: %(default)s)")
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    try:
        fresh = fetch_counts(repo=args.repo, token=token)
    except (urllib.error.URLError, KeyError, ValueError) as exc:
        print(f"::error::Failed to query the GitHub search API: {exc}", file=sys.stderr)
        return 2

    agent_built_text = AGENT_BUILT_PATH.read_text(encoding="utf-8")
    current = extract_counts(agent_built_text)

    if fresh == current:
        print(
            f"No drift: {fresh.total_merged} merged total, "
            f"{fresh.agent_merged} agent-authored ({fresh.agent_pct}%). Nothing to do."
        )
        return 0

    print(
        "Drift detected:\n"
        f"  total merged:  {current.total_merged} -> {fresh.total_merged}\n"
        f"  claude/ merged: {current.claude_merged} -> {fresh.claude_merged}\n"
        f"  codex/ merged:  {current.codex_merged} -> {fresh.codex_merged}\n"
        f"  agent share:    {current.agent_pct}% -> {fresh.agent_pct}%"
    )

    if args.check or args.dry_run:
        return 1 if args.check else 0

    as_of = date.today()
    new_agent_built = rewrite_agent_built(agent_built_text, fresh, as_of)
    AGENT_BUILT_PATH.write_text(new_agent_built, encoding="utf-8")

    proof_readme_text = PROOF_README_PATH.read_text(encoding="utf-8")
    PROOF_README_PATH.write_text(rewrite_n_of_m(proof_readme_text, fresh), encoding="utf-8")

    root_readme_text = ROOT_README_PATH.read_text(encoding="utf-8")
    ROOT_README_PATH.write_text(rewrite_n_of_m(root_readme_text, fresh), encoding="utf-8")

    print("Rewrote proof/agent-built.md, proof/README.md, README.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
