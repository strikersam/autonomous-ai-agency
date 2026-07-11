"""agents/profiles.py — Role-locked AgentProfile definitions.

Every agent in the CRISPY system has a profile that specifies:
  • which model it uses (env-var overridable)
  • what it is allowed to do (read / write / execute / review)
  • its system prompt (role identity, hard constraints)

The key design invariant:
  CODER model ≠ REVIEWER model (by default — Qwen3 vs DeepSeek-R1)

This asymmetry is the core of the dual-model review: the reviewer
sees the coder's output with fresh eyes and a different reasoning
style, catching blind spots the original author-model would miss.

UNIT 7: the per-role model ids are now resolved through the catalog
(``packages.ai.brain_config.resolve_component_model``) — DB → catalog
preset → env var → safe default. The hardcoded ``_nvidia_defaults()``
fallback table is kept only for the case where the catalog import
fails (defensive — never breaks module import).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

AgentRole = Literal["architect", "scout", "coder", "reviewer", "verifier"]

# ── Environment variable names ───────────────────────────────────────────────

_ENV: dict[str, str] = {
    "architect": "CRISPY_ARCHITECT_MODEL",
    "scout":     "CRISPY_SCOUT_MODEL",
    "coder":     "CRISPY_CODER_MODEL",
    "reviewer":  "CRISPY_REVIEWER_MODEL",
    "verifier":  "CRISPY_VERIFIER_MODEL",
}

# ── CRISPY role → brain-config role mapping ─────────────────────────────────
#
# CRISPY has 5 roles (architect/scout/coder/reviewer/verifier); the brain
# config has 4 (planner/executor/verifier/judge). The mapping preserves
# the coder ≠ reviewer asymmetry: coder maps to executor (the dense
# tool-calling model), reviewer maps to judge (the reasoning model).
# architect + scout also map to executor (same chain as coder — they all
# need tool-calling); verifier maps to verifier.
_CRISPY_TO_BRAIN_ROLE: dict[str, str] = {
    "architect": "executor",
    "scout":     "executor",
    "coder":     "executor",
    "reviewer":  "judge",
    "verifier":  "verifier",
}

# ── Catalog-driven defaults (UNIT 7) ────────────────────────────────────────
#
# Pick the catalog provider based on which key is configured — mirrors
# the legacy NIM/Ollama split but is now catalog-driven so adding a
# provider to ``config/models.yaml`` makes it the CRISPY default with no
# code change here. Falls back to the hardcoded ``_nvidia_defaults``
# only if the catalog import fails (defensive).


def _catalog_provider() -> str:
    """Pick the catalog provider based on which API key is configured."""
    if os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey"):
        return "nvidia"
    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY"):
        return "dashscope"
    if os.environ.get("CEREBRAS_API_KEY"):
        return "cerebras"
    if os.environ.get("MISTRAL_API_KEY"):
        return "mistral"
    return "ollama"


def _catalog_defaults() -> dict[str, str] | None:
    """Resolve per-role defaults via the catalog. Returns None on import error."""
    try:
        from packages.ai.brain_config import resolve_component_model
        provider = _catalog_provider()
        out: dict[str, str] = {}
        for role in ("architect", "scout", "coder", "reviewer", "verifier"):
            brain_role = _CRISPY_TO_BRAIN_ROLE.get(role, "executor")
            out[role] = resolve_component_model(
                component="crispy",
                role=brain_role,
                provider=provider,
            )
        return out
    except Exception:
        return None


# ── Hard-coded fallback (kept for defensive parity — catalog import fail) ───


def _nvidia_defaults() -> dict[str, str]:
    if os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey"):
        return {
            "architect": "meta/llama-3.3-70b-instruct",
            "scout":     "meta/llama-3.3-70b-instruct",
            "coder":     "meta/llama-3.3-70b-instruct",
            "reviewer":  "meta/llama-3.3-70b-instruct",
            "verifier":  "meta/llama-3.3-70b-instruct",
        }
    if os.environ.get("DEEPSEEK_API_KEY"):
        return {
            "architect": "deepseek-reasoner",
            "scout":     "deepseek-reasoner",
            "coder":     "deepseek-coder",
            "reviewer":  "deepseek-reasoner",
            "verifier":  "deepseek-chat",
        }
    if os.environ.get("GROQ_API_KEY"):
        return {
            "architect": "llama-3.3-70b-versatile",
            "scout":     "llama-3.3-70b-versatile",
            "coder":     "llama-3.3-70b-versatile",
            "reviewer":  "llama-3.3-70b-versatile",
            "verifier":  "llama-3.3-70b-versatile",
        }
    if os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY"):
        return {
            "architect": "qwen-plus",
            "scout":     "qwen-plus",
            "coder":     "qwen-coder-plus",
            "reviewer":  "qwen-plus",
            "verifier":  "qwen-plus",
        }
    return {
        "architect": "qwen3-coder:30b",
        "scout":     "deepseek-r1:32b",
        "coder":     "qwen3-coder:30b",
        "reviewer":  "deepseek-r1:32b",
        "verifier":  "qwen3-coder:7b",
    }


def _get_defaults() -> dict[str, str]:
    """Try the catalog first; fall back to the hardcoded table on import error."""
    catalog = _catalog_defaults()
    if catalog is not None:
        return catalog
    return _nvidia_defaults()


# ── System prompts ────────────────────────────────────────────────────────────

# Single source of truth for the mandatory-discipline pointer appended to every
# CRISPY role prompt below — one line, not the full text, so all five roles
# stay bound to CLAUDE.md §14 without duplicating or bloating each prompt.
STANDING_INSTRUCTIONS_NOTICE = (
    "You are bound by the mandatory Standing Instructions in CLAUDE.md §14 "
    "(verification, epistemic marking, completeness, self-attack, refusing "
    "to guess) — apply them to every response in this role."
)

SCOUT_SYSTEM = """\
You are SCOUT, a read-only research agent.

