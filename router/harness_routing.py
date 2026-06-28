from __future__ import annotations

"""Cross-Harness Routing (E1 roadmap item).

Detects which AI coding tool (harness) is calling the proxy and adapts
model selection accordingly:

- Claude Code → highest reasoning model (deepseek-r1 or nemotron)
- Cursor → fast coder (qwen3-coder:7b or gemma4:2b)
- Aider → balanced coder (qwen3-coder:30b)
- Continue.dev → lightweight (qwen3-coder:7b)
- Cline/Codebuff → reasoning-heavy (deepseek-r1:32b)
- Unknown → default routing

Detection uses User-Agent headers, X-Tool headers, and request fingerprinting.

Usage::

    from router.harness_routing import detect_harness, route_for_harness

    harness = detect_harness(request_headers)
    preferred_model = route_for_harness(harness, task_category="code_generation")
"""

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("qwen-proxy")

_HARNESS_ROUTING_ENABLED = os.environ.get("HARNESS_ROUTING_ENABLED", "true").strip().lower() in ("true", "1", "yes")


class Harness(Enum):
    """Known AI coding tools that call the proxy."""

    CLAUDE_CODE = "claude_code"
    CURSOR = "cursor"
    AIDER = "aider"
    CONTINUE = "continue_dev"
    CLINE = "cline"
    CODEBUFF = "codebuff"
    WINDSURF = "windsurf"
    CODY = "cody"
    COPILOT = "copilot"
    UNKNOWN = "unknown"


