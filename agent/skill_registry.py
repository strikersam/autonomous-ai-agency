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

log = logging.getLogger("qwen-proxy")

# ---------------------------------------------------------------------------
# Known GitHub skill registries
# Each registry can have a "structure" field:
#   - "subdirs" = skills are in subdirectories (look for skill_file in each dir)
#   - "flat" = skills are top-level .md files (treat each .md as a skill)
# ---------------------------------------------------------------------------
GITHUB_REGISTRIES: list[dict[str, str]] = [
    {
        "id": "agency-agents",
        "owner": "msitarzewski",
        "repo": "agency-agents",
        "path": "",
        "skill_file": "",           # each .md file IS the skill
        "structure": "flat",        # top-level .md files are agent skills
    },
    {
        "id": "agent-skills-addy",
        "owner": "addyosmani",
        "repo": "agent-skills",
        "path": "skills",            # skills are in skills/ subdirectory
        "skill_file": "SKILL.md",
        "structure": "subdirs",
    },
    {
        "id": "anthropic-skills",
        "owner": "anthropics",
        "repo": "skills",
        "path": "skills",            # skills are in skills/ subdirectory
        "skill_file": "SKILL.md",
        "structure": "subdirs",
    },
    {
        "id": "local-llm-claude-skills",
        "owner": "strikersam",
        "repo": "local-llm-server",
        "path": ".claude/skills",
        "skill_file": "SKILL.md",
        "structure": "subdirs",
    },
    {
        # 338 business/PM/engineering skills in nested category dirs
        # (e.g. project-management/discovery/pre-mortem/SKILL.md).
        # Indexed via the git-trees API (single request) and fetched from
        # raw.githubusercontent.com to stay clear of API rate limits.
        "id": "borghei-claude-skills",
        "owner": "borghei",
        "repo": "Claude-Skills",
        "path": "",
        "skill_file": "SKILL.md",
        "structure": "nested",
        "branch": "main",
    },
    # ── Curated from BehiSecc/awesome-claude-skills (issue #491) ───────────
    # The awesome list itself is links, not skills; these are the two largest
    # actual skill repos it references that we don't already index
    # (anthropics/skills is already registered above via "anthropic-skills").
    {
        "id": "superpowers",
        "owner": "obra",
        "repo": "superpowers",
        "path": "",
        "skill_file": "SKILL.md",
        "structure": "nested",
        "branch": "main",
    },
    {
        "id": "ai-skills-sanjay",
        "owner": "sanjay3290",
        "repo": "ai-skills",
        "path": "",
        "skill_file": "SKILL.md",
        "structure": "nested",
        "branch": "main",
    },
]

# Max skill files fetched per refresh for "nested" registries.
NESTED_REGISTRY_FETCH_CAP = 400