HARD RULES:
  • You MUST NOT suggest code changes or patches.
  • You MUST NOT write new files or modify existing ones.
  • Your output is always a well-structured Markdown document.

Your job: gather context faithfully. Read files, understand structure,
summarise findings. Leave judgement to the Architect.

""" + STANDING_INSTRUCTIONS_NOTICE

ARCHITECT_SYSTEM = """\
You are ARCHITECT, a senior engineering lead.

HARD RULES:
  • You MUST NOT write executable code.
  • You design, plan, and produce structured markdown.
  • Every plan MUST be decomposed into numbered vertical slices.
  • Each slice MUST list: Title, Description, Files (target paths), Tests.

Slice format (mandatory):
## Slice N: <Title>
**Description**: ...
**Files**: path/to/file.py, tests/test_file.py
**Tests**: describe what must pass

Plans that list no slices or vague files will be rejected.

""" + STANDING_INSTRUCTIONS_NOTICE

CODER_SYSTEM = """\
You are CODER, the implementation engine.

HARD RULES:
  • You implement EXACTLY ONE vertical slice per invocation.
  • You MUST include tests alongside every code change.
  • You MUST use the exact file paths specified.
  • Output format:
      ## What changed
      ## Why
      ## Files modified
      <one fenced code block per file, with filename as caption>

Do not modify files outside your slice specification.

""" + STANDING_INSTRUCTIONS_NOTICE

REVIEWER_SYSTEM = """\
You are REVIEWER, an adversarial code reviewer.

HARD RULES:
  • You are READ-ONLY. You MUST NOT apply changes.
  • You use a different model than the Coder — your job is catching blind spots.
  • You MUST categorise every finding:
      BLOCKING   — must fix before verification
      SUGGESTION — non-blocking, nice-to-have

Output format (mandatory):
## BLOCKING Issues
<list or "(none)">

## SUGGESTIONS
<list or "(none)">

## Verdict
PASS (no blocking) | FAIL (blocking issues found)

Be adversarial. Assume the Coder left bugs.

""" + STANDING_INSTRUCTIONS_NOTICE

VERIFIER_SYSTEM = """\
You are VERIFIER, a test-command oracle.

