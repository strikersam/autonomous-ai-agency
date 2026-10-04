"""packages/bounty/platforms.py — the bounty platforms the hunter knows how to work.

Each platform is a GitHub search that finds its funded issues plus the text a
pull request must carry for the platform to route the payout.

* Algora: funded issues carry the ``💎 Bounty`` label; ``/claim #N`` in the PR
  body claims, and the payout lands through Stripe Connect after merge.
* Opire: funded issues have an Opire bot comment; ``/claim #N`` in the PR body
  claims. Discovery searches comment text for "opire" rather than naming the
  bot account, which could not be verified when this was written.
* generic: anything labelled ``bounty``. The payout route is whatever the issue
  says, so it is off by default and every record says "check the issue".

IssueHunt is deliberately absent: it takes submissions through its website, not
through PR text, so it cannot be claimed from here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Platform:
    """How to find and claim bounties on one platform."""

    platform_id: str
    search_query: str
    payout_note: str

    def claim_text(self, issue_number: int) -> str:
        """Lines a PR body needs so the platform credits the author."""
        lines = [f"Fixes #{issue_number}"]
        if self.platform_id in {"algora", "opire"}:
            lines.append(f"/claim #{issue_number}")
        return "\n\n".join(lines)


_BASE = "state:open is:issue archived:false no:assignee"

PLATFORMS: dict[str, Platform] = {
    "algora": Platform("algora", f'label:"💎 Bounty" {_BASE}',
                       "Paid by Algora via Stripe Connect after merge."),
    "opire": Platform("opire", f'"opire" in:comments {_BASE}',
                      "Paid by Opire after merge; claim with /claim in the PR."),
    "generic": Platform("generic", f"label:bounty {_BASE}",
                        "Payout route is set by the issue — check it before submitting."),
}


def enabled_platforms(csv: str) -> list[Platform]:
    """Platforms named in a comma-separated setting, in that order, unknown ids dropped."""
    wanted = [part.strip().lower() for part in csv.split(",") if part.strip()]
    return [PLATFORMS[pid] for pid in wanted if pid in PLATFORMS]
