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


def read_entries(workspace_root: str | Path | None = None) -> list[SpecEntry]:
    """Parse existing entries. Never raises — a broken file yields no entries."""
    path = spec_path(workspace_root)
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    entries: list[SpecEntry] = []
    for line in raw.splitlines():
        match = _ENTRY_RE.match(line.strip())
        if match:
            entries.append(
                SpecEntry(
                    signature=match.group("sig"),
                    hits=int(match.group("hits")),
                    text=match.group("text").strip(),
                )
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
        text = str(lesson.get("lesson") or "").strip()
        hits = int(lesson.get("hits") or 0)
        if not signature or not text or hits < threshold:
            continue
        phase = str(lesson.get("phase") or "").strip()
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
    path.write_text(f"{body}\n\n## Standing instructions\n\n{rendered}\n", encoding="utf-8")
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
    except Exception as exc:  # refinement is best-effort, like lessons themselves
        log.debug("harness spec refine skipped: %s", exc)
        return []


def build_block(workspace_root: str | Path | None = None, *, max_chars: int | None = None) -> str:
    """Compact prompt block of standing instructions, or '' when there are none.

    Returns '' when the feature is disabled or no spec exists, so prompts are
    byte-identical to before on any workspace that never opted in.
    """
    if not _flag("HARNESS_SPEC_ENABLED", True):
        return ""
    entries = read_entries(workspace_root)
    if not entries:
        return ""
    budget = max_chars if max_chars is not None else _int_env("HARNESS_SPEC_MAX_CHARS", 1200)
    lines = ["HARNESS SPEC — standing instructions from past failures in this repo:"]
    used = len(lines[0])
    # Most-repeated first: if the budget truncates, keep the costliest lessons.
    for entry in sorted(entries, key=lambda e: e.hits, reverse=True):
        line = f"- {entry.text}"
        if used + len(line) > budget:
            break
        lines.append(line)
        used += len(line)
    return "\n".join(lines) if len(lines) > 1 else ""
