"""agent/ceo_playbook.py — the CEO learns from what its directives actually did.

Before this, the CEO issued directives and never saw how they ended. The four
tasks that timed out at 600s every ten minutes on 2026-09-26 were re-issued
until each hit its retry cap, and nothing upstream noticed the pattern. This
module closes that loop, adapting two ideas:

* **Outcome scoreboard** (Paperclip: management reviews results, not
  activity). Each CEO cycle sees the last seven days of task outcomes per role
  (done / failed / blocked / timed out) and the directives that keep failing.
* **Playbook of evidence-backed beliefs** (Hindsight: mental models refined by
  evidence, not overwritten). Every terminal task outcome is counted once
  against its directive's signature and its role. From those counts the CEO
  derives standing beliefs: "this directive keeps failing — split it or drop
  it", "this role is reliable", "this role is struggling". A belief's weight
  is net evidence, halved every ``_HALF_LIFE_DAYS`` without new evidence, so a
  stale belief fades instead of ruling forever.

Beliefs are derived deterministically from counts, not written by an LLM: the
CEO runs on free open-weights models, and a belief it could hallucinate would
be a belief it could also hallucinate away. The playbook's source of truth is
the task store, which is durable in production, so a lost playbook document
relearns itself from task history. Directives the CEO invents, but never
owner-requested ones, are suppressed at dispatch while an "avoid" belief
carries at least ``_SUPPRESS_WEIGHT`` of evidence.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import time
from collections import Counter, defaultdict
from typing import Any

from packages.config import settings

log = logging.getLogger("qwen-proxy")

_HALF_LIFE_DAYS = 14.0
_WINDOW_DAYS = 7.0
_MIN_ROLE_SAMPLES = 3
_SUPPRESS_WEIGHT = 2.0
_MAX_SEEN = 2000
_MAX_SUBJECTS = 300
_ROLE_TAG_PREFIXES = ("priority-", "runtime-")
_DOC_ID = "playbook"


# ── Task classification ───────────────────────────────────────────────────────


def signature(title: str) -> str:
    """Stable key for a directive, shared by its task title (``agency: <title>``)."""
    text = (title or "").strip()
    if text.lower().startswith("agency:"):
        text = text.split(":", 1)[1]
    text = re.sub(r"\d+", "#", text.lower())
    return re.sub(r"\s+", " ", text).strip()[:80]


def role_of(task: Any) -> str | None:
    """The agency role a CEO directive was issued to, from its task tags."""
    tags = list(getattr(task, "tags", None) or [])
    if "agency" not in tags:
        return None
    for tag in tags:
        if tag != "agency" and ":" not in tag and not tag.startswith(_ROLE_TAG_PREFIXES):
            return tag
    return None


def outcome_of(task: Any) -> str:
    """``success``, ``timeout``, ``failure`` or ``open`` for one task."""
    status = str(getattr(getattr(task, "status", ""), "value", getattr(task, "status", "")))
    reason = f"{getattr(task, 'error_message', '') or ''} {getattr(task, 'blocked_reason', '') or ''}"
    if status == "done":
        return "success"
    if status in {"failed", "blocked"}:
        return "timeout" if "timed out" in reason.lower() else "failure"
    return "open"


def _ts(value: Any) -> float:
    from tasks.store import _ts_to_float

    try:
        return _ts_to_float(value) if value else 0.0
    except Exception:  # noqa: BLE001 - a malformed timestamp just ages out
        return 0.0


# ── Durable store (Mongo in production, SQLite in dev, memory in tests) ──────


class PlaybookStore:
    """One JSON document holding the CEO's counts. Never raises."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._mem: dict[str, Any] = {}
        self._mongo: Any = None
        self._sqlite: sqlite3.Connection | None = None
        if settings.is_testing:
            return
        if settings.storage_backend == "sqlite":
            self._open_sqlite()
        else:
            self._open_mongo()

    def _open_mongo(self) -> None:
        try:
            import pymongo

            client = pymongo.MongoClient(settings.mongo_url, serverSelectionTimeoutMS=2000)
            client.admin.command("ping")
            self._mongo = client[settings.db_name]["ceo_playbook"]
        except Exception as exc:  # noqa: BLE001
            log.warning("CEO playbook: Mongo unavailable (%s); memory only", exc)

    def _open_sqlite(self) -> None:
        try:
            self._sqlite = sqlite3.connect(settings.sqlite_db_path, check_same_thread=False)
            self._sqlite.execute(
                "CREATE TABLE IF NOT EXISTS ceo_playbook (id TEXT PRIMARY KEY, doc TEXT NOT NULL)"
            )
            self._sqlite.commit()
        except Exception as exc:  # noqa: BLE001
            log.warning("CEO playbook: SQLite unavailable (%s); memory only", exc)
            self._sqlite = None

    def load(self) -> dict[str, Any]:
        try:
            if self._mongo is not None:
                doc = self._mongo.find_one({"_id": _DOC_ID}) or {}
                return dict(doc.get("doc") or {})
            if self._sqlite is not None:
                with self._lock:
                    row = self._sqlite.execute(
                        "SELECT doc FROM ceo_playbook WHERE id = ?", (_DOC_ID,)
                    ).fetchone()
                return json.loads(row[0]) if row else {}
        except Exception as exc:  # noqa: BLE001
            log.warning("CEO playbook load failed: %s", exc)
        return json.loads(json.dumps(self._mem))

    def save(self, doc: dict[str, Any]) -> None:
        try:
            if self._mongo is not None:
                self._mongo.replace_one({"_id": _DOC_ID}, {"_id": _DOC_ID, "doc": doc}, upsert=True)
                return
            if self._sqlite is not None:
                with self._lock:
                    self._sqlite.execute(
                        "INSERT OR REPLACE INTO ceo_playbook (id, doc) VALUES (?, ?)",
                        (_DOC_ID, json.dumps(doc)),
                    )
                    self._sqlite.commit()
                return
        except Exception as exc:  # noqa: BLE001
            log.warning("CEO playbook save failed: %s", exc)
        self._mem = json.loads(json.dumps(doc))