# Tech → Skill mapping
# Tells the recommender which skills are most relevant for a given tech.
# Extended with real technologies detected by the website/repo scanner.
# ---------------------------------------------------------------------------
TECH_SKILL_MAP: dict[str, list[str]] = {
    # E-commerce
    "shopify":              ["abandoned-cart", "dynamic-pricing", "stock-alert", "review-response", "campaign-perf", "seo-content"],
    "woocommerce":          ["abandoned-cart", "stock-alert", "seo-content"],
    "salesforce commerce cloud": ["abandoned-cart", "dynamic-pricing", "campaign-perf"],
    "magento":              ["abandoned-cart", "dynamic-pricing", "seo-content"],
    "bigcommerce":          ["abandoned-cart", "campaign-perf"],
    # CMS
    "wordpress":            ["seo-content", "docs-sync", "dependency-audit"],
    "contentful":           ["seo-content", "docs-sync"],
    "drupal":               ["seo-content", "docs-sync", "dependency-audit"],
    "webflow":              ["seo-content", "stop-slop-quality"],
    # Frameworks
    "next.js":              ["seo-content", "stop-slop-quality", "performance", "modularity-review"],
    "react":                ["stop-slop-quality", "modularity-review", "implementation-planner"],
    "vue":                  ["stop-slop-quality", "modularity-review"],
    "angular":              ["stop-slop-quality", "modularity-review", "test-first-executor"],
    "svelte":               ["stop-slop-quality", "modularity-review"],
    "django":               ["test-first-executor", "risky-module-review", "docs-sync"],
    "flask":                ["test-first-executor", "risky-module-review"],
    "fastapi":              ["test-first-executor", "risky-module-review", "docs-sync"],
    "rails":                ["test-first-executor", "risky-module-review", "dependency-audit"],
    "laravel":              ["test-first-executor", "risky-module-review", "dependency-audit"],
    "express":              ["test-first-executor", "risky-module-review"],
    # Analytics
    "google analytics":     ["campaign-perf", "ai-engineering-insights"],
    "google tag manager":   ["campaign-perf"],
    "klaviyo":              ["abandoned-cart", "review-response", "campaign-perf"],
    "hotjar":               ["campaign-perf", "ai-engineering-insights"],
    "segment":              ["ai-engineering-insights"],
    "mixpanel":             ["ai-engineering-insights"],
    "amplitude":            ["ai-engineering-insights"],
    # Infrastructure / CDN
    "aws":                  ["dependency-audit", "risky-module-review", "release-readiness"],
    "cloudflare":           ["dependency-audit", "risky-module-review"],
    "vercel":               ["release-readiness", "branch-cleanup", "stop-slop-quality"],
    "netlify":              ["release-readiness", "branch-cleanup"],
    "heroku":               ["dependency-audit", "release-readiness"],
    "docker":               ["dependency-audit", "release-readiness"],
    "kubernetes":           ["dependency-audit", "risky-module-review", "release-readiness"],
    # Languages
    "python":               ["test-first-executor", "dependency-audit", "risky-module-review"],
    "typescript":           ["test-first-executor", "stop-slop-quality", "modularity-review"],
    "javascript":           ["test-first-executor", "stop-slop-quality", "modularity-review"],
    "go":                   ["test-first-executor", "performance", "dependency-audit"],
    "rust":                 ["test-first-executor", "performance", "risky-module-review"],
    "php":                  ["test-first-executor", "risky-module-review", "dependency-audit"],
    "ruby":                 ["test-first-executor", "dependency-audit"],
    "java":                 ["test-first-executor", "dependency-audit"],
    # Databases
    "postgresql":           ["dependency-audit", "risky-module-review"],
    "mongodb":              ["dependency-audit", "risky-module-review"],
    "mysql":                ["dependency-audit", "risky-module-review"],
    "redis":                ["dependency-audit", "performance"],
    "elasticsearch":        ["performance", "ai-engineering-insights"],
    # Payment
    "stripe":               ["risky-module-review", "dependency-audit"],
    "paypal":               ["risky-module-review"],
    "square":               ["risky-module-review"],
    # CDN / Hosting
    "akamai":               ["risky-module-review"],
    "fastly":               ["risky-module-review"],
    "cloudfront":           ["risky-module-review"],
    # Security
    "hcaptcha":             ["risky-module-review"],
    "recaptcha":            ["risky-module-review"],
    # Marketing
    "hubspot":              ["campaign-perf", "docs-sync"],
    "mailchimp":            ["campaign-perf"],
    "salesforce":           ["campaign-perf", "docs-sync"],
    # AI/ML
    "openai":               ["hybrid-reasoning", "managed-agents-dreams"],
    "tensorflow":           ["hybrid-reasoning", "memory-consolidation"],
    "pytorch":              ["hybrid-reasoning", "memory-consolidation"],
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

# ---------------------------------------------------------------------------
# Pre-compiled tech-match patterns — built once at module load, reused on
# every call to _extract_tech_relevance_dynamic() so we don't re-compile
# ~70 regex patterns per skill per recommendation call.
# ---------------------------------------------------------------------------
_EXTRA_TECHS: set[str] = {
    "react", "vue", "angular", "svelte", "next.js", "nuxt", "remix",
    "django", "flask", "fastapi", "rails", "laravel", "express",
    "spring", "gin", "fiber", "echo",
    "prisma", "drizzle", "typeorm", "sqlalchemy",
    "tailwind", "bootstrap", "material ui", "chakra", "shadcn",
    "graphql", "rest", "grpc", "websocket",
    "docker", "kubernetes", "terraform", "ansible", "pulumi",
    "github actions", "gitlab ci", "circleci", "jenkins",
    "playwright", "cypress", "jest", "vitest", "pytest", "rspec",
    "kafka", "rabbitmq", "redis", "nats",
    "sentry", "datadog", "newrelic", "grafana", "prometheus",
    "supabase", "firebase", "planetscale", "neon", "turso",
    "vercel", "netlify", "render", "fly.io", "railway",
    "openai", "anthropic", "gemini", "langchain", "llamaindex",
    "s3", "rds", "lambda", "ecs", "ec2", "cloudfront",
    "css", "html", "sass", "less",
    "swift", "kotlin", "dart", "flutter",
    "figma", "storybook", "chromatic", "zeplin",
}

_ALL_TECHS: set[str] = set(TECH_SKILL_MAP.keys()) | _EXTRA_TECHS

# Multi-word techs (space- or dot-separated) — substring match is acceptable
_MULTI_WORD_TECHS: tuple[str, ...] = tuple(
    t for t in _ALL_TECHS if " " in t or "." in t
)

# Single-word techs — pre-compile word-boundary regex, sorted longest-first
_SORTED_SINGLE: list[str] = sorted(
    (t for t in _ALL_TECHS if " " not in t and "." not in t),
    key=len, reverse=True,
)

class _TechPattern:
    """Holds a pre-compiled regex + the original tech name."""
    __slots__ = ("pattern", "_tech_name")
    pattern: re.Pattern
    _tech_name: str

    def __init__(self, tech: str) -> None:
        self._tech_name = tech
        if len(tech) <= 1:
            # Standalone single-char match (e.g. "r" but not "render")
            self.pattern = re.compile(
                r"(?:^|[\b \t\n\r,;:.!?()\"'`])"
                + re.escape(tech)
                + r"(?:$|[\b \t\n\r,;:.!?()\"'`])",
                flags=re.IGNORECASE,
            )
        else:
            self.pattern = re.compile(r"\b" + re.escape(tech) + r"\b", flags=re.IGNORECASE)

_SINGLE_WORD_TECHS_BY_LEN: tuple[_TechPattern, ...] = tuple(
    _TechPattern(t) for t in _SORTED_SINGLE
)


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
    _MAX_CONCURRENT = 5   # rate-limit GitHub API calls

    def __init__(self, local_skills_dir: str | Path | None = None,
                 github_token: str | None = None) -> None:
        self._skills: dict[str, RegistrySkill] = {}
        self._last_remote_fetch: float = 0.0
        # Resolve relative to the repo root, not the process CWD — in
        # production the server may start from a different working directory,
        # which made the local skill index come up empty (0 skills loaded).
        _default_dir = Path(__file__).resolve().parent.parent / ".claude" / "skills"
        self._local_dir = Path(local_skills_dir) if local_skills_dir else _default_dir
        self._github_token = github_token
        self._semaphore = asyncio.Semaphore(self._MAX_CONCURRENT)
        self._etags: dict[str, str] = {}  # URL → ETag for conditional requests
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

        # 1. Tech stack matches (hardcoded map)
        for tech in (tech_stack or []):
            t_lower = tech.lower()
            for map_tech, skill_ids in TECH_SKILL_MAP.items():
                if map_tech in t_lower or t_lower in map_tech:
                    for sid in skill_ids:
                        _add(sid, 3, f"detected tech: {tech}")

        # 1b. Dynamic tech_relevance scoring — skills that mention detected techs
        for tech in (tech_stack or []):
            t_lower = tech.lower()
            for skill_id, skill in self._skills.items():
                if t_lower in skill.tech_relevance:
                    _add(skill_id, 4, f"skill mentions: {tech}")

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

        # 4. Add all skills with base score if nothing matched yet
        if not scored:
            for skill in self._skills.values():
                scored[skill.skill_id] = (skill, 1, ["catalog skill"])

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

    async def refresh_remote_force(self) -> int:
        """Force-refresh remote skills, bypassing TTL. Returns count added."""
        self._last_remote_fetch = 0.0
        return await self.refresh_remote()

    def update_github_token(self, token: str | None) -> None:
        """Update the GitHub token used for authenticated API calls."""
        self._github_token = token or ""
        log.info("SkillRegistry GitHub token %s", "updated" if token else "cleared")

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
                tech_rel = _extract_tech_relevance(content)
                wf_rel   = _extract_workflow_relevance(content)
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
        """Fetch one GitHub registry and return a list of RegistrySkill objects.

        Handles two structure types:
          - "subdirs": skills are in subdirectories, look for skill_file in each
          - "flat":    .md files at the target path ARE the skills

        Uses semaphore-based rate limiting and ETag caching to avoid
        hitting GitHub's 60 req/h unauthenticated limit.
        """
        owner, repo = reg["owner"], reg["repo"]
        path = reg.get("path", "")
        skill_file = reg.get("skill_file", "")  # empty for flat structure
        structure = reg.get("structure", "subdirs")

        if structure == "nested":
            return await self._fetch_nested_registry(client, reg)

        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        try:
            async with self._semaphore:
                headers = dict(client.headers)
                if api_url in self._etags:
                    headers["If-None-Match"] = self._etags[api_url]
                r = await client.get(api_url, headers=headers)
            if r.status_code == 304:
                return []  # not modified
            if r.status_code != 200:
                if r.status_code == 403 and "rate limit" in (r.text or "").lower():
                    log.warning("GitHub rate limit hit for %s/%s", owner, repo)
                return []
            if "ETag" in r.headers:
                self._etags[api_url] = r.headers["ETag"]
            entries = r.json()
            if not isinstance(entries, list):
                return []
        except Exception:
            return []

        skills: list[RegistrySkill] = []

        if structure == "flat":
            # Each .md file at this level is a skill
            md_files = [e for e in entries if e.get("type") == "file"
                        and e.get("name", "").endswith(".md")
                        and not e.get("name", "").startswith("README")][:50]
            tasks = [self._fetch_flat_skill_file(client, reg, entry)
                     for entry in md_files]
        else:
            # Skills in subdirectories
            dirs = [e for e in entries if e.get("type") == "dir"][:40]
            tasks = [self._fetch_skill_file(client, reg, entry, skill_file)
                     for entry in dirs]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, RegistrySkill):
                skills.append(res)
        return skills

    async def _fetch_nested_registry(
        self, client: httpx.AsyncClient, reg: dict[str, str]
    ) -> list[RegistrySkill]:
        """Fetch a registry whose skills live in arbitrarily nested directories.

        Uses the git-trees API with ``recursive=1`` (a single request) to find
        every ``<skill_file>`` path, then fetches file contents from
        raw.githubusercontent.com, which is not subject to the 60 req/h
        unauthenticated API limit. Fetch count is capped by
        ``NESTED_REGISTRY_FETCH_CAP``.
        """
        owner, repo = reg["owner"], reg["repo"]
        branch = reg.get("branch", "main")
        skill_file = reg.get("skill_file", "SKILL.md")
        prefix = reg.get("path", "")

        tree_url = (
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        )
        try:
            async with self._semaphore:
                headers = dict(client.headers)
                if tree_url in self._etags:
                    headers["If-None-Match"] = self._etags[tree_url]
                r = await client.get(tree_url, headers=headers)
            if r.status_code == 304:
                return []
            if r.status_code != 200:
                if r.status_code == 403 and "rate limit" in (r.text or "").lower():
                    log.warning("GitHub rate limit hit for %s/%s", owner, repo)
                return []
            if "ETag" in r.headers:
                self._etags[tree_url] = r.headers["ETag"]
            tree = r.json().get("tree", [])
        except Exception:
            return []

        all_paths = [
            e["path"] for e in tree
            if isinstance(e, dict)
            and e.get("type") == "blob"
            and e.get("path", "").endswith("/" + skill_file)
            and e.get("path", "").startswith(prefix)
        ]
        # Round-robin across top-level categories so the cap yields breadth
        # (alphabetical truncation would drop entire categories).
        by_cat: dict[str, list[str]] = {}
        for p in all_paths:
            by_cat.setdefault(p.split("/")[0], []).append(p)
        paths: list[str] = []
        while len(paths) < min(NESTED_REGISTRY_FETCH_CAP, len(all_paths)):
            for cat in sorted(by_cat):
                if by_cat[cat]:
                    paths.append(by_cat[cat].pop(0))
                    if len(paths) >= NESTED_REGISTRY_FETCH_CAP:
                        break

        tasks = [
            self._fetch_nested_skill_file(client, reg, p, branch) for p in paths
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [res for res in results if isinstance(res, RegistrySkill)]

    async def _fetch_nested_skill_file(
        self, client: httpx.AsyncClient, reg: dict[str, str],
        path: str, branch: str,
    ) -> RegistrySkill | None:
        """Fetch one nested SKILL.md via raw.githubusercontent.com."""
        owner, repo = reg["owner"], reg["repo"]
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        try:
            async with self._semaphore:
                r = await client.get(raw_url)
            if r.status_code != 200:
                return None
            raw = r.text
        except Exception:
            return None

        # Strip YAML frontmatter so description comes from real prose.
        body = raw
        if body.startswith("---"):
            end = body.find("\n---", 3)
            if end != -1:
                body = body[end + 4:].lstrip()

        # path = "<categories...>/<skill-name>/SKILL.md"
        parts = path.split("/")
        name = parts[-2] if len(parts) >= 2 else parts[0]
        categories = parts[:-2]  # everything above the skill dir
        skill_id = f"github:{reg['id']}:{name}"

        return RegistrySkill(
            skill_id=skill_id,
            name=_fmt_name(name),
            description=_first_paragraph(body),
            source=f"github:{reg['id']}",
            registry_id=reg["id"],
            url=f"https://github.com/{owner}/{repo}/blob/{branch}/{path}",
            tags=sorted(set(_extract_tags(raw)) | set(categories)),
            tech_relevance=_extract_tech_relevance(raw),
            workflow_relevance=_extract_workflow_relevance(raw),
            raw_content=raw[:4000],
            fetched_at=time.time(),
        )

    async def _fetch_flat_skill_file(
        self, client: httpx.AsyncClient, reg: dict[str, str],
        entry: dict
    ) -> RegistrySkill | None:
        """Fetch a flat .md file and convert it to a RegistrySkill."""
        owner, repo = reg["owner"], reg["repo"]
        file_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{entry['path']}"
        try:
            async with self._semaphore:
                headers = dict(client.headers)
                if file_url in self._etags:
                    headers["If-None-Match"] = self._etags[file_url]
                r = await client.get(file_url, headers=headers)
            if r.status_code in (304, 404):
                return None
            if r.status_code != 200:
                return None
            if "ETag" in r.headers:
                self._etags[file_url] = r.headers["ETag"]
            import base64
            data = r.json()
            raw = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
        except Exception:
            return None

        # Derive name from filename (strip .md extension)
        name = entry["name"]
        if name.endswith(".md"):
            name = name[:-3]
        skill_id = f"github:{reg['id']}:{name}"

        # Try to extract title from first heading
        title = _fmt_name(name)
        for line in raw.splitlines():
            s = line.strip()
            if s.startswith("# ") and len(s) > 3:
                title = s[2:].strip()[:80]
                break

        return RegistrySkill(
            skill_id=skill_id,
            name=title,
            description=_first_paragraph(raw),
            source=f"github:{reg['id']}",
            registry_id=reg["id"],
            url=entry.get("html_url"),
            tags=_extract_tags(raw),
            tech_relevance=_extract_tech_relevance(raw),
            workflow_relevance=_extract_workflow_relevance(raw),
            raw_content=raw[:4000],
            fetched_at=time.time(),
        )

    async def _fetch_skill_file(
        self, client: httpx.AsyncClient, reg: dict[str, str],
        entry: dict, skill_file: str
    ) -> RegistrySkill | None:
        owner, repo = reg["owner"], reg["repo"]
        path = entry["path"]
        file_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}/{skill_file}"
        try:
            async with self._semaphore:
                headers = dict(client.headers)
                if file_url in self._etags:
                    headers["If-None-Match"] = self._etags[file_url]
                r = await client.get(file_url, headers=headers)
            if r.status_code in (304, 404):
                return None
            if r.status_code != 200:
                return None
            if "ETag" in r.headers:
                self._etags[file_url] = r.headers["ETag"]
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
            tech_relevance=_extract_tech_relevance(raw),
            workflow_relevance=_extract_workflow_relevance(raw),
            raw_content=raw[:4000],
            fetched_at=time.time(),
        )


