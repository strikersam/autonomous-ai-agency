"""agent/sam_router.py — turn the Commander's sentence into one SAM action.

An LLM picks a tool from :data:`agent.sam_tools.TOOLS` and fills its arguments
as strict JSON; the arguments are validated against the tool's Pydantic model.
Anything that fails — no LLM, a timeout, prose instead of JSON, an unknown tool,
bad arguments — returns ``None`` and SAM falls back to ordinary chat. The router
never guesses an action.

Only the Commander's *current* sentence (plus the screen) reaches the router —
never conversation history. History can carry untrusted text (web-search titles,
trend headlines); keeping it out means none of it can be replayed into an action.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass

from pydantic import BaseModel

log = logging.getLogger("qwen-proxy")

_ROUTER_TIMEOUT_SEC = 15.0
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_SYSTEM = """You route the Commander's request to exactly one agency action.

Actions:
{tools}

Reply with ONLY a JSON object, no prose:
{{"tool": "<action name>", "args": {{...}}}}
Use {{"tool": "answer"}} when the Commander is asking a question or chatting rather
than asking for something to be done. Use "delegate" for any job none of the
other actions covers. Control keys are UPPER_SNAKE_CASE env names; booleans are
"true"/"false" strings."""


@dataclass(frozen=True)
class RoutedAction:
    tool: str
    args: BaseModel


def _parse(raw: str) -> tuple[str, dict] | None:
    match = _JSON_RE.search(raw or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("tool"), str):
        return None
    args = data.get("args") or {}
    return (data["tool"], args) if isinstance(args, dict) else None


async def _ask_llm(text: str, screen: str) -> str:
    from agent.sam_tools import catalogue_prompt
    from backend.server import call_llm

    user = f"Screen: {screen or 'unknown'}\nCommander: {text}"
    return await call_llm(
        messages=[{"role": "system", "content": _SYSTEM.format(tools=catalogue_prompt())},
                  {"role": "user", "content": user}],
        temperature=0.0,
        max_retries=1,
        provider_timeout_sec=_ROUTER_TIMEOUT_SEC,
    )


async def route(text: str, screen: str = "") -> RoutedAction | None:
    """The action *text* asks for, or None (answer in chat)."""
    from agent.sam_tools import TOOLS

    try:
        raw = await asyncio.wait_for(_ask_llm(text, screen), timeout=_ROUTER_TIMEOUT_SEC + 2)
    except Exception as exc:
        log.info("SAM router unavailable, falling back to chat: %s", exc)
        return None
    parsed = _parse(str(raw))
    if parsed is None:
        return None
    name, raw_args = parsed
    tool = TOOLS.get(name)
    if tool is None:
        return None
    args = tool.parse(raw_args)
    if args is None:
        log.info("SAM router: invalid args for %s, falling back to chat", name)
        return None
    return RoutedAction(tool=name, args=args)
