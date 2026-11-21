"""packages/runs/skill_versions.py — resolve and pin the skill versions a run starts with.

A skill's version is the ``version:`` key of its ``SKILL.md`` frontmatter when
present, otherwise ``sha-`` plus the first 12 hex digits of the file content hash,
so every skill has a stable version without editing any file. The run records the
mapping once, when it opens; a resumed run keeps what it recorded even if a skill
file changed since (``pin``).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from pathlib import Path

log = logging.getLogger("qwen-proxy")

_ROOT = Path(__file__).resolve().parents[2]
# harness/ first: .claude/skills mostly symlinks into it, and the first path wins a name.
SKILL_DIRS: tuple[Path, ...] = (_ROOT / "harness" / "skills", _ROOT / ".claude" / "skills")
_VERSION_LINE = re.compile(r"^version\s*:\s*['\"]?([^'\"\s#][^'\"#]*?)['\"]?\s*(?:#.*)?$", re.I)
_MAX_VERSION_LEN = 64


def parse_version(content: str) -> str | None:
    """The ``version`` key of the leading ``---`` frontmatter block, if any."""
    lines = content.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        match = _VERSION_LINE.match(line.strip())
        if match:
            return match.group(1).strip()[:_MAX_VERSION_LEN] or None
    return None


def version_of(content: str) -> str:
    """Declared version, else a stable content hash prefix."""
    return parse_version(content) or "sha-" + hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def resolve_skill_versions(dirs: tuple[Path, ...] | None = None) -> dict[str, str]:
    """Skill name -> version for every ``SKILL.md`` under *dirs* (blocking; see the async form)."""
    found: dict[str, str] = {}
    for base in dirs if dirs is not None else SKILL_DIRS:
        if not base.is_dir():
            continue
        for path in sorted(base.glob("*/SKILL.md")):
            if path.parent.name in found:
                continue
            try:
                found[path.parent.name] = version_of(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                log.debug("skill versions: could not read %s", path)
    return found


async def resolve_skill_versions_async(dirs: tuple[Path, ...] | None = None) -> dict[str, str]:
    """``resolve_skill_versions`` off the event loop."""
    return await asyncio.to_thread(resolve_skill_versions, dirs)


def pin(recorded: dict[str, str] | None, resolved: dict[str, str]) -> dict[str, str]:
    """What a run records: its earlier pin when it has one, else the freshly resolved map."""
    return dict(recorded) if recorded else dict(resolved)
