"""agents/harness_adapter.py — ECC Cross-Harness Adapter

Normalises API differences across AI coding harnesses (Claude Code, Cursor,
Codex, OpenCode, Gemini, Zed, GitHub Copilot) so the orchestrator can route
requests regardless of which tool the user or agent is using.

Inspired by ECC (https://github.com/affaan-m/ECC).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("qwen-proxy")


@dataclass(frozen=True)
class HarnessSpec:
    harness_id: str
    display_name: str
    context_key: str
    supports: list[str] = field(default_factory=list)
    default_model: str | None = None
    is_active: bool = False


HARNESS_CATALOG: dict[str, HarnessSpec] = {
    "claude_code": HarnessSpec(
        harness_id="claude_code",
        display_name="Claude Code",
        context_key="workspace",
        supports=["streaming", "tool_use", "multi_step"],
        default_model="claude-sonnet-4-6",
    ),
    "cursor": HarnessSpec(
        harness_id="cursor",
        display_name="Cursor",
        context_key="editor",
        supports=["streaming", "streaming_chunks", "inline_edit"],
        default_model="nvidia/llama-3.3-nemotron-super-49b-v1",
    ),
    "codex": HarnessSpec(
        harness_id="codex",
        display_name="OpenAI Codex CLI",
        context_key="project",
        supports=["completion", "streaming"],
        default_model="nvidia/llama-3.3-nemotron-super-49b-v1",
    ),
    "opencode": HarnessSpec(
        harness_id="opencode",
        display_name="OpenCode",
        context_key="workspace",
        supports=["streaming", "tool_use", "multi_step"],
        default_model="nvidia/llama-3.3-nemotron-super-49b-v1",
    ),
    "gemini_cli": HarnessSpec(
        harness_id="gemini_cli",
        display_name="Gemini CLI",
        context_key="workspace",
        supports=["streaming", "multi_modal"],
        default_model="gemini-2.5-pro",
    ),
    "zed": HarnessSpec(
        harness_id="zed",
        display_name="Zed AI",
        context_key="editor",
        supports=["completion", "inline_edit"],
        default_model="nvidia/llama-3.3-nemotron-super-49b-v1",
    ),
    "github_copilot": HarnessSpec(
        harness_id="github_copilot",
        display_name="GitHub Copilot",
        context_key="editor",
        supports=["completion", "inline_edit"],
        default_model="nvidia/llama-3.3-nemotron-super-49b-v1",
    ),
    "aider": HarnessSpec(
        harness_id="aider",
        display_name="Aider",
        context_key="workspace",
        supports=["streaming", "tool_use", "multi_step"],
        default_model="nvidia/nemotron-3-super-120b-a12b",
    ),
    "continue": HarnessSpec(
        harness_id="continue",
        display_name="Continue.dev",
        context_key="editor",
        supports=["streaming", "completion"],
        default_model="nvidia/llama-3.3-nemotron-super-49b-v1",
    ),
    "telegram": HarnessSpec(
        harness_id="telegram",
        display_name="Telegram Bot",
        context_key="chat",
        supports=["streaming", "freebuff"],
        default_model="nvidia/nemotron-3-super-120b-a12b",
    ),
}


class HarnessAdapter:
    """Adapt harness-native requests to the local-llm-server internal format.

    Each harness submits requests in its own dialect; this adapter normalises
    them to a common shape before the orchestrator or agent runner processes
    them.  Also provides harness-aware model selection hints.
    """

    def __init__(self) -> None:
        self._active: dict[str, HarnessSpec] = {}

    def register_active(self, harness_id: str) -> None:
        spec = HARNESS_CATALOG.get(harness_id)
        if spec is None:
            log.warning("Unknown harness %r — not registered", harness_id)
            return
        self._active[harness_id] = HarnessSpec(
            harness_id=spec.harness_id,
            display_name=spec.display_name,
            context_key=spec.context_key,
            supports=list(spec.supports),
            default_model=spec.default_model,
            is_active=True,
        )
        log.info("Harness activated: %s (%s)", spec.display_name, harness_id)

    def deregister(self, harness_id: str) -> None:
        self._active.pop(harness_id, None)

    @property
    def active_harness_ids(self) -> list[str]:
        return sorted(self._active)

    def detect_harness(self, request_headers: dict[str, str]) -> str | None:
        """Detect which harness sent this request from headers.

        Check order: explicit header → user-agent heuristic → unknown.
        """
        explicit = request_headers.get("x-harness-id") or request_headers.get("x-client-id")
        if explicit:
            explicit = explicit.strip().lower()
            if explicit in HARNESS_CATALOG:
                return explicit

        ua = (request_headers.get("user-agent") or "").lower()
        if "claude-code" in ua or "claudecli" in ua:
            return "claude_code"
        if "cursor" in ua:
            return "cursor"
        if "codex" in ua:
            return "codex"
        if "opencode" in ua:
            return "opencode"
        if "gemini" in ua:
            return "gemini_cli"
        if "copilot" in ua:
            return "github_copilot"
        if "aider" in ua:
            return "aider"
        if "continue" in ua:
            return "continue"
        if "telegram" in ua:
            return "telegram"

        return None

    def normalize_request(self, harness_id: str, request: dict[str, Any]) -> dict[str, Any]:
        """Convert a harness-native request dict to the local-llm-server format."""
        spec = HARNESS_CATALOG.get(harness_id)
        if spec is None:
            return request

        normalized: dict[str, Any] = {
            "harness": harness_id,
            "harness_display": spec.display_name,
            "context_key": spec.context_key,
        }

        # Copy over common fields, preferring our mapping
        for field in ("messages", "model", "temperature", "max_tokens", "stream"):
            if field in request:
                normalized[field] = request[field]

        # Harness-specific normalizations
        if harness_id == "claude_code":
            normalized.setdefault("model", spec.default_model or "claude-sonnet-4-6")
        elif harness_id == "cursor":
            normalized.setdefault("model", spec.default_model or "nvidia/llama-3.3-nemotron-super-49b-v1")
        elif harness_id == "telegram":
            normalized.setdefault("model", spec.default_model or "nvidia/nemotron-3-super-120b-a12b")

        return normalized

    def model_hint(self, harness_id: str) -> str | None:
        """Return the recommended model for this harness."""
        spec = HARNESS_CATALOG.get(harness_id)
        return spec.default_model if spec else None

    def supports_feature(self, harness_id: str, feature: str) -> bool:
        """Check whether a harness supports a specific capability."""
        spec = HARNESS_CATALOG.get(harness_id)
        return feature in (spec.supports if spec else [])

    def as_dict(self) -> dict[str, Any]:
        return {
            "active_harnesses": [
                {
                    "harness_id": h.harness_id,
                    "display_name": h.display_name,
                    "supports": h.supports,
                    "is_active": h.is_active,
                }
                for h in self._active.values()
            ],
            "catalog_size": len(HARNESS_CATALOG),
            "detectable": True,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

_adapter: HarnessAdapter | None = None


def get_harness_adapter() -> HarnessAdapter:
    global _adapter
    if _adapter is None:
        _adapter = HarnessAdapter()
    return _adapter
