"""OpenHands-compatible microagents: keyword-triggered repo knowledge.

OpenHands (github.com/OpenHands/OpenHands) lets a repository ship
"microagents" — markdown files with YAML frontmatter under
``.openhands/microagents/`` — that inject targeted guidance into the
agent's prompt. Two types exist:

- ``repo``      — always injected (repo-wide conventions the agent must know)
- ``knowledge`` — injected only when one of its ``triggers`` keywords
  appears in the task instruction

This module implements the same file format and matching rules so this
repo's microagents also work verbatim in OpenHands and any other tool
that reads the convention. The planner (``AgentRunner._generate_plan``)
calls :func:`microagents_block` and appends the result to its system
prompt, exactly like the lessons block from ``agent/lessons.py``.

Fail open by design: every public function returns a safe empty value on
any error, so microagents can never break a run.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("qwen-agent")

_MICROAGENTS_DIR = Path(".openhands") / "microagents"
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
# Short triggers ("pr", "ci") match on word boundaries to avoid firing on
# substrings like "sprint" or "circle"; longer ones use plain containment,
# matching OpenHands' case-insensitive behaviour.
_SHORT_TRIGGER_LEN = 4
_MAX_AGENT_CHARS = 1500
_MAX_BLOCK_CHARS = 4000


@dataclass
class Microagent:
    """One parsed microagent file."""

    name: str
    type: str  # "repo" | "knowledge"
    triggers: list[str] = field(default_factory=list)
    content: str = ""
    path: str = ""

    def matches(self, text: str) -> bool:
        """True when this microagent should be injected for *text*."""
        if self.type == "repo":
            return True
        lowered = text.lower()
        for trigger in self.triggers:
            trig = trigger.lower().strip()
            if not trig:
                continue
            if len(trig) < _SHORT_TRIGGER_LEN:
                if re.search(rf"\b{re.escape(trig)}\b", lowered):
                    return True
            elif trig in lowered:
                return True
        return False


def load_microagents(root: str | Path | None = None) -> list[Microagent]:
    """Parse every microagent under ``<root>/.openhands/microagents/``.

    Malformed files are skipped with a debug log; never raises.
    """
    agents: list[Microagent] = []
    try:
        directory = Path(root or ".") / _MICROAGENTS_DIR
        if not directory.is_dir():
            return []
        for md_file in sorted(directory.rglob("*.md")):
            agent = _parse_file(md_file)
            if agent is not None:
                agents.append(agent)
    except Exception as exc:
        log.debug("microagent loading skipped: %s", exc)
    return agents


def match_microagents(text: str, agents: list[Microagent]) -> list[Microagent]:
    """Microagents that apply to *text*: repo-type first, then triggered ones."""
    matched = [a for a in agents if a.matches(text or "")]
    return sorted(matched, key=lambda a: (a.type != "repo", a.name))


def microagents_block(instruction: str, root: str | Path | None = None) -> str:
    """Formatted prompt block of applicable microagents, or ''. Never raises."""
    try:
        matched = match_microagents(instruction, load_microagents(root))
    except Exception as exc:
        log.debug("microagent matching skipped: %s", exc)
        return ""
    if not matched:
        return ""
    parts = ["Repository microagent knowledge (applies to this task):"]
    used = len(parts[0])
    for agent in matched:
        content = agent.content.strip()[:_MAX_AGENT_CHARS]
        section = f"\n### {agent.name}\n{content}"
        if used + len(section) > _MAX_BLOCK_CHARS:
            break
        parts.append(section)
        used += len(section)
    return "\n".join(parts) if len(parts) > 1 else ""


def _parse_file(md_file: Path) -> Microagent | None:
    """Parse one microagent markdown file; None when it isn't one."""
    try:
        raw = md_file.read_text(encoding="utf-8")
        match = _FRONTMATTER_RE.match(raw)
        if not match:
            return None
        import yaml  # lazy: only needed when microagent files exist

        meta = yaml.safe_load(match.group(1)) or {}
        if not isinstance(meta, dict):
            return None
        agent_type = str(meta.get("type", "knowledge")).lower()
        triggers = [str(t) for t in (meta.get("triggers") or []) if str(t).strip()]
        if agent_type == "knowledge" and not triggers:
            return None  # untriggerable knowledge agent — never injectable
        return Microagent(
            name=str(meta.get("name") or md_file.stem),
            type=agent_type,
            triggers=triggers,
            content=raw[match.end():],
            path=str(md_file),
        )
    except Exception as exc:
        log.debug("microagent %s skipped: %s", md_file, exc)
        return None
