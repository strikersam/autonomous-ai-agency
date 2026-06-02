"""
Harness Adapter — normalize API calls across different agent harnesses.

Inspired by ECC's cross-harness architecture:
https://github.com/affaan-m/ECC/blob/main/docs/architecture/cross-harness.md

Supports: Claude Code, Cursor, Codex, OpenCode, Gemini, Zed, GitHub Copilot
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional

log = logging.getLogger("harness_adapter")


class HarnessType(str, Enum):
    """Supported agent harnesses"""

    CLAUDE_CODE = "claude_code"
    CURSOR = "cursor"
    CODEX = "codex"
    OPENCODE = "opencode"
    GEMINI = "gemini"
    ZED = "zed"
    GITHUB_COPILOT = "github_copilot"


class HarnessCapabilities:
    """Declare capabilities per harness"""

    HARNESS_FEATURES = {
        HarnessType.CLAUDE_CODE: {
            "supports_streaming": True,
            "supports_context_file": True,
            "max_context_bytes": 50 * 1024 * 1024,  # 50MB
            "model_preference": "reasoning",  # prefers deepseek-r1
            "context_source": "workspace_tree",
        },
        HarnessType.CURSOR: {
            "supports_streaming": True,
            "supports_context_file": True,
            "max_context_bytes": 25 * 1024 * 1024,  # 25MB
            "model_preference": "speed",  # prefers qwen3-coder
            "context_source": "editor_open_tabs",
        },
        HarnessType.CODEX: {
            "supports_streaming": False,
            "supports_context_file": True,
            "max_context_bytes": 10 * 1024 * 1024,  # 10MB
            "model_preference": "completion",
            "context_source": "current_file",
        },
        HarnessType.OPENCODE: {
            "supports_streaming": True,
            "supports_context_file": False,
            "max_context_bytes": 30 * 1024 * 1024,  # 30MB
            "model_preference": "speed",
            "context_source": "buffer",
        },
        HarnessType.GEMINI: {
            "supports_streaming": True,
            "supports_context_file": True,
            "max_context_bytes": 40 * 1024 * 1024,  # 40MB
            "model_preference": "balanced",
            "context_source": "project_root",
        },
        HarnessType.ZED: {
            "supports_streaming": True,
            "supports_context_file": True,
            "max_context_bytes": 20 * 1024 * 1024,  # 20MB
            "model_preference": "speed",
            "context_source": "editor_buffer",
        },
        HarnessType.GITHUB_COPILOT: {
            "supports_streaming": True,
            "supports_context_file": False,
            "max_context_bytes": 35 * 1024 * 1024,  # 35MB
            "model_preference": "balanced",
            "context_source": "vscode_context",
        },
    }


class HarnessAdapter:
    """
    Normalize API differences across harnesses.

    Each harness has different:
    - Request/response formats
    - Context retrieval mechanisms
    - Streaming capabilities
    - Model routing preferences
    """

    def __init__(self, harness_type: str | HarnessType):
        if isinstance(harness_type, str):
            try:
                self.harness = HarnessType(harness_type)
            except ValueError:
                log.warning(f"Unknown harness: {harness_type}, defaulting to claude_code")
                self.harness = HarnessType.CLAUDE_CODE
        else:
            self.harness = harness_type

        self.capabilities = HarnessCapabilities.HARNESS_FEATURES.get(
            self.harness,
            HarnessCapabilities.HARNESS_FEATURES[HarnessType.CLAUDE_CODE],
        )

    def normalize_request(self, request: dict) -> dict:
        """Convert harness-native request to local-llm-server format"""
        if self.harness == HarnessType.CLAUDE_CODE:
            return self._normalize_claude_code(request)
        elif self.harness == HarnessType.CURSOR:
            return self._normalize_cursor(request)
        elif self.harness == HarnessType.CODEX:
            return self._normalize_codex(request)
        else:
            log.warning(f"No normalization for {self.harness}, passing through")
            return request

    def denormalize_response(self, response: dict) -> dict:
        """Convert local-llm-server response to harness-native format"""
        if self.harness == HarnessType.CLAUDE_CODE:
            return self._denormalize_claude_code(response)
        elif self.harness == HarnessType.CURSOR:
            return self._denormalize_cursor(response)
        else:
            return response

    def get_model_preference(self) -> str:
        """Get preferred model type for this harness"""
        return self.capabilities.get("model_preference", "balanced")

    def get_max_context(self) -> int:
        """Get maximum context size for this harness"""
        return self.capabilities.get("max_context_bytes", 10 * 1024 * 1024)

    def supports_streaming(self) -> bool:
        """Check if harness supports streaming responses"""
        return self.capabilities.get("supports_streaming", False)

    # ===== Claude Code Normalization =====

    def _normalize_claude_code(self, request: dict) -> dict:
        """Claude Code sends workspace context, minimal transformation needed"""
        return {
            **request,
            "harness": self.harness.value,
            "context_type": "workspace",
        }

    def _denormalize_claude_code(self, response: dict) -> dict:
        """Claude Code expects streaming delta format"""
        return response

    # ===== Cursor Normalization =====

    def _normalize_cursor(self, request: dict) -> dict:
        """Cursor uses active editor tabs as context"""
        return {
            **request,
            "harness": self.harness.value,
            "context_type": "editor_tabs",
            "context": request.get("context", {}).get("active_tabs"),
        }

    def _denormalize_cursor(self, response: dict) -> dict:
        """Cursor expects completion format"""
        return response

    # ===== Codex Normalization =====

    def _normalize_codex(self, request: dict) -> dict:
        """Codex uses current file as context"""
        return {
            **request,
            "harness": self.harness.value,
            "context_type": "current_file",
            "stream": False,  # Codex doesn't support streaming
            "streaming": False,  # Codex doesn't support streaming
        }

    def _denormalize_codex(self, response: dict) -> dict:
        """Codex expects completion format"""
        return response


def detect_harness() -> HarnessType:
    """
    Attempt to detect active harness from environment.

    Checks:
    - VSCODE_PID (Claude Code, Cursor, GitHub Copilot in VS Code)
    - ZED_SOCKET (Zed IDE)
    - GEMINI_SESSION_ID (Gemini IDE)
    - CURSOR_SESSION_ID (Cursor)
    """
    import os

    if os.getenv("CURSOR_SESSION_ID"):
        return HarnessType.CURSOR
    if os.getenv("ZED_SOCKET"):
        return HarnessType.ZED
    if os.getenv("GEMINI_SESSION_ID"):
        return HarnessType.GEMINI
    if os.getenv("VSCODE_PID"):
        # Could be Claude Code, GitHub Copilot, or others in VS Code
        return HarnessType.CLAUDE_CODE

    # Default to Claude Code
    log.info("Could not detect harness, defaulting to claude_code")
    return HarnessType.CLAUDE_CODE
# refresh diff for review resolution
