"""packages/bounty/models.py — data shapes for the bounty hunter."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator

_REPO_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}$")


def valid_repo(full_name: str) -> bool:
    """True when *full_name* is a plausible ``owner/name`` GitHub slug."""
    return bool(_REPO_RE.match(full_name or "")) and ".." not in full_name


class BountyState(str, Enum):
    """Lifecycle of one hunt record. Terminal states close the tracking issue."""

    FAILED = "failed"                    # solver gave up or the patch failed a guard
    AWAITING_REVIEW = "awaiting-review"  # branch pushed to the fork; human decides
    DECLINED = "declined"                # human said no
    SUBMITTED = "submitted"              # upstream PR opened with /claim
    MERGED = "merged"                    # maintainer merged; payout pending
    PAID = "paid"                        # Algora payout observed
    LOST = "lost"                        # PR closed unmerged, or bounty gone

    @property
    def terminal(self) -> bool:
        """True when no further transition is expected."""
        return self in {BountyState.FAILED, BountyState.DECLINED,
                        BountyState.PAID, BountyState.LOST}


class Bounty(BaseModel):
    """One bounty-carrying issue on a third-party repository."""

    platform: str = "algora"
    repo: str
    issue_number: int = Field(gt=0)
    title: str
    url: str
    amount_usd: int = Field(ge=0)
    labels: list[str] = Field(default_factory=list)
    comment_count: int = 0
    created_at: datetime | None = None

    @field_validator("repo")
    @classmethod
    def _check_repo(cls, value: str) -> str:
        if not valid_repo(value):
            raise ValueError(f"invalid repository slug: {value!r}")
        return value

    @property
    def key(self) -> str:
        """Stable identity used to de-duplicate attempts."""
        return f"{self.repo}#{self.issue_number}".lower()


class Verdict(BaseModel):
    """Triage outcome for a candidate bounty."""

    accept: bool
    score: float = 0.0
    agent_id: str = ""
    competitors: int = 0
    reasons: list[str] = Field(default_factory=list)


class HuntRecord(BaseModel):
    """Everything the ledger needs to know about one attempt."""

    bounty: Bounty
    agent_id: str
    state: BountyState
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    fork_repo: str = ""
    branch: str = ""
    base_branch: str = ""
    upstream_pr: int = 0
    tests: str = "unverified"
    tokens_used: int = 0
    llm_cost_usd: float = 0.0
    revenue_usd: float = 0.0
    summary: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def reached_review(self) -> bool:
        """True once a human has been asked to spend time on this attempt."""
        return self.state not in {BountyState.FAILED}
