"""agent/harness_enrichment.py — Automatic Harness Enrichment for Agent Prompts

Every agent run auto-discovers available skills and tools, then injects a
compact enrichment block into the system prompt so even light/dumb models
can leverage the full capabilities of the repo.

Design goals:
  - Zero manual wiring — auto-discovers from live registries
  - Token-efficient — compact summaries for small context windows
  - Graceful degradation — never blocks the agent loop on failure
  - Skills-as-tools — runtime skills exposed as callable agent tools
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

log = logging.getLogger("harness.enrichment")

# ── Cache TTL (seconds) ────────────────────────────────────────────────────
# Skills/tools don't change mid-run; refresh on TTL expiry only.
_CACHE_TTL = int(os.environ.get("HARNESS_ENRICHMENT_CACHE_TTL", "300"))

# ── Token budget for enrichment blocks ──────────────────────────────────────
# Keep enrichment compact for small models (qwen3-coder:7b / 30b).
# ~500-800 chars for tools, ~300-500 for skills.
_MAX_TOOL_ENRICHMENT_CHARS = int(os.environ.get("HARNESS_ENRICHMENT_TOOL_CHARS", "800"))
_MAX_SKILL_ENRICHMENT_CHARS = int(os.environ.get("HARNESS_ENRICHMENT_SKILL_CHARS", "500"))


class HarnessEnrichment:
    """Auto-discovers skills and tools for agent prompt injection.

    Usage::

        enrichment = HarnessEnrichment()
        block = enrichment.build_tool_block()  # compact tool catalog
        block2 = enrichment.build_skill_block()  # compact skill catalog

        # Inject into any system prompt
        enriched = enrichment.inject(enriched_prompt, [block, block2])
    """

    def __init__(self, workspace_root: str | None = None) -> None:
        self._workspace_root = workspace_root or os.getcwd()
        self._cache_ts: float = 0.0
        self._cached_tool_block: str = ""
        self._cached_skill_block: str = ""

    # ── Public API ──────────────────────────────────────────────────────────

    def build_tool_block(self) -> str:
        """Build a compact, token-efficient catalog of available agent tools.

        Discovers from:
          1. ToolRegistry (capability_registry.py) — dynamic @agent_tool-registered tools
          2. Hardcoded fallback catalog — always-available tools
        """
        if self._cache_valid():
            return self._cached_tool_block

        lines: list[str] = []
        seen: set[str] = set()

        # 1. Discover from capability registry
        tr = self._get_tool_registry()
        if tr is not None:
            try:
                for tool in tr.list_all():
                    name = tool.name
                    if name in seen:
                        continue
                    seen.add(name)
                    desc = (tool.description or "")[:100]
                    lines.append(f"- {name}: {desc}")
            except Exception as exc:
                log.debug("Tool registry enumeration failed: %s", exc)

        # 2. Always-available tools (hardcoded dispatch in _dispatch_tool)
        _ALWAYS_TOOLS = [
            ("read_file", "Read a file's contents"),
            ("head_file", "Read first N lines of a file"),
            ("file_index", "Index directory structure"),
            ("list_files", "List files in a directory"),
            ("search_code", "Search codebase for patterns"),
            ("write_file", "Write content to a file"),
            ("recall_memory", "Recall saved user preferences"),
            ("save_memory", "Save user preferences"),
            ("spawn_subagent", "Delegate to a specialized sub-agent"),
            ("finish", "Signal step completion"),
            ("execute_skill", "Run a named skill by ID (see available skills below)"),
            ("recommend_skills", "Get recommended skills for the current task"),
            ("run_command", "Run a shell command in workspace"),
            # GitHub tools
            ("github_read_repo_file", "Read a file from a GitHub repo"),
            ("github_create_branch", "Create a branch on GitHub"),
            ("github_commit_changes", "Commit changes to GitHub"),
            ("github_open_pull_request", "Open a PR on GitHub"),
            ("github_list_repos", "List accessible GitHub repos"),
            ("github_list_branches", "List branches in a GitHub repo"),
        ]
        for name, desc in _ALWAYS_TOOLS:
            if name not in seen:
                lines.append(f"- {name}: {desc}")

        block = "AVAILABLE TOOLS:\n" + "\n".join(lines)
        if len(block) > _MAX_TOOL_ENRICHMENT_CHARS:
            block = block[:_MAX_TOOL_ENRICHMENT_CHARS] + "\n… [truncated]"
        self._cached_tool_block = block
        return block

    def build_skill_block(self) -> str:
        """Build a compact catalog of available runtime skills.

        Discovers from SkillBindings (30+ core skills) — returns the top
        enabled skills with one-line descriptions, sorted by category.
        """
        if self._cache_valid() and self._cached_skill_block:
            return self._cached_skill_block

        lines: list[str] = []
        sb = self._get_skill_bindings()
        if sb is not None:
            try:
                skills = sb.list_all()
                # Only include enabled skills, sorted by category
                enabled = [s for s in skills if getattr(s, "is_enabled", True)]
                # Always-show skills (council-review, graphify, ecc-harness-patterns)
                always = {"council-review", "graphify", "ecc-harness-patterns"}
                for s in enabled:
                    sid = s.skill_id
                    name = s.name
                    desc = (s.description or "")[:120]
                    cat = getattr(s, "category", None)
                    cat_str = f"[{cat.value}] " if cat else ""
                    marker = " ★" if sid in always else ""
                    lines.append(f"- {name}{marker}: {cat_str}{desc}")
            except Exception as exc:
                log.debug("Skill enumeration failed: %s", exc)

        if not lines:
            lines.append("- (no skills available — SkillBindings not loaded)")

        block = "AVAILABLE SKILLS:\n" + "\n".join(lines)
        if len(block) > _MAX_SKILL_ENRICHMENT_CHARS:
            block = block[:_MAX_SKILL_ENRICHMENT_CHARS] + "\n… [truncated]"
        self._cached_skill_block = block
        return block

    def build_full_enrichment(self) -> str:
        """Build the complete enrichment block (tools + skills).

        Returns empty string when no tools or skills are available, so
        callers can skip injection entirely for light models.
        """
        tool_block = self.build_tool_block()
        skill_block = self.build_skill_block()
        has_tools = tool_block and "AVAILABLE TOOLS:" in tool_block and len(tool_block) > 25
        has_skills = skill_block and "AVAILABLE SKILLS:" in skill_block and len(skill_block) > 25
        if not has_tools and not has_skills:
            return ""
        parts = []
        if has_tools:
            parts.append(tool_block)
        if has_skills:
            parts.append(skill_block)
        return (
            "─── HARNESS CAPABILITIES ───\n\n"
            + "\n\n".join(parts)
            + "\n\n"
            "HOW TO USE: Call tools by name with JSON args. "
            "Use 'recommend_skills' to find relevant skills for your task. "
            "Use 'execute_skill' to run a skill by its skill_id."
        )

    def inject(self, system_prompt: str, blocks: list[str] | None = None) -> str:
        """Inject enrichment blocks into a system prompt string.

        Appends blocks after the existing system prompt content. If no blocks
        are specified, injects the full enrichment.
        """
        if blocks is None:
            enrichment = self.build_full_enrichment()
        else:
            enrichment = "\n\n".join(blocks)
        return f"{system_prompt}\n\n{enrichment}"

    # ── Cache helpers ───────────────────────────────────────────────────────

    def _cache_valid(self) -> bool:
        return (time.time() - self._cache_ts) < _CACHE_TTL

    def invalidate_cache(self) -> None:
        self._cache_ts = 0.0

    # ── Lazy accessors ──────────────────────────────────────────────────────

    @staticmethod
    def _get_tool_registry() -> Any:
        try:
            from agent.capability_registry import get_tool_registry
            return get_tool_registry()
        except Exception as exc:
            log.debug("ToolRegistry not available: %s", exc)
            return None

    @staticmethod
    def _get_skill_bindings() -> Any:
        try:
            from services.skill_bindings import get_skill_bindings
            return get_skill_bindings()
        except Exception as exc:
            log.debug("SkillBindings not available: %s", exc)
            return None

    @staticmethod
    def _get_skill_registry() -> Any:
        try:
            from agent.skill_registry import get_skill_registry_safe
            return get_skill_registry_safe()
        except Exception:
            return None


# ── Module-level singleton ──────────────────────────────────────────────────

_enrichment: HarnessEnrichment | None = None


def get_enrichment(workspace_root: str | None = None) -> HarnessEnrichment:
    global _enrichment
    if _enrichment is None:
        _enrichment = HarnessEnrichment(workspace_root)
    return _enrichment


def invalidate_enrichment_cache() -> None:
    global _enrichment
    if _enrichment is not None:
        _enrichment.invalidate_cache()