# ---------------------------------------------------------------------------
# Module-level extraction helpers (no longer static methods so they can
# use the pre-compiled module-level pattern constants)
# ---------------------------------------------------------------------------

def _extract_tech_relevance(content: str) -> list[str]:
    """Dynamic extraction: finds any tech keyword mentioned in the skill content,
    including those not in TECH_SKILL_MAP. Uses word-boundary-aware matching
    to avoid false positives (e.g. 'react' should match 'react component'
    but not 'reactive')."""
    content_lower = content.lower()
    found: list[str] = []

    # Multi-word techs — use explicit [a-z0-9] boundary to avoid matching
    # "next.js" inside "next.jsx" or similar compound identifiers.
    for tech in _MULTI_WORD_TECHS:
        pattern = re.compile(
            r"(?<![a-z0-9])" + re.escape(tech) + r"(?![a-z0-9])",
            flags=re.IGNORECASE,
        )
        if pattern.search(content_lower):
            found.append(tech)

    # Word-boundary check for single-word techs — pre-compiled at module load
    for tp in _SINGLE_WORD_TECHS_BY_LEN:
        if tp.pattern.search(content_lower):
            found.append(tp._tech_name)

    # Deduplicate and cap at 12
    return list(dict.fromkeys(found))[:12]


def _extract_workflow_relevance(content: str) -> list[str]:
    """Return workflow types mentioned in the skill content."""
    content_lower = content.lower()
    found: list[str] = []
    for wf in WORKFLOW_SKILL_MAP:
        if wf in content_lower or wf.replace("_", " ") in content_lower:
            found.append(wf)
    return found[:5]


