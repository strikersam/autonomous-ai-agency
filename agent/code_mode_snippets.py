from __future__ import annotations

"""Code Mode phase 5: saved programs an agent can re-run by name.

A ``run_code`` program that solved a lookup can be saved with the
``save_snippet`` tool and replayed later with ``snippets.run(name, **args)``
inside another program, so a repeated multi-step lookup costs one call. This is
Cloudflare Code Mode's ``codemode.run``.

Snippets are scoped to a user (the agent run's ``user_id``; runs without one
share ``"_shared"``), checked with :func:`agent.code_mode.validate` before they
are stored, and capped in size and number. They hold program text only: the
interpreter, its limits and its read-only tool reach apply again on every run.
Memory is the hot copy; when state persistence is on each save is mirrored to
the ``code_mode_snippets`` collection and a memory miss falls back to it.
"""

import asyncio
import logging
import re
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any

from packages.storage import state_persistence as _persist

log = logging.getLogger("qwen-proxy")

COLLECTION = "code_mode_snippets"
MAX_CODE_CHARS = 4000
MAX_DESCRIPTION_CHARS = 200
MAX_PER_SCOPE = 50
SHARED_SCOPE = "_shared"
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


@dataclass
class Snippet:
    """One saved program."""

    name: str
    description: str
    code: str
    scope: str
    saved_at: float


def snippets_enabled() -> bool:
    """Read AGENT_CODE_MODE_SNIPPETS_ENABLED at call time (live control)."""
    try:
        from packages.config import settings

        return settings.agent_code_mode_snippets
    except Exception as exc:  # noqa: BLE001 - unreadable setting keeps snippets off
        log.debug("AGENT_CODE_MODE_SNIPPETS_ENABLED unreadable: %s", exc)
        return False


def scope_for(user_id: str | None) -> str:
    return str(user_id) if user_id else SHARED_SCOPE


def check(name: Any, code: Any, description: Any) -> str | None:
    """Why this snippet cannot be saved, or None when it can."""
    from agent.code_mode import CodeModeError, validate

    if not isinstance(name, str) or not _NAME_RE.match(name):
        return "name must be lowercase letters, digits and '_' (start with a letter, max 40)"
    if not isinstance(code, str) or not code.strip() or len(code) > MAX_CODE_CHARS:
        return f"code must be a non-empty program of at most {MAX_CODE_CHARS} characters"
    if not isinstance(description, str) or len(description) > MAX_DESCRIPTION_CHARS:
        return f"description must be text of at most {MAX_DESCRIPTION_CHARS} characters"
    try:
        validate(code)
    except CodeModeError as exc:
        return f"code is not a valid run_code program: {exc}"
    return None


class SnippetStore:
    """Per-scope snippets in memory, mirrored to the DB when persistence is on."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Snippet]] = {}
        self._lock = threading.Lock()

    def save(self, scope: str, name: str, code: str, description: str) -> str | None:
        """Store the snippet; returns an error message or None."""
        problem = check(name, code, description)
        if problem:
            return problem
        with self._lock:
            bucket = self._items.setdefault(scope, {})
            if name not in bucket and len(bucket) >= MAX_PER_SCOPE:
                return f"at most {MAX_PER_SCOPE} snippets; overwrite an existing name instead"
            snippet = Snippet(name, description, code, scope, time.time())
            bucket[name] = snippet
        _persist.fire_and_forget(self._write(snippet))
        return None

    def get(self, scope: str, name: str) -> Snippet | None:
        with self._lock:
            return self._items.get(scope, {}).get(name)

    def list(self, scope: str) -> list[dict[str, str]]:
        with self._lock:
            bucket = dict(self._items.get(scope, {}))
        return [{"name": s.name, "description": s.description} for s in sorted(bucket.values(), key=lambda s: s.name)]

    async def get_async(self, scope: str, name: str) -> Snippet | None:
        """Memory first, then the DB mirror (survives a restart)."""
        hit = self.get(scope, name)
        if hit is not None:
            return hit
        col = _persist.collection(COLLECTION)
        if col is None:
            return None
        try:
            doc = await asyncio.wait_for(col.find_one({"_id": f"{scope}:{name}"}), timeout=5)
        except Exception as exc:  # noqa: BLE001 - a miss is not an error
            log.debug("snippet %s unreadable from DB: %s", name, exc)
            return None
        if not doc or check(doc.get("name"), doc.get("code"), doc.get("description", "")):
            return None
        snippet = Snippet(doc["name"], doc.get("description", ""), doc["code"], scope, float(doc.get("saved_at", 0)))
        with self._lock:
            self._items.setdefault(scope, {})[name] = snippet
        return snippet

    async def _write(self, snippet: Snippet) -> None:
        col = _persist.collection(COLLECTION)
        if col is None:
            return
        try:
            doc = {"_id": f"{snippet.scope}:{snippet.name}", **asdict(snippet)}
            await col.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        except Exception as exc:  # noqa: BLE001 - memory copy still serves this worker
            _persist.warn_limited("snippet-write", "snippet %s not persisted: %s", snippet.name, exc)


_store: SnippetStore | None = None
_store_lock = threading.Lock()


def get_snippet_store() -> SnippetStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = SnippetStore()
        return _store


def reset_store() -> None:
    """Drop the singleton (tests)."""
    global _store
    with _store_lock:
        _store = None
