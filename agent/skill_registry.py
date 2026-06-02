"""agent/skill_registry.py — Dynamic Skill Registry & Recommender

Fetches skill packs from well-known GitHub registries, indexes them alongside
local .claude/skills/, and recommends skills based on:
  1. The company's detected tech stack (from scanner results)
  2. Active workflow configurations
  3. A keyword/intent query from the chat context

Skill sources:
  - Local:  .claude/skills/**/SKILL.md
  - GitHub: msitarzewski/agency-agents, addyosmani/agent-skills,
            anthropics/skills, and a configurable list stored in DB
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("skill-registry")

# ---------------------------------------------------------------------------
# Known GitHub skill registries
# ---------------------------------------------------------------------------
GITHUB_REGISTRIES: list[dict[str, str]] = [
    {
        "id": "agency-agents",
        "owner": "msitarzewski",
        "repo": "agency-agents",
        "path": "",          # skills are top-level dirs
        "skill_file": "README.md",
    },
    {
        "id": "agent-skills-addy",
        "owner": "addyosmani",
        "repo": "agent-skills",
        "path": "",
        "skill_file": "README.md",
    },
    {
        "id": "anthropic-skills",
        "owner": "anthropics",
        "repo": "skills",
        "path": "",
        "skill_file": "README.md",
    },
    {
        "id": "local-llm-claude-skills",
        "owner": "strikersam",
        "repo": "local-llm-server",
        "path": ".claude/skills",
        "skill_file": "SKILL.md",
    },
]

# ---------------------------------------------------------------------------
# Tech → Skill mapping
# Tells the recommender which skills are most relevant for a given tech
# ---------------------------------------------------------------------------
TECH_SKILL_MAP: dict[str, list[str]] = {
    # E-commerce
    "shopify":           ["abandoned-cart", "dynamic-pricing", "stock-alert", "review-response", "campaign-perf", "seo-content"],
    "woocommerce":       ["abandoned-cart", "stock-alert", "seo-content"],
    "salesforce commerce cloud": ["abandoned-cart", "dynamic-pricing", "campaign-perf"],
    # CMS
    "wordpress":         ["seo-content", "docs-sync"],
    "contentful":        ["seo-content", "docs-sync"],
    "next.js":           ["seo-content", "stop-slop-quality", "performance"],
    # Analytics
    "google analytics":  ["campaign-perf", "ai-engineering-insights"],
    "klaviyo":           ["abandoned-cart", "review-response"],
    # Infrastructure
    "aws":               ["dependency-audit", "risky-module-review"],
    "cloudflare":        ["dependency-audit"],
    "vercel":            ["release-readiness", "branch-cleanup"],
    # Dev
    "react":             ["stop-slop-quality", "modularity-review"],
    "python":            ["test-first-executor", "dependency-audit", "risky-module-review"],
    "typescript":        ["test-first-executor", "stop-slop-quality", "modularity-review"],
    "postgresql":        ["dependency-audit"],
    "mongodb":           ["dependency-audit"],
    # Payment
    "stripe":            ["risky-module-review", "dependency-audit"],
}

# Workflow type → recommended skills
WORKFLOW_SKILL_MAP: dict[str, list[str]] = {
    "ci_cd":        ["test-first-executor", "release-readiness", "changelog-enforcer", "branch-cleanup"],
    "content":      ["seo-content", "docs-sync", "stop-slop-quality"],
    "ecommerce":    ["abandoned-cart", "dynamic-pricing", "stock-alert", "review-response"],
    "security":     ["risky-module-review", "dependency-audit"],
    "analytics":    ["campaign-perf", "ai-engineering-insights", "financial-analyst"],
    "research":     ["research-coordinator", "graphify", "memory-consolidation"],
    "multi_agent":  ["multi-agent", "managed-agents-dreams", "council-review"],
}


@dataclass
class RegistrySkill:
    """A skill fetched from a remote or local registry."""
    skill_id: str
    name: str
    description: str
    source: str                       # "local" | "github:<registry_id>"
    registry_id: str = ""
    url: str | None = None
    tags: list[str] = field(default_factory=list)
    tech_relevance: list[str] = field(default_factory=list)  # which techs this applies to
    workflow_relevance: list[str] = field(default_factory=list)
    raw_content: str = ""
    fetched_at: float = 0.0
    install_cmd: str | None = None    # e.g. "npx install-skill abandoned-cart"

    def as_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "registry_id": self.registry_id,
            "url": self.url,
            "tags": self.tags,
            "tech_relevance": self.tech_relevance,
            "workflow_relevance": self.workflow_relevance,
            "install_cmd": self.install_cmd,
        }


class SkillRegistry:
    """
    Central registry that indexes local + remote skills and provides
    context-aware recommendations.

    Thread-safe read, async write (refresh).
    """

    _TTL_SECONDS = 3600  # refresh remote skills every hour

    def __init__(self, local_skills_dir: str | Path | None = None,
                 github_token: str | None = None) -> None:
        self._skills: dict[str, RegistrySkill] = {}
        self._last_remote_fetch: float = 0.0
        self._local_dir = Path(local_skills_dir or ".claude/skills")
        self._github_token = github_token
        # Seed local skills synchronously at startup
        self._index_local()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list(self, source: str | None = None) -> list[RegistrySkill]:
        skills = list(self._skills.values())
        if source:
            skills = [s for s in skills if s.source.startswith(source)]
        return skills

    def search(self, query: str) -> list[RegistrySkill]:
        q = query.lower()
        out = []
        for s in self._skills.values():
            hay = (
                s.skill_id.lower() + " "
                + s.name.lower() + " "
                + s.description.lower() + " "
                + " ".join(s.tags).lower() + " "
                + s.raw_content.lower()[:2000]
            )
            if q in hay:
                out.append(s)
        return out

    def get(self, skill_id: str) -> RegistrySkill | None:
        return self._skills.get(skill_id)

    def recommend(
        self,
        *,
        tech_stack: list[str] | None = None,
        workflow_types: list[str] | None = None,
        query: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Return ranked skill recommendations based on tech stack, active
        workflow types, and an optional text query.

        Each result includes a `score` and `reason` field.
        """
        scored: dict[str, tuple[RegistrySkill, int, list[str]]] = {}

        def _add(skill_id: str, points: int, reason: str) -> None:
            if skill_id not in self._skills:
                return
            s = self._skills[skill_id]
            if skill_id in scored:
                existing = scored[skill_id]
                scored[skill_id] = (s, existing[1] + points, existing[2] + [reason])
            else:
                scored[skill_id] = (s, points, [reason])

        # 1. Tech stack matches
        for tech in (tech_stack or []):
            t_lower = tech.lower()
            for map_tech, skill_ids in TECH_SKILL_MAP.items():
                if map_tech in t_lower or t_lower in map_tech:
                    for sid in skill_ids:
                        _add(sid, 3, f"detected tech: {tech}")

        # 2. Workflow type matches
        for wf in (workflow_types or []):
            w_lower = wf.lower()
            for map_wf, skill_ids in WORKFLOW_SKILL_MAP.items():
                if map_wf in w_lower or w_lower in map_wf:
                    for sid in skill_ids:
                        _add(sid, 2, f"active workflow: {wf}")

        # 3. Text query
        if query:
            for skill in self.search(query):
                _add(skill.skill_id, 1, f"query match: {query}")

        # 4. Add all local skills with base score if nothing matched
        if not scored:
            for skill in self._skills.values():
                if skill.source == "local":
                    scored[skill.skill_id] = (skill, 1, ["local skill"])

        results = sorted(scored.values(), key=lambda x: x[1], reverse=True)[:limit]
        return [
            {**r[0].as_dict(), "score": r[1], "reasons": list(dict.fromkeys(r[2]))}
            for r in results
        ]

    async def refresh_remote(self) -> int:
        """Fetch skills from all configured GitHub registries. Returns count added."""
        if time.time() - self._last_remote_fetch < self._TTL_SECONDS:
            return 0
        added = 0
        headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
        if self._github_token:
            headers["Authorization"] = f"Bearer {self._github_token}"

        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            tasks = [self._fetch_registry(client, reg) for reg in GITHUB_REGISTRIES]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    for skill in res:
                        if skill.skill_id not in self._skills:
                            added += 1
                        self._skills[skill.skill_id] = skill
                elif isinstance(res, Exception):
                    log.debug("Registry fetch error: %s", res)

        self._last_remote_fetch = time.time()
        log.info("Remote skill refresh complete — %d new skills, total=%d", added, len(self._skills))
        return added

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _index_local(self) -> None:
        if not self._local_dir.exists():
            return
        indexed = 0
        for skill_md in self._local_dir.rglob("SKILL.md"):
            try:
                content = skill_md.read_text(encoding="utf-8", errors="replace")
                name = skill_md.parent.name
                skill_id = f"local:{name}"
                tech_rel = self._extract_tech_relevance(content)
                wf_rel   = self._extract_workflow_relevance(content)
                self._skills[skill_id] = RegistrySkill(
                    skill_id=skill_id,
                    name=_fmt_name(name),
                    description=_first_paragraph(content),
                    source="local",
                    registry_id="local",
                    tags=_extract_tags(content),
                    tech_relevance=tech_rel,
                    workflow_relevance=wf_rel,
                    raw_content=content[:4000],
                    fetched_at=time.time(),
                )
                indexed += 1
            except Exception as exc:
                log.debug("Could not index %s: %s", skill_md, exc)
        log.info("Indexed %d local skills from %s", indexed, self._local_dir)

    async def _fetch_registry(
        self, client: httpx.AsyncClient, reg: dict[str, str]
    ) -> list[RegistrySkill]:
        """Fetch one GitHub registry and return a list of RegistrySkill objects."""
        owner, repo = reg["owner"], reg["repo"]
        path = reg.get("path", "")
        skill_file = reg.get("skill_file", "README.md")

        # Get directory listing
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        try:
            r = await client.get(api_url)
            if r.status_code != 200:
                return []
            entries = r.json()
            if not isinstance(entries, list):
                return []
        except Exception:
            return []

        skills: list[RegistrySkill] = []
        tasks = []
        dirs = [e for e in entries if e.get("type") == "dir"][:30]  # cap at 30

        for entry in dirs:
            tasks.append(self._fetch_skill_file(client, reg, entry, skill_file))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, RegistrySkill):
                skills.append(res)
        return skills

    async def _fetch_skill_file(
        self, client: httpx.AsyncClient, reg: dict[str, str],
        entry: dict, skill_file: str
    ) -> RegistrySkill | None:
        owner, repo = reg["owner"], reg["repo"]
        path = entry["path"]
        file_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}/{skill_file}"
        try:
            r = await client.get(file_url)
            if r.status_code != 200:
                return None
            import base64
            data = r.json()
            raw = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
        except Exception:
            return None

        name = entry["name"]
        skill_id = f"github:{reg['id']}:{name}"
        return RegistrySkill(
            skill_id=skill_id,
            name=_fmt_name(name),
            description=_first_paragraph(raw),
            source=f"github:{reg['id']}",
            registry_id=reg["id"],
            url=entry.get("html_url"),
            tags=_extract_tags(raw),
            tech_relevance=self._extract_tech_relevance(raw),
            workflow_relevance=self._extract_workflow_relevance(raw),
            raw_content=raw[:4000],
            fetched_at=time.time(),
        )

    @staticmethod
    def _extract_tech_relevance(content: str) -> list[str]:
        content_lower = content.lower()
        found = []
        for tech in TECH_SKILL_MAP:
            if tech in content_lower:
                found.append(tech)
        return found[:8]

    @staticmethod
    def _extract_workflow_relevance(content: str) -> list[str]:
        content_lower = content.lower()
        found = []
        for wf in WORKFLOW_SKILL_MAP:
            if wf in content_lower or wf.replace("_", " ") in content_lower:
                found.append(wf)
        return found[:5]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_name(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").title()


def _first_paragraph(text: str) -> str:
    """Return the first non-empty, non-heading line."""
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and not s.startswith("<!--") and len(s) > 10:
            return s[:250]
    return ""


def _extract_tags(content: str) -> list[str]:
    """Pull hashtags and bold words from markdown as tags."""
    tags: list[str] = []
    tags += re.findall(r"#(\w+)", content)
    tags += re.findall(r"\*\*([^*]{3,30})\*\*", content)
    return list(dict.fromkeys(t.lower() for t in tags))[:12]
