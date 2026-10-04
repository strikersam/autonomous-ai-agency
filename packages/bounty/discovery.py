"""packages/bounty/discovery.py — turn GitHub search results into bounty candidates.

Algora marks a funded issue with the ``💎 Bounty`` label and its bot posts the
amount in a comment ("💎 $250 bounty"). The amount is not always in the issue
body, so extraction looks at labels, title, bot comments and body, in that
order of trust.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from packages.bounty.models import Bounty, valid_repo

log = logging.getLogger("qwen-proxy")

ALGORA_LABEL = "💎 Bounty"
SEARCH_QUERY = f'label:"{ALGORA_LABEL}" state:open is:issue archived:false no:assignee'

_AMOUNT_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?\s*([kK])?\b")
_BOT_AMOUNT_RE = re.compile(r"💎\s*\$\s?(\d{1,3}(?:,\d{3})+|\d+)\s*([kK])?")


def _to_usd(number: str, kilo: str | None) -> int:
    value = int(number.replace(",", ""))
    return value * 1000 if kilo else value


def extract_amount(labels: list[str], title: str, bot_comments: list[str], body: str) -> int:
    """Best-effort bounty amount in whole USD; 0 when none is found."""
    for text in labels:
        match = _AMOUNT_RE.search(text)
        if match:
            return _to_usd(*match.groups())
    for text in bot_comments:
        match = _BOT_AMOUNT_RE.search(text)
        if match:
            return _to_usd(*match.groups())
    for text in (title, body):
        match = _AMOUNT_RE.search(text or "")
        if match:
            return _to_usd(*match.groups())
    return 0


def repo_from_item(item: dict[str, Any]) -> str:
    """``owner/name`` from a search item's ``repository_url``."""
    url = str(item.get("repository_url", ""))
    return url.split("/repos/", 1)[-1] if "/repos/" in url else ""


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def candidate_from_item(item: dict[str, Any], bot_comments: list[str]) -> Bounty | None:
    """Build a :class:`Bounty` from one search item, or ``None`` if unusable."""
    repo = repo_from_item(item)
    if not valid_repo(repo) or "pull_request" in item:
        return None
    labels = [str(lbl.get("name", "")) for lbl in item.get("labels", []) if isinstance(lbl, dict)]
    amount = extract_amount(labels, str(item.get("title", "")), bot_comments, str(item.get("body") or ""))
    try:
        return Bounty(
            repo=repo,
            issue_number=int(item.get("number", 0)),
            title=str(item.get("title", ""))[:300],
            url=str(item.get("html_url", "")),
            amount_usd=amount,
            labels=labels,
            comment_count=int(item.get("comments", 0) or 0),
            created_at=_parse_time(item.get("created_at")),
        )
    except (ValidationError, ValueError) as exc:
        log.info("bounty: skipping malformed search item %s: %s", item.get("html_url"), exc)
        return None
