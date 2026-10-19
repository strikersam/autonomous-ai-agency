"""Regenerate harness/skills/README.md from each skill's SKILL.md frontmatter.

Usage:
    python harness/scripts/index_skills.py          # rewrite the index
    python harness/scripts/index_skills.py --check  # exit 1 if the index is stale
"""
from __future__ import annotations

import logging
import pathlib
import re
import sys

import yaml

log = logging.getLogger("qwen-proxy")
SKILLS = pathlib.Path(__file__).resolve().parent.parent / "skills"
INDEX = SKILLS / "README.md"
HEADER = """# Skills

One folder per skill, each with a `SKILL.md` (YAML frontmatter `name` + `description`,
then instructions). Claude Code, Codex and any agent that reads `SKILL.md` files can
load them. `CATALOG.md` maps use cases to skills.

This index is generated: `python harness/scripts/index_skills.py`.

| Skill | What it does |
|---|---|
"""


def describe(skill_md: pathlib.Path) -> str:
    """Return the frontmatter description of a SKILL.md, flattened to one line."""
    text = skill_md.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    match = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not match:
        return ""
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return ""
    value = " ".join(str(meta.get("description", "")).split())
    return value[:160] + ("…" if len(value) > 160 else "")


def render() -> str:
    """Build the full index text."""
    rows = []
    for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
        name = skill_md.parent.name
        desc = describe(skill_md).replace("|", "\\|") or "_(no description yet)_"
        rows.append(f"| [`{name}`]({name}/SKILL.md) | {desc} |")
    return HEADER + "\n".join(rows) + "\n"


def main() -> int:
    """Write the index, or with --check report whether it is current."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    content = render()
    if "--check" in sys.argv:
        current = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
        if current != content:
            log.error("harness/skills/README.md is stale; run python harness/scripts/index_skills.py")
            return 1
        log.info("SKILL INDEX OK")
        return 0
    INDEX.write_text(content, encoding="utf-8")
    log.info("Wrote %s", INDEX)
    return 0


if __name__ == "__main__":
    sys.exit(main())
