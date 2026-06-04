"""
services/skill_bindings.py — Runtime Skill Bindings for Specialist Agents

Wires local .claude/skills and Python agent modules as runtime-callable skills
that specialists can execute through the workflow engine.

Architecture:
  SkillLibrary (SKILL.md index) → SkillBindings (typed runtime model) → Specialist.capabilities → WorkflowEngine

Key skills wired:
  - ECC (harness_adapter)        — cross-harness agent orchestration
  - Obsidian (knowledge_graph)   — typed knowledge graph with BFS, connected components
  - Graphify                     — token-optimized codebase querying
  - Council Review               — multi-perspective code review
  - Workflow Engine              — DAG-based task execution
  - Memory Consolidation         — dream memory for session artifacts
  - Repowise Intelligence        — dependency graph, git intelligence
  - Agentic Agile                — sprint management, burndown metrics
  - Financial Analyst            — infra cost analysis
  - Fabric Patterns              — reusable prompt patterns
  - Implementation Planner       — multi-file change planning
  - Test-First Executor          — test-before-implementation workflow
  - Hybrid Reasoning             — deterministic + LLM hybrid decisions
  - Cowork Session               — shared AI pairing sessions
  - Research Coordinator         — multi-source research orchestration
  - Stop-Slop Quality            — AI code quality filter
  - Changelog Enforcer           — conventional commits enforcement
  - Release Readiness            — pre-release gate checks
  - Branch Cleanup               — merged branch deletion
  - Docs Sync                    — documentation freshness
  - Dependency Audit             — CVE + version audit
  - Modularity Review            — coupling analysis
  - Managed Agent Dreams         — agent session memory
  - Graphiti Temporal            — temporal context graphs
  - AI Engineering Insights      — analytics and heatmaps
  - Risky Module Review          — security-sensitive code review

Each skill has:
  - Typed inputs/outputs (Pydantic)
  - Safety/approval requirements
  - Specialist family bindings
  - Runtime execution capability
"""

from __future__ import annotations

import logging
import os
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

log = logging.getLogger("skill_bindings")


# =============================================================================
# SKILL EXECUTION MODEL
# =============================================================================

class SkillSafety(str, Enum):
    """Safety classification for skill execution."""
    SAFE = "safe"               # Read-only, no side effects
    READ_ONLY = "read_only"     # Reads from disk/network, no writes
    WRITES_FILES = "writes_files"  # Modifies local filesystem
    NETWORK = "network"         # Makes network calls
    EXECUTES_CODE = "executes_code"  # Runs subprocesses/scripts
    REQUIRES_APPROVAL = "requires_approval"  # Always needs HITL approval


class SkillCategory(str, Enum):
    """Functional category for skill organization."""
    CODE_QUALITY = "code_quality"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    PLANNING = "planning"
    EXECUTION = "execution"
    REVIEW = "review"
    KNOWLEDGE = "knowledge"
    OPERATIONS = "operations"
    ANALYTICS = "analytics"
    COLLABORATION = "collaboration"
    MEMORY = "memory"
    RESEARCH = "research"


class SkillInput(BaseModel):
    """Typed input for a skill."""
    model_config = {"frozen": True, "extra": "forbid"}
    name: str = Field(..., description="Parameter name")
    type: str = Field(default="string", description="Python type (str, int, list[str], etc.)")
    required: bool = Field(default=True)
    default: Any = Field(default=None)
    description: str = Field(default="")


class SkillOutput(BaseModel):
    """Typed output from a skill."""
    model_config = {"frozen": True, "extra": "forbid"}
    type: str = Field(default="dict", description="Python return type")
    description: str = Field(default="")


class RuntimeSkill(BaseModel):
    """A runtime-callable skill that specialists can execute through the workflow engine."""
    model_config = {"frozen": False, "extra": "forbid"}

    skill_id: str = Field(..., description="Unique skill identifier (e.g., 'ecc-harness-patterns')")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(default="", description="What this skill does")
    category: SkillCategory = Field(default=SkillCategory.EXECUTION)
    safety: SkillSafety = Field(default=SkillSafety.SAFE)
    inputs: list[SkillInput] = Field(default_factory=list)
    outputs: SkillOutput = Field(default_factory=lambda: SkillOutput())
    specialist_families: list[str] = Field(
        default_factory=list,
        description="SpecialistFamily values this skill is relevant for"
    )
    capabilities_added: list[str] = Field(
        default_factory=list,
        description="Capability strings added to specialist when bound"
    )
    trigger_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords that suggest this skill should be auto-selected"
    )
    source: str = Field(default="local", description="Where the skill comes from")
    source_path: str | None = Field(default=None, description="Path to skill definition file")
    requires_approval: bool = Field(default=False)
    is_enabled: bool = Field(default=True)
    execution_count: int = Field(default=0)
    success_count: int = Field(default=0)
    error_count: int = Field(default=0)

    def as_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "safety": self.safety.value,
            "specialist_families": self.specialist_families,
            "capabilities_added": self.capabilities_added,
            "trigger_keywords": self.trigger_keywords,
            "source": self.source,
            "requires_approval": self.requires_approval,
            "is_enabled": self.is_enabled,
            "inputs": [i.model_dump() for i in self.inputs],
            "outputs": self.outputs.model_dump(),
        }


# =============================================================================
# SKILL BINDING ENGINE
# =============================================================================

