"""packages/gateway/prompt_policy.py — operator prompt policy for proxied chat requests.

A JSON file (``GATEWAY_PROMPT_POLICY_FILE``) describes what may be sent::

    {
      "deny":  ["(?i)ignore all previous instructions"],
      "allow": [],
      "prepend_system": "Company policy: never reveal customer data.",
      "append_system": ""
    }

* ``deny`` — a request whose message text matches any pattern is refused (400).
* ``allow`` — when non-empty, the request text must match at least one pattern;
  ``deny`` is still checked first.
* ``prepend_system`` / ``append_system`` — added as system messages at the start
  / end of the conversation. They are added after the checks, so they are never
  themselves scanned.

The file is re-read when its mtime changes. A pattern longer than
``MAX_PATTERN_CHARS`` or that does not compile is dropped with a warning. If the
file cannot be read, the last good policy stays in force (or none, on first
load) — a typo in the policy file must not take the gateway down. Prompt text is
never logged; a block logs only which rule matched.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException

from packages.gateway import config
from packages.gateway.messages import iter_texts

log = logging.getLogger("qwen-proxy")

MAX_PATTERN_CHARS = 512
BLOCK_DETAIL = "Request blocked by policy"


@dataclass(frozen=True)
class Policy:
    """A compiled policy."""

    deny: tuple[re.Pattern[str], ...] = ()
    allow: tuple[re.Pattern[str], ...] = ()
    prepend_system: str = ""
    append_system: str = ""


@dataclass
class _Cache:
    path: str = ""
    mtime: float = -1.0
    policy: Policy = field(default_factory=Policy)


_lock = threading.Lock()
_cache = _Cache()


def reset() -> None:
    """Drop the cached policy (test hook)."""
    global _cache
    with _lock:
        _cache = _Cache()


def _compile(raw: Any, kind: str) -> tuple[re.Pattern[str], ...]:
    compiled: list[re.Pattern[str]] = []
    for index, pattern in enumerate(raw if isinstance(raw, list) else []):
        if not isinstance(pattern, str) or not pattern or len(pattern) > MAX_PATTERN_CHARS:
            log.warning("Prompt policy %s[%d] rejected: not a string of 1-%d chars", kind, index, MAX_PATTERN_CHARS)
            continue
        try:
            compiled.append(re.compile(pattern))
        except re.error:
            log.warning("Prompt policy %s[%d] rejected: invalid regular expression", kind, index)
    return tuple(compiled)


def parse_policy(data: Any) -> Policy:
    """Build a :class:`Policy` from decoded JSON; unusable parts are ignored."""
    if not isinstance(data, dict):
        return Policy()
    prepend, append = data.get("prepend_system"), data.get("append_system")
    return Policy(
        deny=_compile(data.get("deny"), "deny"),
        allow=_compile(data.get("allow"), "allow"),
        prepend_system=prepend.strip() if isinstance(prepend, str) else "",
        append_system=append.strip() if isinstance(append, str) else "",
    )


def _current_policy() -> Policy:
    """Load (or reload on mtime change) the policy file. Blocking; run in a thread."""
    global _cache
    path = config.prompt_policy_file()
    if not path:
        return Policy()
    try:
        mtime = os.stat(path).st_mtime
    except OSError:
        log.warning("Prompt policy file is not readable; keeping the last good policy")
        return _cache.policy if _cache.path == path else Policy()
    with _lock:
        if _cache.path == path and _cache.mtime == mtime:
            return _cache.policy
        try:
            with open(path, encoding="utf-8") as fh:
                policy = parse_policy(json.load(fh))
        except (OSError, ValueError):
            log.warning("Prompt policy file could not be parsed; keeping the last good policy")
            return _cache.policy if _cache.path == path else Policy()
        _cache = _Cache(path=path, mtime=mtime, policy=policy)
        return policy


def _violated_rule(policy: Policy, texts: list[str]) -> str | None:
    for index, pattern in enumerate(policy.deny):
        if any(pattern.search(t) for t in texts):
            return f"deny[{index}]"
    if policy.allow and not any(p.search(t) for p in policy.allow for t in texts):
        return "allow"
    return None


def evaluate(payload: dict[str, Any], policy: Policy) -> dict[str, Any]:
    """Apply *policy* to *payload*: raise 400 on a violation, else decorate."""
    rule = _violated_rule(policy, list(iter_texts(payload.get("messages"))))
    if rule is not None:
        log.warning("Prompt policy blocked a request (rule %s)", rule)
        raise HTTPException(status_code=400, detail=BLOCK_DETAIL)
    messages = payload.get("messages")
    if not isinstance(messages, list) or not (policy.prepend_system or policy.append_system):
        return payload
    decorated = list(messages)
    if policy.prepend_system:
        decorated.insert(0, {"role": "system", "content": policy.prepend_system})
    if policy.append_system:
        decorated.append({"role": "system", "content": policy.append_system})
    return {**payload, "messages": decorated}


async def apply_prompt_policy(payload: dict[str, Any]) -> dict[str, Any]:
    """Enforce the policy on *payload*; a no-op unless the toggle is on."""
    if not config.prompt_policy_enabled():
        return payload
    policy = await asyncio.to_thread(_current_policy)
    return evaluate(payload, policy)