# ---------------------------------------------------------------------------
# Singleton helper — get the global SkillRegistry safely
# ---------------------------------------------------------------------------

_global_skill_registry: "SkillRegistry | None" = None


def set_skill_registry(instance: "SkillRegistry") -> None:
    global _global_skill_registry
    _global_skill_registry = instance


def get_skill_registry_safe() -> "SkillRegistry | None":
    """Return the global SkillRegistry if set, else None.
    Used by onboarding and other modules to avoid circular imports."""
    return _global_skill_registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_name(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").title()


def _first_paragraph(text: str) -> str:
    """Return the first non-empty, non-heading line.

    Skips YAML frontmatter (--- ... ---) so the description isn't "---".
    """
    lines = text.splitlines()
    # Skip YAML frontmatter
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                lines = lines[i + 1:]
                break
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and not s.startswith("<!--") and len(s) > 10:
            return s[:250]
    return ""


def _extract_tags(content: str) -> list[str]:
    """Pull hashtags and bold words from markdown as tags."""
    import re as _re
    tags: list[str] = []
    # Hashtags: # must NOT be preceded by an alphanumeric (not a word boundary)
    tags += _re.findall(r"(?<![a-zA-Z0-9])#([a-zA-Z0-9_]{1,30})", content)
    # Bold: **word** or __word__ with content length 3-30
    tags += _re.findall(r"\*\*([^\n*]{3,30})\*\*", content)
    tags += _re.findall(r"__([^\n_]{3,30})__", content)
    return list(dict.fromkeys(t.lower() for t in tags))[:12]