# ── Learning ──────────────────────────────────────────────────────────────────


def learn(doc: dict[str, Any], tasks: list[Any], *, now: float | None = None) -> int:
    """Count each terminal task outcome once into *doc*; return how many were new."""
    now = time.time() if now is None else now
    seen: dict[str, str] = doc.setdefault("seen", {})
    subjects: dict[str, dict[str, Any]] = doc.setdefault("subjects", {})
    roles: dict[str, dict[str, int]] = doc.setdefault("roles", {})
    new = 0
    for task in tasks:
        outcome = outcome_of(task)
        task_id = str(getattr(task, "task_id", "") or "")
        if outcome == "open" or not task_id or seen.get(task_id) == outcome:
            continue
        seen[task_id] = outcome
        new += 1
        sig = signature(getattr(task, "title", ""))
        entry = subjects.setdefault(sig, {"title": getattr(task, "title", "")[:120],
                                          "success": 0, "failure": 0, "timeout": 0})
        entry[outcome] += 1
        entry["updated_at"] = now
        role = role_of(task)
        if role:
            bucket = roles.setdefault(role, {"success": 0, "failure": 0})
            bucket["success" if outcome == "success" else "failure"] += 1
            bucket["updated_at"] = now
    _bound(doc)
    return new


def _bound(doc: dict[str, Any]) -> None:
    seen = doc.get("seen", {})
    for key in list(seen)[: max(len(seen) - _MAX_SEEN, 0)]:
        del seen[key]
    subjects = doc.get("subjects", {})
    if len(subjects) > _MAX_SUBJECTS:
        keep = sorted(subjects, key=lambda k: subjects[k].get("updated_at", 0))[-_MAX_SUBJECTS:]
        doc["subjects"] = {k: subjects[k] for k in keep}


def _weight(entry: dict[str, Any], now: float) -> float:
    net = entry.get("failure", 0) + entry.get("timeout", 0) - entry.get("success", 0)
    age_days = max(now - float(entry.get("updated_at", now)), 0.0) / 86400.0
    return net * 0.5 ** (age_days / _HALF_LIFE_DAYS)


def beliefs(doc: dict[str, Any], *, now: float | None = None, limit: int = 8) -> list[str]:
    """The CEO's current standing beliefs, strongest first."""
    now = time.time() if now is None else now
    ranked: list[tuple[float, str]] = []
    for entry in doc.get("subjects", {}).values():
        weight = _weight(entry, now)
        fails = entry.get("failure", 0) + entry.get("timeout", 0)
        if fails >= 2 and weight >= 1.0:
            timeouts = f", {entry['timeout']} timed out" if entry.get("timeout") else ""
            ranked.append((weight, (
                f"AVOID: \"{entry['title']}\" failed {fails}x{timeouts}, succeeded "
                f"{entry.get('success', 0)}x. Do not reissue it as one task: split it into "
                "smaller steps with explicit file paths, or drop it."
            )))
    for role, counts in doc.get("roles", {}).items():
        total = counts.get("success", 0) + counts.get("failure", 0)
        # The rate is what it is; how much it counts fades like any other evidence.
        age_days = max(now - float(counts.get("updated_at", now)), 0.0) / 86400.0
        if round(total * 0.5 ** (age_days / _HALF_LIFE_DAYS), 3) < _MIN_ROLE_SAMPLES:
            continue
        rate = counts.get("success", 0) / total
        if rate >= 0.7:
            ranked.append((rate, f"RELIABLE: role {role} completed {counts['success']}/{total} directives."))
        elif rate <= 0.3:
            ranked.append((1 - rate, (
                f"STRUGGLING: role {role} completed only {counts.get('success', 0)}/{total} "
                "directives. Give it smaller, more explicit tasks."
            )))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [text for _, text in ranked[:limit]]


