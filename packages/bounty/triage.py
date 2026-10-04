"""packages/bounty/triage.py — decide which bounties are worth an attempt.

Deterministic on purpose: an LLM is not asked whether to spend money. The
filters encode what a public census of Algora bounties found — most "open"
bounties are already paid (Algora pays by comment and leaves the label on),
sit in archived repos, or are swarmed by competing attempts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from packages.bounty.ledger import AgentProfile, agent_for_language
from packages.bounty.models import Bounty, Verdict
from packages.config.bounty_settings import BountySettings

_PAID_RE = re.compile(
    r"(rewarded|awarded|has been paid|paid out|payment (?:sent|completed)|"
    r"bounty (?:has been )?claimed by)",
    re.IGNORECASE,
)
_ATTEMPT_RE = re.compile(r"(^|\s)/(attempt|claim)\b", re.IGNORECASE)
_AI_BAN_RE = re.compile(
    r"(no|not accept\w*|prohibit\w*|ban\w*|disallow\w*|reject\w*|forbid\w*|close\w*)"
    r"[^.\n]{0,80}\b(AI|LLM|ChatGPT|Copilot|machine[- ]generated|AI[- ]generated)\b"
    r"|\b(AI|LLM)[- ]generated\b[^.\n]{0,60}\b(not|won't|will not|never)\b[^.\n]{0,30}"
    r"\b(accept\w*|merge\w*|review\w*)",
    re.IGNORECASE,
)


@dataclass
class TriageInput:
    """Everything triage needs about one candidate, fetched beforehand."""

    bounty: Bounty
    repo_info: dict[str, Any]
    comments: list[dict[str, Any]] = field(default_factory=list)
    policy_text: str = ""


def _age_days(when: datetime | None, now: datetime) -> float:
    if when is None:
        return 0.0
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (now - when).total_seconds() / 86400


def _parse(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


def count_competitors(comments: list[dict[str, Any]], own_login: str) -> int:
    """Distinct other users who announced an attempt or a claim."""
    authors = {
        str((c.get("user") or {}).get("login", "")).lower()
        for c in comments
        if _ATTEMPT_RE.search(str(c.get("body") or ""))
    }
    authors.discard(own_login.lower())
    authors.discard("")
    return len(authors)


def already_paid(comments: list[dict[str, Any]]) -> bool:
    """True when a bot comment says the bounty was awarded or paid."""
    for comment in comments:
        user = comment.get("user") or {}
        is_bot = str(user.get("type", "")) == "Bot" or str(user.get("login", "")).endswith("[bot]")
        if is_bot and _PAID_RE.search(str(comment.get("body") or "")):
            return True
    return False


def bans_ai(policy_text: str) -> bool:
    """True when the repo's contribution policy appears to refuse AI-made PRs."""
    return bool(_AI_BAN_RE.search(policy_text or ""))


def _hard_rejections(item: TriageInput, settings: BountySettings, now: datetime) -> list[str]:
    bounty, info = item.bounty, item.repo_info
    reasons: list[str] = []
    if info.get("archived") or info.get("disabled"):
        reasons.append("repository is archived")
    if bounty.amount_usd < settings.min_usd:
        reasons.append(f"amount ${bounty.amount_usd} below minimum ${settings.min_usd}")
    if already_paid(item.comments):
        reasons.append("bounty already awarded")
    if bans_ai(item.policy_text):
        reasons.append("contribution policy refuses AI-generated PRs")
    if _age_days(bounty.created_at, now) > settings.max_issue_age_days:
        reasons.append("issue older than the age limit")
    if _age_days(_parse(info.get("pushed_at")), now) > settings.max_repo_idle_days:
        reasons.append("repository looks unmaintained")
    return reasons


def triage(
    item: TriageInput,
    settings: BountySettings,
    roster: tuple[AgentProfile, ...],
    *,
    now: datetime | None = None,
) -> Verdict:
    """Accept or reject one candidate and score it by expected value."""
    now = now or datetime.now(timezone.utc)
    reasons = _hard_rejections(item, settings, now)
    competitors = count_competitors(item.comments, settings.github_login)
    if competitors > settings.max_competitors:
        reasons.append(f"{competitors} competing attempts")
    agent = agent_for_language(roster, str(item.repo_info.get("language") or ""))
    if agent is None:
        reasons.append(f"no agent covers language {item.repo_info.get('language')!r}")
    if reasons:
        return Verdict(accept=False, competitors=competitors, reasons=reasons)
    win_probability = 1.0 / (1 + competitors)
    freshness = max(0.25, 1.0 - _age_days(item.bounty.created_at, now) / (2 * settings.max_issue_age_days))
    score = round(item.bounty.amount_usd * win_probability * freshness, 2)
    return Verdict(
        accept=True,
        score=score,
        agent_id=agent.agent_id if agent else "",
        competitors=competitors,
        reasons=[f"${item.bounty.amount_usd}, {competitors} competitor(s)"],
    )