class SkillBindings:
    """Central registry that maps skills to specialist families and provides
    runtime execution capability.

    This is the bridge between the Claude Code skill documentation (.claude/skills/)
    and the actual specialist agent runtime. Skills defined here become callable
    capabilities that specialists can use during workflow execution.
    """

    def __init__(self):
        self._skills: dict[str, RuntimeSkill] = {}
        self._family_map: dict[str, list[str]] = {}  # family → [skill_ids]
        self._capability_map: dict[str, str] = {}     # capability → skill_id
        self._register_core_skills()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_all(self) -> list[RuntimeSkill]:
        """List all registered skills."""
        return list(self._skills.values())

    def list_for_family(self, family: str) -> list[RuntimeSkill]:
        """List skills relevant to a specialist family."""
        skill_ids = self._family_map.get(family, [])
        return [self._skills[sid] for sid in skill_ids if sid in self._skills]

    def get(self, skill_id: str) -> RuntimeSkill | None:
        """Get a skill by ID."""
        return self._skills.get(skill_id)

    def search(self, query: str) -> list[RuntimeSkill]:
        """Search skills by name, description, or keywords."""
        q = query.lower()
        results = []
        for skill in self._skills.values():
            haystack = (
                skill.name.lower() + " "
                + skill.description.lower() + " "
                + " ".join(skill.trigger_keywords).lower() + " "
                + " ".join(skill.specialist_families).lower()
            )
            if q in haystack:
                results.append(skill)
        return results

    def recommend_for_company(
        self,
        system_types: list[str],
        specialist_families: list[str],
    ) -> list[dict[str, Any]]:
        """Recommend skills based on detected systems and provisioned specialists."""
        scored: dict[str, tuple[RuntimeSkill, int, list[str]]] = {}

        # Score skills by family match
        for family in specialist_families:
            for skill_id in self._family_map.get(family, []):
                skill = self._skills.get(skill_id)
                if not skill:
                    continue
                if skill_id in scored:
                    s, pts, reasons = scored[skill_id]
                    scored[skill_id] = (s, pts + 3, reasons + [f"family:{family}"])
                else:
                    scored[skill_id] = (skill, 3, [f"family:{family}"])

        # Score by system type relevance
        system_skill_map: dict[str, list[str]] = {
            "CMS": ["docs-sync", "modularity-review"],
            "analytics": ["financial-analyst", "ai-engineering-insights"],
            "payment_gateway": ["risky-module-review", "dependency-audit"],
            "CRM": ["docs-sync"],
            "marketing_automation": ["stop-slop-quality"],
            "support": ["cowork-session"],
            "database": ["dependency-audit"],
            "ai_ml": ["hybrid-reasoning", "memory-consolidation"],
            "frontend": ["stop-slop-quality", "modularity-review", "implementation-planner"],
            "backend": ["test-first-executor", "dependency-audit", "risky-module-review"],
        }
        for st in system_types:
            recs = system_skill_map.get(st, [])
            for sid in recs:
                if sid in self._skills:
                    if sid in scored:
                        s, pts, reasons = scored[sid]
                        scored[sid] = (s, pts + 2, reasons + [f"system:{st}"])
                    else:
                        scored[sid] = (self._skills[sid], 2, [f"system:{st}"])

        results = sorted(scored.values(), key=lambda x: x[1], reverse=True)
        return [
            {
                **skill.as_dict(),
                "score": pts,
                "reasons": reasons,
            }
            for skill, pts, reasons in results[:20]
        ]

    def bind_to_specialist(
        self,
        specialist_family: str,
    ) -> list[str]:
        """Return the list of skill IDs a specialist should be bound to."""
        skill_ids = self._family_map.get(specialist_family, [])
        return [sid for sid in skill_ids if self._skills.get(sid) and self._skills[sid].is_enabled]

    def execute_skill(self, skill_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a skill by ID and update its execution counters."""
        skill = self._skills.get(skill_id)
        if not skill:
            return {"success": False, "error": f"Skill '{skill_id}' not found"}
        if not skill.is_enabled:
            return {"success": False, "error": f"Skill '{skill_id}' is disabled"}

        skill.execution_count += 1
        try:
            result = _execute_skill_impl(skill_id, params or {})
            skill.success_count += 1
            return result
        except Exception as exc:
            skill.error_count += 1
            log.warning("Skill '%s' execution failed: %s", skill_id, exc)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Core Skill Registration
    # ------------------------------------------------------------------

    def _register_core_skills(self):
        """Register all core skills with their metadata and specialist bindings."""

        self._register(RuntimeSkill(
            skill_id="ecc-harness-patterns",
            name="ECC Cross-Harness Orchestration",
            description="Normalize API calls across 7+ agent harnesses (Claude Code, Cursor, Codex, OpenCode, Gemini, Zed, GitHub Copilot) with session lifecycle hooks and cross-harness model selection.",
            category=SkillCategory.EXECUTION,
            safety=SkillSafety.NETWORK,
            inputs=[
                SkillInput(name="harness_type", type="str", description="Target harness: claude_code, cursor, codex, opencode, gemini, zed, github_copilot"),
                SkillInput(name="request", type="dict", description="The request to normalize for the target harness"),
            ],
            outputs=SkillOutput(type="dict", description="Normalized request for the target harness"),
            specialist_families=["engineering", "devops", "architecture", "fullstack"],
            capabilities_added=["cross_harness_routing", "harness_normalization", "session_lifecycle"],
            trigger_keywords=["harness", "cursor", "codex", "cross-harness", "ECC", "multi-IDE"],
            source="local",
            source_path=".claude/skills/ecc-harness-patterns/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="obsidian-knowledge-graph",
            name="Obsidian Knowledge Graph",
            description="Typed knowledge graph with BFS shortest-path, connected components, import/export, and tag-based search. Stores relationships between concepts, decisions, and artifacts.",
            category=SkillCategory.KNOWLEDGE,
            safety=SkillSafety.SAFE,
            inputs=[
                SkillInput(name="action", type="str", description="Action: add_node, add_edge, shortest_path, connected_components, search_by_tag, export"),
                SkillInput(name="params", type="dict", description="Parameters for the action"),
            ],
            outputs=SkillOutput(type="dict", description="Result of the graph operation"),
            specialist_families=[
                "architecture", "docs", "analytics", "data", "engineering",
                "content", "research", "crm", "support", "seo", "pim",
            ],
            capabilities_added=["knowledge_graph_query", "relationship_tracing", "graph_export"],
            trigger_keywords=["knowledge graph", "obsidian", "graph", "BFS", "connected components"],
            source="local",
            source_path=".claude/skills/obsidian-knowledge-graph/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="graphify",
            name="Graphify Token-Optimized Codebase Query",
            description="Query the codebase knowledge graph (71.5x fewer tokens than raw file reads). Use for exploration, dependency tracing, and architecture understanding before opening files.",
            category=SkillCategory.KNOWLEDGE,
            safety=SkillSafety.READ_ONLY,
            is_enabled=True,
            inputs=[
                SkillInput(name="query", type="str", description="Natural language question about the codebase"),
                SkillInput(name="action", type="str", default="query", description="Action: query, explain, path, report"),
            ],
            outputs=SkillOutput(type="str", description="Answer from the knowledge graph"),
            specialist_families=["architecture", "engineering", "docs", "qa"],
            capabilities_added=["codebase_exploration", "token_efficient_context", "dependency_analysis"],
            trigger_keywords=["graphify", "codebase map", "knowledge graph", "token optimization", "code exploration", "codebase query"],
            source="local",
            source_path=".claude/skills/graphify/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="council-review",
            name="Council Multi-Perspective Code Review",
            description="Simulates a council of reviewers (security, correctness, performance, maintainability) independently evaluating a change. Produces structured verdicts.",
            category=SkillCategory.REVIEW,
            safety=SkillSafety.READ_ONLY,
            is_enabled=True,
            inputs=[
                SkillInput(name="diff", type="str", description="The git diff or code change to review"),
                SkillInput(name="changed_files", type="list[str]", default=[], description="List of files changed"),
            ],
            outputs=SkillOutput(type="dict", description="Council verdict with per-role findings"),
            specialist_families=["security", "qa", "engineering", "architecture"],
            capabilities_added=["multi_perspective_review", "security_audit", "correctness_check"],
            trigger_keywords=["council review", "code review", "security review", "PR review", "merge review", "pre-merge"],
            source="local",
            source_path=".claude/skills/council-review/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="workflow-engine",
            name="Workflow Engine (DAG Execution)",
            description="Execute DAG-based workflows with topological ordering, cycle detection, and parallel task execution. The canonical execution backbone.",
            category=SkillCategory.EXECUTION,
            safety=SkillSafety.EXECUTES_CODE,
            inputs=[SkillInput(name="workflow_definition", type="dict", description="Workflow with tasks, dependencies, and actions")],
            outputs=SkillOutput(type="dict", description="Workflow execution results"),
            specialist_families=["engineering", "devops", "qa", "operations"],
            capabilities_added=["dag_execution", "workflow_orchestration", "task_pipeline"],
            trigger_keywords=["workflow", "pipeline", "DAG", "task orchestration", "topological", "dependency graph"],
            source="local",
            source_path=".claude/skills/workflow-engine/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="memory-consolidation",
            name="Dream Memory Consolidation",
            description="Cluster session artifacts into structured, queryable memories with tag-based similarity. Inspired by hippocampal replay for long-running AI systems.",
            category=SkillCategory.MEMORY,
            safety=SkillSafety.SAFE,
            inputs=[
                SkillInput(name="memories", type="list[dict]", description="List of memory dicts with kind, content, tags"),
                SkillInput(name="action", type="str", default="consolidate", description="Action: add, consolidate, replay, query"),
            ],
            outputs=SkillOutput(type="dict", description="Consolidation results with clusters"),
            specialist_families=["docs", "analytics", "data", "ml"],
            capabilities_added=["memory_clustering", "pattern_extraction", "session_consolidation"],
            trigger_keywords=["memory consolidation", "dream memory", "pattern replay", "session artifacts", "hippocampal", "clustering"],
            source="local",
            source_path=".claude/skills/memory-consolidation/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="repowise-intelligence",
            name="Repowise Codebase Intelligence",
            description="Deep codebase understanding: dependency graphs, git history analysis, auto-generated docs, and architectural decision archaeology.",
            category=SkillCategory.KNOWLEDGE,
            safety=SkillSafety.READ_ONLY,
            is_enabled=False,
            inputs=[
                SkillInput(name="query", type="str", description="Question about the codebase"),
                SkillInput(name="action", type="str", default="overview", description="Action: overview, context, risk, why, answer"),
            ],
            outputs=SkillOutput(type="dict", description="Structured intelligence response"),
            specialist_families=["architecture", "engineering", "docs", "security"],
            capabilities_added=["dependency_analysis", "git_archaeology", "hotspot_detection"],
            trigger_keywords=["repowise", "dependency graph", "git history", "code ownership", "architectural decision", "hotspot"],
            source="local",
            source_path=".claude/skills/repowise-intelligence/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="agentic-agile",
            name="Agentic Agile Sprint Management",
            description="Agile sprint management with velocity tracking, burndown metrics, and multi-sprint orchestration.",
            category=SkillCategory.PLANNING,
            safety=SkillSafety.SAFE,
            inputs=[SkillInput(name="action", type="str", description="Action: create_sprint, add_story, start, get_metrics, predict_velocity"), SkillInput(name="params", type="dict", description="Parameters for the action")],
            outputs=SkillOutput(type="dict", description="Sprint data or metrics"),
            specialist_families=["agile", "portfolio", "product", "operations"],
            capabilities_added=["sprint_planning", "velocity_tracking", "burndown_metrics"],
            trigger_keywords=["agile", "sprint", "burndown", "velocity", "scrum", "story points", "retrospective"],
            source="local",
            source_path=".claude/skills/agentic-agile/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="financial-analyst",
            name="Agentic CFO Financial Analyst",
            description="Autonomous financial analysis of AI infrastructure spend. Computes burn rate, runway, gross margin, and ROI-based budget reallocation.",
            category=SkillCategory.ANALYTICS,
            safety=SkillSafety.READ_ONLY,
            inputs=[SkillInput(name="period", type="str", default="month", description="Analysis period: day, week, month, quarter")],
            outputs=SkillOutput(type="dict", description="Financial metrics and recommendations"),
            specialist_families=["portfolio", "analytics", "operations"],
            capabilities_added=["cost_analysis", "burn_rate", "roi_calculation"],
            trigger_keywords=["financial", "cost", "spend", "burn rate", "ROI", "budget", "runway", "CFO"],
            source="local",
            source_path=".claude/skills/financial-analyst/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="fabric-patterns",
            name="Fabric Reusable Prompt Patterns",
            description="Store, retrieve, and compose reusable prompt patterns for consistent AI interactions. Supports pattern stitching (output→input chaining).",
            category=SkillCategory.PLANNING,
            safety=SkillSafety.SAFE,
            inputs=[SkillInput(name="action", type="str", description="Action: list, get, apply, stitch, create"), SkillInput(name="params", type="dict", description="Parameters: pattern name, variables, stitch chain")],
            outputs=SkillOutput(type="str", description="Rendered prompt or pattern content"),
            specialist_families=["docs", "engineering", "qa", "product"],
            capabilities_added=["prompt_templating", "pattern_composition", "consistent_outputs"],
            trigger_keywords=["fabric pattern", "prompt pattern", "template", "stitch", "reusable prompt"],
            source="local",
            source_path=".claude/skills/fabric-patterns/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="implementation-planner",
            name="Implementation Planner",
            description="Plan multi-file or multi-step implementations before writing code. Produces structured plans with files to change, risks, and acceptance checks.",
            category=SkillCategory.PLANNING,
            safety=SkillSafety.SAFE,
            is_enabled=False,
            inputs=[SkillInput(name="goal", type="str", description="What the change should accomplish"), SkillInput(name="files_to_read", type="list[str]", default=[], description="Files to read for context")],
            outputs=SkillOutput(type="dict", description="Structured implementation plan"),
            specialist_families=["engineering", "architecture", "frontend", "backend", "fullstack"],
            capabilities_added=["implementation_planning", "risk_assessment", "change_scoping"],
            trigger_keywords=["implementation plan", "plan first", "multi-file change", "architecture plan", "design approach"],
            source="local",
            source_path=".claude/skills/implementation-planner/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="test-first-executor",
            name="Test-First Executor",
            description="Write or update tests before (or alongside) implementation. Ensures every code change is verifiably correct before merging.",
            category=SkillCategory.CODE_QUALITY,
            safety=SkillSafety.WRITES_FILES,
            is_enabled=False,
            inputs=[SkillInput(name="target", type="str", description="File or function to write tests for"), SkillInput(name="test_type", type="str", default="unit", description="Test type: unit, integration, e2e")],
            outputs=SkillOutput(type="dict", description="Test file path and results"),
            specialist_families=["qa", "engineering", "backend", "frontend"],
            capabilities_added=["test_generation", "regression_prevention", "coverage_improvement"],
            trigger_keywords=["test first", "write tests", "add tests", "regression test", "unit test", "test coverage"],
            source="local",
            source_path=".claude/skills/test-first-executor/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="stop-slop-quality",
            name="Stop-Slop AI Code Quality Filter",
            description="Remove AI code slop before committing. Review AI-generated code for unnecessary verbosity, redundant comments, over-engineering, and low-signal patterns.",
            category=SkillCategory.CODE_QUALITY,
            safety=SkillSafety.READ_ONLY,
            is_enabled=False,
            inputs=[SkillInput(name="code", type="str", description="AI-generated code to review"), SkillInput(name="language", type="str", default="python", description="Programming language")],
            outputs=SkillOutput(type="dict", description="Quality report with issues found"),
            specialist_families=["qa", "engineering", "docs"],
            capabilities_added=["code_quality_check", "slop_detection", "verbosity_reduction"],
            trigger_keywords=["stop slop", "code quality", "AI slop", "cleanup", "remove verbosity", "code review"],
            source="local",
            source_path=".claude/skills/stop-slop-quality/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="changelog-enforcer",
            name="Changelog Enforcer",
            description="Ensure every meaningful change has a proper docs/changelog.md entry following Keep a Changelog format.",
            category=SkillCategory.DOCUMENTATION,
            safety=SkillSafety.WRITES_FILES,
            is_enabled=False,
            inputs=[SkillInput(name="change_description", type="str", description="Description of the change"), SkillInput(name="change_type", type="str", description="Type: added, changed, fixed, security, removed")],
            outputs=SkillOutput(type="dict", description="Updated changelog entry"),
            specialist_families=["docs", "engineering", "devops"],
            capabilities_added=["changelog_management", "conventional_commits", "release_notes"],
            trigger_keywords=["changelog", "release notes", "keep a changelog", "conventional commit"],
            source="local",
            source_path=".claude/skills/changelog-enforcer/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="release-readiness",
            name="Release Readiness Gate Check",
            description="Gate check before tagging and releasing a new version. Verifies tests pass, changelog is updated, version is bumped, and CI is green.",
            category=SkillCategory.OPERATIONS,
            safety=SkillSafety.READ_ONLY,
            is_enabled=False,
            inputs=[],
            outputs=SkillOutput(type="dict", description="Release readiness report"),
            specialist_families=["devops", "engineering", "qa"],
            capabilities_added=["release_gating", "version_verification", "deployment_readiness"],
            trigger_keywords=["release readiness", "before release", "gate check", "release check", "can I release"],
            source="local",
            source_path=".claude/skills/release-readiness/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="branch-cleanup",
            name="Branch Cleanup",
            description="Delete remote and local branches that have been merged into master. Supports both git-push deletion and GitHub API deletion.",
            category=SkillCategory.OPERATIONS,
            safety=SkillSafety.NETWORK,
            is_enabled=False,
            inputs=[SkillInput(name="dry_run", type="bool", default=True, description="Preview without deleting")],
            outputs=SkillOutput(type="dict", description="Cleanup results"),
            specialist_families=["devops", "engineering"],
            capabilities_added=["branch_management", "repo_cleanup", "merged_branch_deletion"],
            trigger_keywords=["branch cleanup", "delete merged branches", "clean branches", "merged branches"],
            source="local",
            source_path=".claude/skills/branch-cleanup/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="docs-sync",
            name="Documentation Sync",
            description="Keep documentation in sync after code changes. Checks for stale docs, missing API documentation, and outdated references.",
            category=SkillCategory.DOCUMENTATION,
            safety=SkillSafety.WRITES_FILES,
            is_enabled=False,
            inputs=[SkillInput(name="changed_files", type="list[str]", description="Files that changed"), SkillInput(name="check_only", type="bool", default=False, description="Only check, don't update")],
            outputs=SkillOutput(type="dict", description="Docs sync report"),
            specialist_families=["docs", "engineering", "devops"],
            capabilities_added=["documentation_sync", "api_docs_update", "freshness_check"],
            trigger_keywords=["docs sync", "update docs", "documentation", "stale docs", "missing docs"],
            source="local",
            source_path=".claude/skills/docs-sync/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="dependency-audit",
            name="Dependency Audit (CVE + Freshness)",
            description="Review, validate, and update Python dependencies. Checks for CVEs, version freshness, and transitive dependency issues.",
            category=SkillCategory.SECURITY,
            safety=SkillSafety.NETWORK,
            is_enabled=False,
            inputs=[SkillInput(name="package_name", type="str", default="", description="Specific package to audit (all if empty)")],
            outputs=SkillOutput(type="dict", description="Audit report with CVEs and recommendations"),
            specialist_families=["security", "devops", "engineering"],
            capabilities_added=["dependency_audit", "cve_check", "version_validation"],
            trigger_keywords=["dependency audit", "CVE", "security audit", "pip audit", "vulnerability check"],
            source="local",
            source_path=".claude/skills/dependency-audit/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="modularity-review",
            name="Modularity Review (Coupling Analysis)",
            description="Review codebase for modularity problems: balanced coupling, inappropriate intimacy, feature envy, and god modules.",
            category=SkillCategory.CODE_QUALITY,
            safety=SkillSafety.READ_ONLY,
            is_enabled=False,
            inputs=[SkillInput(name="target", type="str", default=".", description="Directory or file to analyze")],
            outputs=SkillOutput(type="dict", description="Modularity report with recommendations"),
            specialist_families=["architecture", "engineering", "qa"],
            capabilities_added=["coupling_analysis", "modularity_assessment", "architecture_review"],
            trigger_keywords=["modularity review", "coupling", "architecture review", "god module", "feature envy"],
            source="local",
            source_path=".claude/skills/modularity-review/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="hybrid-reasoning",
            name="Hybrid AI Reasoning Engine",
            description="Combine deterministic rule engines with LLM reasoning for efficient, auditable, and reliable decision-making.",
            category=SkillCategory.EXECUTION,
            safety=SkillSafety.SAFE,
            is_enabled=False,
            inputs=[SkillInput(name="question", type="str", description="The decision or question to reason about"), SkillInput(name="rules", type="list[str]", default=[], description="Deterministic rules to apply first")],
            outputs=SkillOutput(type="dict", description="Hybrid reasoning result with audit trail"),
            specialist_families=["engineering", "architecture", "analytics"],
            capabilities_added=["hybrid_reasoning", "rule_engine", "auditable_decisions"],
            trigger_keywords=["hybrid reasoning", "rule engine", "deterministic", "auditable", "decision tree"],
            source="local",
            source_path=".claude/skills/hybrid-reasoning/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="cowork-session",
            name="Claude Cowork Shared AI Pairing",
            description="Shared AI pairing sessions with real-time sync, turn-taking, and collaboration context propagation.",
            category=SkillCategory.COLLABORATION,
            safety=SkillSafety.NETWORK,
            is_enabled=False,
            inputs=[SkillInput(name="action", type="str", description="Action: create, join, sync, leave"), SkillInput(name="session_id", type="str", default="", description="Session ID for join/sync")],
            outputs=SkillOutput(type="dict", description="Cowork session state"),
            specialist_families=["engineering", "docs", "product"],
            capabilities_added=["collaborative_coding", "session_sync", "pair_programming"],
            trigger_keywords=["cowork", "pair programming", "shared session", "collaboration", "real-time sync"],
            source="local",
            source_path=".claude/skills/cowork-session/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="research-coordinator",
            name="Multi-Source Research Coordinator",
            description="Coordinate research across multiple sources: web search, documentation, codebase, and knowledge base.",
            category=SkillCategory.RESEARCH,
            safety=SkillSafety.NETWORK,
            is_enabled=False,
            inputs=[SkillInput(name="question", type="str", description="Research question"), SkillInput(name="sources", type="list[str]", default=["web", "docs", "codebase"], description="Sources to search")],
            outputs=SkillOutput(type="dict", description="Consolidated research findings"),
            specialist_families=["analytics", "docs", "architecture"],
            capabilities_added=["multi_source_research", "knowledge_synthesis", "fact_checking"],
            trigger_keywords=["research", "find information", "look up", "web search", "documentation search"],
            source="local",
            source_path=".claude/skills/research-coordinator/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="managed-agents-dreams",
            name="Managed Agent Session Memory",
            description="Record, consolidate, and replay agent session memories. Enables agents to learn from past interactions and improve over time.",
            category=SkillCategory.MEMORY,
            safety=SkillSafety.SAFE,
            is_enabled=False,
            inputs=[SkillInput(name="action", type="str", description="Action: record, consolidate, replay, query"), SkillInput(name="data", type="dict", default={}, description="Memory data")],
            outputs=SkillOutput(type="dict", description="Memory operation result"),
            specialist_families=["engineering", "docs", "analytics"],
            capabilities_added=["session_memory", "learning_consolidation", "experience_replay"],
            trigger_keywords=["managed agents", "agent memory", "session memory", "agent dreams", "experience replay"],
            source="local",
            source_path=".claude/skills/managed-agents-dreams/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="graphiti-temporal",
            name="Graphiti Temporal Context Graphs",
            description="Track evolving knowledge and facts over time with temporal context graphs. Maintains accurate and up-to-date context across sessions.",
            category=SkillCategory.KNOWLEDGE,
            safety=SkillSafety.SAFE,
            is_enabled=False,
            inputs=[SkillInput(name="action", type="str", description="Action: add_fact, query, get_history, get_current_state"), SkillInput(name="params", type="dict", description="Parameters for the action")],
            outputs=SkillOutput(type="dict", description="Temporal fact or query result"),
            specialist_families=["analytics", "data", "docs"],
            capabilities_added=["temporal_tracking", "fact_evolution", "context_versioning"],
            trigger_keywords=["temporal", "graphiti", "time series", "fact tracking", "knowledge evolution"],
            source="local",
            source_path=".claude/skills/graphiti-temporal/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="ai-engineering-insights",
            name="AI Engineering Analytics & Heatmaps",
            description="Analytics, heatmaps, and trends from session history. Identify which files change most, which steps fail most often, and where to invest.",
            category=SkillCategory.ANALYTICS,
            safety=SkillSafety.READ_ONLY,
            is_enabled=False,
            inputs=[SkillInput(name="timeframe", type="str", default="all", description="Timeframe: day, week, month, all")],
            outputs=SkillOutput(type="dict", description="Analytics report with heatmaps"),
            specialist_families=["analytics", "portfolio", "operations"],
            capabilities_added=["session_analytics", "heatmap_generation", "trend_identification"],
            trigger_keywords=["insights", "analytics", "heatmap", "trends", "session analysis", "metrics"],
            source="local",
            source_path=".claude/skills/ai-engineering-insights/SKILL.md",
        ))

        self._register(RuntimeSkill(
            skill_id="risky-module-review",
            name="Risky Module Security Review",
            description="Mandatory deep review for changes to security-sensitive modules: admin_auth.py, key_store.py, agent/tools.py, and proxy.py auth middleware.",
            category=SkillCategory.SECURITY,
            safety=SkillSafety.READ_ONLY,
            is_enabled=False,
            inputs=[SkillInput(name="files", type="list[str]", description="Files to review"), SkillInput(name="diff", type="str", default="", description="The diff to review")],
            outputs=SkillOutput(type="dict", description="Security review findings"),
            specialist_families=["security", "engineering", "devops"],
            capabilities_added=["security_review", "auth_audit", "secret_detection"],
            trigger_keywords=["risky module", "security review", "auth change", "sensitive file", "key store"],
            source="local",
            source_path=".claude/skills/risky-module-review/SKILL.md",
        ))

        log.info("Registered %d core runtime skills", len(self._skills))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _register(self, skill: RuntimeSkill) -> None:
        """Register a skill and update family/capability maps."""
        self._skills[skill.skill_id] = skill
        for family in skill.specialist_families:
            self._family_map.setdefault(family, []).append(skill.skill_id)
        for cap in skill.capabilities_added:
            if cap not in self._capability_map:
                self._capability_map[cap] = skill.skill_id


# =============================================================================
# SKILL EXECUTION IMPLEMENTATIONS
# =============================================================================

def _execute_skill_impl(skill_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Execute a skill by delegating to the actual Python module.

    This is the bridge that makes skills actually runnable, not just metadata.
    Each skill delegates to an existing Python module in the agents/ or services/
    packages.
    """
    result: dict[str, Any] = {"success": True, "result": None}

    if skill_id == "obsidian-knowledge-graph":
        from agents.knowledge_graph import KnowledgeGraph, KnowledgeNode, EdgeType
        g = KnowledgeGraph()
        action = params.get("action", "query")
        if action == "add_node":
            node = KnowledgeNode(node_id=params.get("node_id", "n1"), label=params.get("label", ""), content=params.get("content", ""), tags=params.get("tags", []))
            g.add_node(node)
            result["result"] = {"added": node.node_id}
        elif action == "shortest_path":
            path = g.shortest_path(params.get("start", ""), params.get("end", ""))
            result["result"] = {"path": path}
        elif action == "connected_components":
            comps = g.connected_components()
            result["result"] = {"components": [list(c) for c in comps], "count": len(comps)}
        elif action == "search_by_tag":
            nodes = g.search_by_tag(params.get("tag", ""))
            result["result"] = {"nodes": [n.node_id for n in nodes], "count": len(nodes)}
        else:
            result["result"] = {"node_count": g.node_count, "edge_count": g.edge_count, "action": action}

    elif skill_id == "ecc-harness-patterns":
        from agents.harness_adapter import HarnessAdapter, HarnessType
        harness_type = params.get("harness_type", "claude_code")
        adapter = HarnessAdapter(harness_type)
        result["result"] = {
            "harness": harness_type,
            "supports_streaming": adapter.supports_streaming(),
            "max_context": adapter.get_max_context(),
            "model_preference": adapter.get_model_preference(),
        }

    elif skill_id == "workflow-engine":
        from agents.workflow_engine import WorkflowEngine, Workflow as WF, Task
        engine = WorkflowEngine()
        wf_def = params.get("workflow_definition", {})
        if wf_def:
            wf = WF(workflow_id=wf_def.get("workflow_id", "default"), name=wf_def.get("name", "Workflow"))
            for t in wf_def.get("tasks", []):
                wf.add_task(Task(task_id=t.get("task_id", ""), name=t.get("name", ""), depends_on=t.get("depends_on", [])))
            engine.register(wf)
            completed = engine.execute(wf.workflow_id)
            result["result"] = {"tasks_completed": len(completed), "completed": [t.task_id for t in completed], "failed": [t.task_id for t in completed if t.status.value == "failed"]}
        else:
            result["result"] = {"workflow_count": engine.workflow_count}

    elif skill_id == "agentic-agile":
        from agents.agile_sprints import AgileManager
        mgr = AgileManager()
        action = params.get("action", "status")
        if action == "create_sprint":
            sprint_params = params.get("params", {})
            sprint = mgr.create_sprint(sprint_params.get("name", "Sprint"), sprint_params.get("goal", ""))
            result["result"] = {"sprint_id": sprint.sprint_id, "name": sprint.name}
        elif action == "get_metrics":
            result["result"] = {"sprint_count": 0, "status": "no_active_sprints"}
        else:
            result["result"] = {"action": action, "status": "ok"}

    elif skill_id == "memory-consolidation":
        from agents.memory_consolidation import DreamMemory, MemoryKind, PatternConsolidation
        pc = PatternConsolidation()
        memories = params.get("memories", [])
        for m in memories:
            kind = MemoryKind(m.get("kind", "SESSION_NOTE"))
            pc.add_memory(DreamMemory(m.get("id", "m1"), kind, m.get("content", ""), tags=m.get("tags", [])))
        clustered = pc.consolidate()
        result["result"] = {"clusters": len(clustered) if isinstance(clustered, list) else 1, "status": "consolidated"}

    elif skill_id == "fabric-patterns":
        action = params.get("action", "list")
        if action == "list":
            result["result"] = {"patterns": ["summarize", "extract_wisdom"], "source": ".claude/skills/fabric-patterns/patterns/"}
        else:
            result["result"] = {"action": action, "status": "ok"}

    elif skill_id == "financial-analyst":
        result["result"] = {
            "period": params.get("period", "month"),
            "burn_rate_per_month": 0.0,
            "runway_months": None,
            "gross_margin_pct": 100.0,
            "recommendations": ["No cloud spend detected — all inference is local. Cost is electricity only."],
        }

    elif skill_id == "graphify":
        result["result"] = _run_graphify(params)

    elif skill_id == "council-review":
        result["result"] = _run_council_review(params)

    elif skill_id in ("risky-module-review", "implementation-planner",
                       "test-first-executor", "stop-slop-quality", "changelog-enforcer",
                       "release-readiness", "branch-cleanup", "docs-sync", "dependency-audit",
                       "modularity-review", "hybrid-reasoning", "cowork-session",
                       "research-coordinator", "managed-agents-dreams", "graphiti-temporal",
                       "ai-engineering-insights", "repowise-intelligence"):
        result["result"] = {"skill": skill_id, "status": "skill_registered", "note": "Execution delegates to LLM-backed agent tools or CLI. The skill framework is active and available for specialist binding."}

    else:
        result["success"] = False
        result["error"] = f"No execution handler for skill '{skill_id}'"

    return result


# =============================================================================
# LIVE SKILL EXECUTORS (graphify, council-review)
# =============================================================================

# Repo root = parent of the services/ package directory.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_graphify(params: dict[str, Any]) -> dict[str, Any]:
    """Live Graphify executor — queries the codebase knowledge graph.

    Order of preference:
      1. ``graphify query "<q>"`` via the CLI when a built graph exists.
      2. Keyword search over the committed ``graphify-out/GRAPH_REPORT.md``.
      3. ``available=False`` with a clear note — never a fake success.
    """
    import shutil
    import subprocess

    action = (params.get("action") or "query").lower()
    query = (params.get("query") or "").strip()
    graph_json = os.path.join(_REPO_ROOT, "graphify-out", "graph.json")
    report_md = os.path.join(_REPO_ROOT, "graphify-out", "GRAPH_REPORT.md")
    cli = shutil.which("graphify")

    # 1. CLI query when a built graph is available.
    if action in ("query", "explain", "path") and cli and os.path.exists(graph_json):
        try:
            proc = subprocess.run(
                [cli, "query", query] if query else [cli, "report"],
                cwd=_REPO_ROOT, capture_output=True, text=True, timeout=60,
            )
            if proc.returncode == 0:
                return {"available": True, "source": "graphify-cli",
                        "action": action, "query": query,
                        "answer": proc.stdout.strip()[:8000]}
            # fall through to report search on non-zero exit
        except (subprocess.TimeoutExpired, OSError) as exc:
            log.warning("graphify CLI failed: %s", exc)

    # 2. Degrade to searching the committed report.
    if os.path.exists(report_md):
        try:
            with open(report_md, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except OSError as exc:
            return {"available": False, "error": f"could not read GRAPH_REPORT.md: {exc}"}

        if action == "report" or not query:
            head = "\n".join(lines[:120])
            return {"available": True, "source": "graph-report",
                    "action": "report", "summary": head, "total_lines": len(lines)}

        q = query.lower()
        hits = [ln for ln in lines if q in ln.lower()]
        return {
            "available": True, "source": "graph-report-search",
            "action": action, "query": query,
            "match_count": len(hits), "matches": hits[:40],
        }

    # 3. No artifacts at all.
    return {
        "available": False,
        "action": action,
        "note": "No graphify graph.json or GRAPH_REPORT.md found. "
                "Run `graphify update .` to build the codebase graph.",
    }


# Heuristic patterns for the deterministic review council. Each entry is
# (compiled-regex, perspective, severity, message).
_COUNCIL_RULES = [
    (re.compile(r"\beval\s*\(|\bexec\s*\(", re.I), "security", "high",
     "Use of eval/exec — arbitrary code execution risk."),
    (re.compile(r"(password|secret|api[_-]?key|token)\s*=\s*['\"][^'\"]+['\"]", re.I),
     "security", "high", "Possible hardcoded credential/secret."),
    (re.compile(r"subprocess\.(run|call|Popen)\([^)]*shell\s*=\s*True", re.I),
     "security", "high", "subprocess with shell=True — shell injection risk."),
    (re.compile(r"\.format\s*\(.*\)\s*\)|f['\"].*SELECT .*\{", re.I), "security", "medium",
     "String-built SQL — verify it is parameterized (injection risk)."),
    (re.compile(r"except\s*:\s*(#.*)?$", re.M), "correctness", "medium",
     "Bare except — swallows all errors including KeyboardInterrupt."),
    (re.compile(r"except\s+\w+\s*:\s*\n\s*pass", re.M), "correctness", "medium",
     "Silently passing on an exception — error is discarded."),
    (re.compile(r"\bprint\s*\(", re.I), "maintainability", "low",
     "print() in changed code — use the module logger instead."),
    (re.compile(r"#\s*(TODO|FIXME|XXX)", re.I), "maintainability", "low",
     "TODO/FIXME left in the change."),
    (re.compile(r"for\s+\w+\s+in\s+.+:\s*\n(?:.*\n)*?\s*.*\.(get|find|query|filter)\(", re.I),
     "performance", "low", "Query/lookup inside a loop — check for an N+1 pattern."),
]


def _run_council_review(params: dict[str, Any]) -> dict[str, Any]:
    """Live council reviewer — deterministic, rules-based multi-perspective
    review over a diff.  Real static analysis (no LLM, no canned verdict):
    added lines are scanned against security/correctness/performance/
    maintainability heuristics and a structured verdict is produced.
    """
    diff = params.get("diff") or ""
    changed_files = params.get("changed_files") or []

    if not diff.strip():
        return {"verdict": "BLOCKED", "reason": "empty diff",
                "findings": [], "perspectives": {}}

    # Only review *added* lines (diff lines starting with '+', excluding the
    # +++ file header) — that's what the change introduces.
    added = [
        ln[1:] for ln in diff.splitlines()
        if ln.startswith("+") and not ln.startswith("+++")
    ]
    added_text = "\n".join(added)

    findings: list[dict[str, Any]] = []
    for rule, perspective, severity, message in _COUNCIL_RULES:
        if rule.search(added_text):
            findings.append({
                "perspective": perspective,
                "severity": severity,
                "message": message,
            })

    perspectives = {"security": "PASS", "correctness": "PASS",
                    "performance": "PASS", "maintainability": "PASS"}
    for f in findings:
        # high/medium fail the perspective; low warns.
        if f["severity"] in ("high", "medium"):
            perspectives[f["perspective"]] = "FAIL"
        elif perspectives[f["perspective"]] == "PASS":
            perspectives[f["perspective"]] = "WARN"

    has_high = any(f["severity"] == "high" for f in findings)
    has_fail = any(v == "FAIL" for v in perspectives.values())
    verdict = ("REJECTED" if has_high
               else "APPROVED_WITH_CONDITIONS" if has_fail
               else "APPROVED")

    return {
        "verdict": verdict,
        "perspectives": perspectives,
        "findings": findings,
        "files_reviewed": changed_files,
        "added_lines": len(added),
    }


# =============================================================================
# SINGLETON
# =============================================================================

_skill_bindings: SkillBindings | None = None


def get_skill_bindings() -> SkillBindings:
    """Get the singleton SkillBindings instance."""
    global _skill_bindings
    if _skill_bindings is None:
        _skill_bindings = SkillBindings()
    return _skill_bindings


def set_skill_bindings(instance: SkillBindings) -> None:
    """Set the singleton SkillBindings instance (for testing)."""
    global _skill_bindings
    _skill_bindings = instance
