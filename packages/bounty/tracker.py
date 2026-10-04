"""packages/bounty/tracker.py — hunt records stored as issues in this repository.

Each attempt is one issue labelled ``bounty-hunt`` plus ``bounty:<state>``. The
machine-readable record sits in an HTML comment so the issue stays readable
for the human reviewer. Issues are the store because the hunter runs in GitHub
Actions, where the dashboard database is not reachable, and because the review
decision itself is a label on that issue.
"""
from __future__ import annotations

import json
import re

from pydantic import ValidationError

from packages.bounty.models import BountyState, HuntRecord

TRACK_LABEL = "bounty-hunt"
LEDGER_LABEL = "bounty:ledger"
APPROVE_LABEL = "bounty:approved"
DECLINE_LABEL = "bounty:declined"

_RECORD_RE = re.compile(r"<!-- bounty-record:v1\n(.*?)\n-->", re.DOTALL)
_MAX_DIFF_CHARS = 30000


def neutralise(text: str) -> str:
    """Defang untrusted text before it lands in an issue: no @-pings, no fence breaks."""
    return (text or "").replace("@", "@\u200b").replace("```", "``\u200b`")


def state_label(state: BountyState) -> str:
    """The ``bounty:<state>`` label for *state*."""
    return f"bounty:{state.value}"


def labels_for(record: HuntRecord) -> list[str]:
    """Full label set a tracking issue should carry."""
    return [TRACK_LABEL, state_label(record.state)]


def parse_record(body: str) -> HuntRecord | None:
    """Recover the record embedded in an issue body, or ``None``."""
    match = _RECORD_RE.search(body or "")
    if not match:
        return None
    try:
        return HuntRecord.model_validate_json(match.group(1))
    except (ValidationError, ValueError):
        return None


def issue_title(record: HuntRecord) -> str:
    """Tracking issue title."""
    bounty = record.bounty
    title = neutralise(bounty.title)
    return f"[bounty ${bounty.amount_usd}] {bounty.repo}#{bounty.issue_number}: {title}"[:250]


def _review_block(record: HuntRecord, login: str) -> list[str]:
    if record.state is not BountyState.AWAITING_REVIEW:
        return []
    compare = (
        f"https://github.com/{record.bounty.repo}/compare/{record.base_branch}..."
        f"{login}:{record.fork_repo.split('/', 1)[-1]}:{record.branch}"
    )
    return [
        "### Your decision",
        f"- Review the change: {compare}",
        f"- Add the label `{APPROVE_LABEL}` to open the upstream PR under @{login} and claim the bounty.",
        f"- Add `{DECLINE_LABEL}` to drop it. Nothing is sent upstream until you approve.",
        "",
    ]


def render_body(record: HuntRecord, login: str, diff: str = "", test_log: str = "") -> str:
    """Human-readable issue body with the record embedded."""
    bounty = record.bounty
    parts = [
        f"**Bounty:** ${bounty.amount_usd} on {bounty.platform} — {bounty.url}",
        f"**Agent:** `{record.agent_id}` · **State:** `{record.state.value}` · "
        f"**Score:** {record.score} · **Tests:** {record.tests}",
        f"**Triage:** {'; '.join(record.reasons) or '—'}",
        "",
        f"**Summary:** {neutralise(record.summary) or '—'}",
        "",
        *_review_block(record, login),
    ]
    if record.upstream_pr:
        parts.append(f"**Upstream PR:** https://github.com/{bounty.repo}/pull/{record.upstream_pr}\n")
    if diff:
        clipped = neutralise(diff[:_MAX_DIFF_CHARS])
        parts += ["<details><summary>Diff</summary>", "", "```diff", clipped, "```", "</details>", ""]
    if test_log:
        parts += ["<details><summary>Test log (tail)</summary>", "", "```", neutralise(test_log[-4000:]), "```",
                  "</details>", ""]
    parts.append("<!-- bounty-record:v1\n" + record.model_dump_json() + "\n-->")
    return "\n".join(parts)


def rerender(body: str, record: HuntRecord, login: str) -> str:
    """Rebuild the header and record for a new state, keeping the diff and test log."""
    without_record = _RECORD_RE.sub("", body or "")
    marker = without_record.find("<details>")
    details = without_record[marker:].strip() if marker >= 0 else ""
    fresh = render_body(record, login)
    if not details:
        return fresh
    head, _, record_block = fresh.rpartition("<!-- bounty-record:v1")
    return f"{head}{details}\n\n<!-- bounty-record:v1{record_block}"


def ledger_body(table: str) -> str:
    """Body for the single ledger issue."""
    return "\n".join([
        "Profit and loss for every bounty-hunter agent, rewritten after each run.",
        "Review time is charged as cost, so agents that waste it get retired.",
        "",
        table,
        "",
        "<!-- bounty-ledger -->",
    ])


def dump(record: HuntRecord) -> str:
    """Compact JSON for logs and tests."""
    return json.dumps(json.loads(record.model_dump_json()), sort_keys=True)