@dataclass
class HarnessProfile:
    """Preferred model routing for each harness by task category."""

    harness: Harness
    preferred_coder: str      # Model for code execution
    preferred_reasoning: str  # Model for planning/reasoning
    preferred_fast: str       # Model for fast/lightweight tasks
    min_context: int = 4096   # Minimum context window needed
    max_latency_ms: int = 0   # Max acceptable latency (0 = unlimited)

    @staticmethod
    def defaults() -> dict[Harness, HarnessProfile]:
        """Return cached harness profiles (rebuilt when NVIDIA key changes)."""
        global _cached_profiles
        nvidia = bool(os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey"))
        cache_key = str(nvidia)
        if _cached_profiles and _cached_profiles_key == cache_key:
            return _cached_profiles

        _coder = "nvidia/llama-3.3-nemotron-super-49b-v1.5" if nvidia else "qwen3-coder:30b"
        _fast = "meta/llama-3.1-8b-instruct" if nvidia else "qwen3-coder:7b"
        _reason = "deepseek-ai/deepseek-v4-pro" if nvidia else "deepseek-r1:32b"
        _light = "meta/llama-3.1-8b-instruct" if nvidia else "gemma4:2b"

        _cached_profiles = {
            Harness.CLAUDE_CODE: HarnessProfile(
                harness=Harness.CLAUDE_CODE,
                preferred_coder=_coder,
                preferred_reasoning=_reason,
                preferred_fast=_coder,
                min_context=32768,
            ),
            Harness.CURSOR: HarnessProfile(
                harness=Harness.CURSOR,
                preferred_coder=_fast,
                preferred_reasoning=_coder,
                preferred_fast=_light,
                max_latency_ms=2000,
            ),
            Harness.AIDER: HarnessProfile(
                harness=Harness.AIDER,
                preferred_coder=_coder,
                preferred_reasoning=_reason,
                preferred_fast=_fast,
            ),
            Harness.CONTINUE: HarnessProfile(
                harness=Harness.CONTINUE,
                preferred_coder=_fast,
                preferred_reasoning=_coder,
                preferred_fast=_light,
                max_latency_ms=3000,
            ),
            Harness.CLINE: HarnessProfile(
                harness=Harness.CLINE,
                preferred_coder=_reason,
                preferred_reasoning=_reason,
                preferred_fast=_coder,
                min_context=16384,
            ),
            Harness.CODEBUFF: HarnessProfile(
                harness=Harness.CODEBUFF,
                preferred_coder=_reason,
                preferred_reasoning=_reason,
                preferred_fast=_fast,
                min_context=16384,
            ),
            Harness.WINDSURF: HarnessProfile(
                harness=Harness.WINDSURF,
                preferred_coder=_fast,
                preferred_reasoning=_coder,
                preferred_fast=_light,
                max_latency_ms=2000,
            ),
            Harness.CODY: HarnessProfile(
                harness=Harness.CODY,
                preferred_coder=_fast,
                preferred_reasoning=_coder,
                preferred_fast=_light,
            ),
            Harness.COPILOT: HarnessProfile(
                harness=Harness.COPILOT,
                preferred_coder=_fast,
                preferred_reasoning=_coder,
                preferred_fast=_light,
                max_latency_ms=3000,
            ),
            Harness.UNKNOWN: HarnessProfile(
                harness=Harness.UNKNOWN,
                preferred_coder=_coder,
                preferred_reasoning=_reason,
                preferred_fast=_fast,
            ),
        }
        _cached_profiles_key = cache_key
        return _cached_profiles


# ── Harness detection ────────────────────────────────────────────────────────

_USER_AGENT_PATTERNS: dict[str, Harness] = {
    "claude-code": Harness.CLAUDE_CODE,
    "anthropic-claude": Harness.CLAUDE_CODE,
    "cursor": Harness.CURSOR,
    "aider": Harness.AIDER,
    "continue": Harness.CONTINUE,
    "cline": Harness.CLINE,
    "codebuff": Harness.CODEBUFF,
    "windsurf": Harness.WINDSURF,
    "cody": Harness.CODY,
    "github-copilot": Harness.COPILOT,
}

_TOOL_HEADERS = {
    "x-tool": None,          # Generic: Cursor, Continue set this
    "x-client": None,        # Alternative: Cline, Codebuff
    "x-source": None,        # Alternative: Windsurf
}


def detect_harness(headers: dict[str, str] | None = None) -> Harness:
    """Detect which AI coding tool is calling the proxy.

    Checks in priority order:
    1. X-Tool / X-Client / X-Source headers
    2. User-Agent header pattern matching
    3. Request fingerprint (model name pattern matching)

    Returns Harness.UNKNOWN if detection fails.
    """
    if not _HARNESS_ROUTING_ENABLED:
        return Harness.UNKNOWN

    if headers is None:
        return Harness.UNKNOWN

    # Lowercase all header keys for case-insensitive matching
    lowered = {k.lower(): v.lower() if isinstance(v, str) else v for k, v in headers.items()}

    # 1. Check explicit tool headers
    for header_name in ("x-tool", "x-client", "x-source"):
        value = lowered.get(header_name, "")
        if isinstance(value, str):
            for pattern, harness in _USER_AGENT_PATTERNS.items():
                if pattern in value:
                    log.debug("Harness detected via %s: %s → %s", header_name, value, harness.value)
                    return harness

    # 2. Check User-Agent
    ua = lowered.get("user-agent", "")
    if isinstance(ua, str):
        for pattern, harness in _USER_AGENT_PATTERNS.items():
            if pattern in ua:
                log.debug("Harness detected via User-Agent: %s → %s", ua[:80], harness.value)
                return harness

    return Harness.UNKNOWN


def route_for_harness(
    harness: Harness,
    *,
    task_category: str = "code_generation",
) -> str | None:
    """Return the preferred model for this harness and task, or None if no preference.

    Callers should use the returned model name as an override.
    """
    if not _HARNESS_ROUTING_ENABLED or harness == Harness.UNKNOWN:
        return None

    profiles = HarnessProfile.defaults()
    profile = profiles.get(harness)
    if profile is None:
        return None

    # Route by task category
    if task_category in ("reasoning", "planning", "analysis", "complex_tasks"):
        return profile.preferred_reasoning
    elif task_category in ("fast_response", "conversation"):
        return profile.preferred_fast
    else:
        return profile.preferred_coder


def harness_context_limit(harness: Harness) -> int:
    """Return the minimum recommended context window for the harness."""
    profiles = HarnessProfile.defaults()
    profile = profiles.get(harness)
    return profile.min_context if profile else 4096


# ── Cached profile lookup ──────────────────────────────────────────────────

_cached_profiles: dict[Harness, HarnessProfile] | None = None
_cached_profiles_key: str = ""

# ── Module-level stats ────────────────────────────────────────────────────────

_harness_hits: dict[str, int] = {h.value: 0 for h in Harness}


def record_harness_hit(harness: Harness) -> None:
    _harness_hits[harness.value] = _harness_hits.get(harness.value, 0) + 1


def harness_stats() -> dict[str, Any]:
    return {
        "enabled": _HARNESS_ROUTING_ENABLED,
        "hits": dict(_harness_hits),
        "total": sum(_harness_hits.values()),
    }