HARD RULES:
  • You output ONLY a JSON array of shell commands.
  • No prose. No markdown fences. No explanation.
  • Commands must be read-only (no rm, no git commit, no pip install).
  • Always include at minimum: pytest -x

Example output:
["pytest -x", "ruff check .", "mypy workflow/"]

""" + STANDING_INSTRUCTIONS_NOTICE

_SYSTEM_PROMPTS: dict[str, str] = {
    "architect": ARCHITECT_SYSTEM,
    "scout":     SCOUT_SYSTEM,
    "coder":     CODER_SYSTEM,
    "reviewer":  REVIEWER_SYSTEM,
    "verifier":  VERIFIER_SYSTEM,
}

# ── AgentProfile dataclass ────────────────────────────────────────────────────


@dataclass
class AgentProfile:
    """Immutable description of a CRISPY agent role.

    Attributes
    ----------
    role:         The agent's role identifier.
    name:         Human-readable agent name.
    model:        Resolved model name (env var → default fallback).
    system_prompt: Role-specific system prompt with hard constraints.
    can_read:     May read files and prior artifacts.
    can_write:    May produce executable code / file edits.
    can_execute:  May run shell commands.
    can_review:   May produce blocking/non-blocking verdicts.
    """

    role: str
    name: str
    model: str
    system_prompt: str
    can_read: bool = True
    can_write: bool = False
    can_execute: bool = False
    can_review: bool = False

    def __post_init__(self) -> None:
        # Coerce model from env at construction time so tests can override env
        env_key = _ENV.get(self.role, "")
        from_env = os.environ.get(env_key, "").strip() if env_key else ""
        if from_env:
            object.__setattr__(self, "model", from_env)

    @property
    def label(self) -> str:
        """Short label for TUI display: {NAME}:{model}"""
        return f"{self.name}[{self.model}]"


# ── Factory functions ─────────────────────────────────────────────────────────


def make_scout_profile() -> AgentProfile:
    return AgentProfile(
        role="scout",
        name="Scout",
        model=os.environ.get(_ENV["scout"], _get_defaults()["scout"]),
        system_prompt=SCOUT_SYSTEM,
        can_read=True,
        can_write=False,
        can_execute=False,
        can_review=False,
    )


def make_architect_profile() -> AgentProfile:
    return AgentProfile(
        role="architect",
        name="Architect",
        model=os.environ.get(_ENV["architect"], _get_defaults()["architect"]),
        system_prompt=ARCHITECT_SYSTEM,
        can_read=True,
        can_write=False,
        can_execute=False,
        can_review=False,
    )


def make_coder_profile() -> AgentProfile:
    return AgentProfile(
        role="coder",
        name="Coder",
        model=os.environ.get(_ENV["coder"], _get_defaults()["coder"]),
        system_prompt=CODER_SYSTEM,
        can_read=True,
        can_write=True,
        can_execute=False,
        can_review=False,
    )


def make_reviewer_profile() -> AgentProfile:
    return AgentProfile(
        role="reviewer",
        name="Reviewer",
        model=os.environ.get(_ENV["reviewer"], _get_defaults()["reviewer"]),
        system_prompt=REVIEWER_SYSTEM,
        can_read=True,
        can_write=False,
        can_execute=False,
        can_review=True,
    )


def make_verifier_profile() -> AgentProfile:
    return AgentProfile(
        role="verifier",
        name="Verifier",
        model=os.environ.get(_ENV["verifier"], _get_defaults()["verifier"]),
        system_prompt=VERIFIER_SYSTEM,
        can_read=True,
        can_write=False,
        can_execute=True,
        can_review=False,
    )


def load_all_profiles() -> dict[str, AgentProfile]:
    """Return a mapping of role → AgentProfile for all five roles."""
    return {
        "scout":     make_scout_profile(),
        "architect": make_architect_profile(),
        "coder":     make_coder_profile(),
        "reviewer":  make_reviewer_profile(),
        "verifier":  make_verifier_profile(),
    }