def suppression_reason(doc: dict[str, Any], title: str, *, now: float | None = None) -> str | None:
    """Why a CEO directive with *title* should not be dispatched, or ``None``."""
    now = time.time() if now is None else now
    entry = doc.get("subjects", {}).get(signature(title))
    if not entry:
        return None
    weight = _weight(entry, now)
    if weight < _SUPPRESS_WEIGHT:
        return None
    fails = entry.get("failure", 0) + entry.get("timeout", 0)
    return f"failed {fails}x and succeeded {entry.get('success', 0)}x (evidence {weight:.1f})"


def scoreboard(tasks: list[Any], *, now: float | None = None) -> dict[str, Any]:
    """Last ``_WINDOW_DAYS`` of outcomes per role plus the directives failing most."""
    now = time.time() if now is None else now
    cutoff = now - _WINDOW_DAYS * 86400
    per_role: dict[str, Counter] = defaultdict(Counter)
    failing: Counter = Counter()
    for task in tasks:
        if _ts(getattr(task, "updated_at", 0)) < cutoff:
            continue
        outcome = outcome_of(task)
        per_role[role_of(task) or str(getattr(task, "task_type", "other"))][outcome] += 1
        if outcome in {"failure", "timeout"}:
            failing[getattr(task, "title", "")[:80]] += 1
    return {
        "roles": {role: dict(counts) for role, counts in sorted(per_role.items())},
        "repeat_failures": [t for t, n in failing.most_common(5) if n >= 2],
    }


def render(board: dict[str, Any], standing: list[str], lessons: str) -> str:
    """The CEO prompt section for everything learned; '' when there is nothing."""
    lines: list[str] = []
    if board.get("roles"):
        lines.append(f"## Outcomes, last {int(_WINDOW_DAYS)} days (done / failed / timed out / open)")
        for role, c in board["roles"].items():
            lines.append(f"  {role}: {c.get('success', 0)} / {c.get('failure', 0)} / "
                         f"{c.get('timeout', 0)} / {c.get('open', 0)}")
    if board.get("repeat_failures"):
        lines.append("Failing repeatedly: " + "; ".join(board["repeat_failures"]))
    if standing:
        lines.append("\n## CEO Playbook — beliefs learned from your own results")
        lines.extend(f"  - {b}" for b in standing)
    if lessons:
        lines.append("\n## " + lessons)
    return "\n".join(lines)


# ── Cycle entry points ────────────────────────────────────────────────────────

_store: PlaybookStore | None = None
_doc: dict[str, Any] = {}


def _get_store() -> PlaybookStore:
    global _store
    if _store is None:
        _store = PlaybookStore()
    return _store


async def learning_context(limit: int = 300) -> str:
    """Learn from recent task outcomes and return the CEO prompt block. Never raises."""
    global _doc
    try:
        from agent.lessons import recent_lessons_block
        from tasks.store import get_task_store

        tasks = await get_task_store().list_all(limit=limit, include_log=False)
        store = _get_store()
        doc = store.load()
        if learn(doc, tasks):
            store.save(doc)
        _doc = doc
        return render(scoreboard(tasks), beliefs(doc), recent_lessons_block())
    except Exception as exc:  # noqa: BLE001 - learning must never stop a CEO cycle
        log.warning("CEO learning context unavailable: %s", exc)
        return ""


def should_suppress(title: str) -> str | None:
    """Suppression reason for a CEO-invented directive, from the last learned playbook."""
    from packages.config.autonomy_limits import ceo_playbook_enforced

    if not ceo_playbook_enforced():
        return None
    try:
        return suppression_reason(_doc, title)
    except Exception:  # noqa: BLE001
        return None


def snapshot() -> dict[str, Any]:
    """The playbook as last learned, for the dashboard and tests."""
    return {"beliefs": beliefs(_doc), "subjects": len(_doc.get("subjects", {})),
            "roles": dict(_doc.get("roles", {}))}
