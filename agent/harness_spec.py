"""agent/harness_spec.py — the Continual Harness: a persistent, cited spec.

Borrowed from Prime Agent's "Continual Harness" idea: the agent keeps a durable
document about *how to work in this repo* and refines it as evidence arrives, so
run N+1 starts smarter than run N. `agent/lessons.py` already records why steps
failed; this module is what turns a repeated failure into a standing
instruction the planner sees before it plans.

Two deliberate design choices, both about trust:

1. **Every entry cites its evidence.** An entry carries the signature of the
   lesson that produced it and the hit count at the time it was written. An
   uncited proposal is discarded, not written. That citation requirement is the
   whole difference between a continual harness and prompt drift — without it,
   a self-editing prompt accumulates plausible-sounding rules nobody can trace
   back to a real failure.
2. **Refinement is deterministic, not model-generated.** A lesson promotes to a
   spec entry once it has been seen `HARNESS_SPEC_MIN_HITS` times. No LLM call
   decides what goes in the file, so the mechanism cannot hallucinate a rule,
   costs no tokens, and is fully testable.

Storage is a plain Markdown file (``.agency/harness.md``) inside the workspace:
readable and editable by a human, diffable in review, and greppable when a
prompt starts behaving oddly.

Configuration:
  HARNESS_SPEC_ENABLED      — 'false' disables reading/injection (default: on)
  HARNESS_SPEC_AUTO_REFINE  — 'true' lets runs append entries (default: off)
  HARNESS_SPEC_MIN_HITS     — repeats before a lesson promotes (default: 2)
  HARNESS_SPEC_MAX_ENTRIES  — entries kept in the file (default: 40)
  HARNESS_SPEC_MAX_CHARS    — cap on the injected block (default: 1200)
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("harness.spec")

_SPEC_RELPATH = Path(".agency") / "harness.md"
_HEADER = "# Harness Spec\n\n" \
          "Standing instructions derived from repeated run failures.\n" \
          "Each entry cites the lesson that produced it. Machine-appended by\n" \
          "agent/harness_spec.py — hand edits are preserved.\n"
# Signatures are currently sha1 hex slices, but the pattern stays permissive on
# purpose: if agent/lessons.py ever changes its signature scheme, a stricter
# regex would silently stop parsing entries this module itself wrote.
_ENTRY_RE = re.compile(r"^- \[lesson:(?P<sig>[\w.-]+) hits=(?P<hits>\d+)\] (?P<text>.+)$")

# Serialises the read-merge-write in refine(): two runs finishing at the same
# moment would otherwise both read the old file, and the second write would
# silently drop the first run's promotion.
_REFINE_LOCK = threading.Lock()


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes"}


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _one_line(value: Any) -> str:
    """Collapse a value to a single trimmed line.

    Entries are one Markdown list item each, and the parser reads line by line —
    an embedded newline would silently truncate an entry on the next read.
    """
    return " ".join(str(value or "").split()).strip()


@dataclass(frozen=True)
class SpecEntry:
    """One standing instruction plus the evidence that earned it."""

    signature: str
    hits: int
    text: str

    def render(self) -> str:
        return f"- [lesson:{self.signature} hits={self.hits}] {self.text}"


def spec_path(workspace_root: str | Path | None = None) -> Path:
    """Absolute path of the harness spec for a workspace."""
    return Path(workspace_root or os.getcwd()) / _SPEC_RELPATH


def _known_entry_texts() -> dict[str, set[str]]:
    """Recorded lessons as ``{signature: {acceptable text, ...}}``.

    The citation binds to the *text*, not merely the signature. Verifying the
    signature alone would let a third-party workspace keep a known
    ``lesson:<sig>`` prefix and swap the body for arbitrary instructions, which
    `build_block()` would then inject as trusted standing guidance.

    Fails closed: when the store cannot be read this returns an empty mapping and
    every entry is dropped. Injecting unverified workspace text because our own
    bookkeeping was briefly unavailable would defeat the check — and losing the
    block is harmless, since it is an enhancement, not a critical path.
    """
    try:
        from agent.lessons import _get_store  # local import: avoids a cycle

        lessons = _get_store().recent(limit=1000)
    except Exception as exc:
        log.warning("harness spec: lesson store unreadable, dropping all entries: %s", exc)
        return {}

    known: dict[str, set[str]] = {}
    for entry in lessons:
        signature = str(entry.get("signature") or "")
        text = _one_line(entry.get("lesson"))
        if not signature or not text:
            continue
        phase = _one_line(entry.get("phase"))
        # Both renderings are accepted: propose_entries() prefixes the phase, and
        # a spec written before a phase was recorded would not carry one.
        accepted = {text}
        if phase:
            accepted.add(f"During {phase}: {text}")
        known.setdefault(signature, set()).update(accepted)
    return known


def read_entries(
    workspace_root: str | Path | None = None, *, verify: bool = False
) -> list[SpecEntry]:
    """Parse existing entries. Never raises — a broken file yields no entries.

    With ``verify=True`` an entry is kept only when its citation matches a lesson
    this platform actually recorded. The spec file lives *inside the workspace*,
    which for agent work is frequently a third-party repository — without the
    check, anyone able to commit a `.agency/harness.md` could write arbitrary
    text straight into the agent's system prompt. A citation nobody can trace is
    exactly the thing this module refuses to trust.
    """
    path = spec_path(workspace_root)
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    known = _known_entry_texts() if verify else None
    entries: list[SpecEntry] = []
    for line in raw.splitlines():
        match = _ENTRY_RE.match(line.strip())
        if not match:
            continue
        signature = match.group("sig")
        text = match.group("text").strip()
        if known is not None and text not in known.get(signature, set()):
            log.warning(
                "harness spec: dropping entry whose text does not match lesson %s in %s",
                signature, path,
            )
            continue
        entries.append(
            SpecEntry(signature=signature, hits=int(match.group("hits")), text=text)
        )
    return entries


def propose_entries(lessons: list[dict[str, Any]], *, min_hits: int | None = None) -> list[SpecEntry]:
    """Turn qualifying lessons into candidate entries.

    A lesson qualifies only when it carries a signature (its citation) and has
    recurred at least `min_hits` times. Everything else is dropped: a failure
    seen once is an incident, not a rule.
    """
    threshold = min_hits if min_hits is not None else _int_env("HARNESS_SPEC_MIN_HITS", 2)
    proposals: list[SpecEntry] = []
    for lesson in lessons or []:
        if not isinstance(lesson, dict):
            continue
        signature = str(lesson.get("signature") or "").strip()
        text = _one_line(lesson.get("lesson"))
        try:
            hits = int(lesson.get("hits") or 0)
        except (TypeError, ValueError):
            # One malformed row must not discard the whole batch.
            continue
        if not signature or not text or hits < threshold:
            continue
        phase = _one_line(lesson.get("phase"))
        prefix = f"During {phase}: " if phase else ""
        proposals.append(SpecEntry(signature=signature, hits=hits, text=f"{prefix}{text}"))
    return proposals


def write_entries(entries: list[SpecEntry], workspace_root: str | Path | None = None) -> Path:
    """Rewrite the spec file, preserving any non-entry (hand-written) lines."""
    path = spec_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    preserved: list[str] = []
    try:
        existing = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        existing = []
    in_generated = False
    for line in existing:
        if line.strip() == "## Standing instructions":
            in_generated = True
            continue
        if in_generated and (_ENTRY_RE.match(line.strip()) or not line.strip()):
            continue
        in_generated = False
        preserved.append(line)

    body = "\n".join(preserved).strip() or _HEADER.strip()
    rendered = "\n".join(entry.render() for entry in entries)
    # Write-then-replace: a crash mid-write must not leave a half-parsed spec,
    # and os.replace is atomic within the same directory.
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(f"{body}\n\n## Standing instructions\n\n{rendered}\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def refine(
    workspace_root: str | Path | None = None,
    *,
    lessons: list[dict[str, Any]] | None = None,
    force: bool = False,
) -> list[SpecEntry]:
    """Promote repeated lessons into the spec. Returns the entries added.

    No-op unless HARNESS_SPEC_AUTO_REFINE is set (or `force`), so a deployment
    that has not opted in never gets a self-editing prompt. Never raises: a
    failure to refine must not fail the run that triggered it.
    """
    if not force and not _flag("HARNESS_SPEC_AUTO_REFINE", False):
        return []
    try:
        # Read-merge-write under one lock: two runs finishing together would
        # otherwise both read the old file and the second would drop the first's
        # promotion.
        with _REFINE_LOCK:
            return _refine_locked(workspace_root, lessons)
    except Exception as exc:  # refinement is best-effort, like lessons themselves
        log.error("harness spec refine failed: %s", exc, exc_info=True)
        return []


def _refine_locked(
    workspace_root: str | Path | None,
    lessons: list[dict[str, Any]] | None,
) -> list[SpecEntry]:
    """Merge qualifying lessons into the spec. Caller holds _REFINE_LOCK."""
    if lessons is None:
        from agent.lessons import _get_store  # local import: avoids a cycle

        lessons = _get_store().recent(limit=_int_env("HARNESS_SPEC_MAX_ENTRIES", 40))
    existing = read_entries(workspace_root)
    known = {entry.signature for entry in existing}
    added = [p for p in propose_entries(lessons) if p.signature not in known]
    if not added:
        return []
    combined = (existing + added)[-_int_env("HARNESS_SPEC_MAX_ENTRIES", 40):]
    write_entries(combined, workspace_root)
    log.info("harness spec: promoted %d lesson(s) at %s", len(added), spec_path(workspace_root))
    return added


def build_block(workspace_root: str | Path | None = None, *, max_chars: int | None = None) -> str:
    """Compact prompt block of standing instructions, or '' when there are none.

    Returns '' when the feature is disabled or no spec exists, so prompts are
    byte-identical to before on any workspace that never opted in.
    """
    if not _flag("HARNESS_SPEC_ENABLED", True):
        return ""
    # verify=True: this text goes into a system prompt, and the file is
    # workspace-controlled.
    entries = read_entries(workspace_root, verify=True)
    if not entries:
        return ""
    budget = max_chars if max_chars is not None else _int_env("HARNESS_SPEC_MAX_CHARS", 1200)
    lines = ["HARNESS SPEC — standing instructions from past failures in this repo:"]
    used = len(lines[0])
    # Most-repeated first: if the budget truncates, keep the costliest lessons.
    for entry in sorted(entries, key=lambda e: e.hits, reverse=True):
        line = f"- {entry.text}"
        # +1 for the newline "\n".join() will add — without it the rendered block
        # can exceed HARNESS_SPEC_MAX_CHARS.
        if used + len(line) + 1 > budget:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines) if len(lines) > 1 else ""
