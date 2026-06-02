"""Memory middleware for automatic context injection into AI tool requests.

This middleware intercepts chat requests from various AI coding tools and automatically
injects relevant persistent memories into the context.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from agent.persistent_memory import MemoryCategory, MemoryScope, PersistentMemoryStore

log = logging.getLogger("qwen-agent")

# Tool detection patterns
TOOL_SIGNATURES = {
    "claude-code": ["claude-code", "claudecode", "claude_code"],
    "cursor": ["cursor", "cursor-editor"],
    "vscode": ["vscode", "visual-studio-code", "code"],
    "zed": ["zed", "zed-editor"],
    "continue": ["continue", "continue-dev"],
    "aider": ["aider"],
    "cline": ["cline"],
    "codex": ["codex", "openai-codex"],
}


class MemoryMiddleware:
    """Middleware for automatic memory loading and injection."""

    def __init__(self, memory_store: PersistentMemoryStore | None = None):
        self.memory_store = memory_store or PersistentMemoryStore()
        self.enabled = os.environ.get("MEMORY_AUTOLOAD_ENABLED", "true").lower() in ("true", "1", "yes")
        self.max_memories = int(os.environ.get("MEMORY_AUTOLOAD_MAX", "50"))
        log.info("MemoryMiddleware initialized: enabled=%s max=%d", self.enabled, self.max_memories)

    def detect_tool(self, headers: dict[str, str]) -> str | None:
        """Detect AI coding tool from request headers."""
        user_agent = headers.get("user-agent", "").lower()
        referer = headers.get("referer", "").lower()
        x_tool = headers.get("x-tool", "").lower()
        
        # Check explicit tool header first
        if x_tool:
            for tool, patterns in TOOL_SIGNATURES.items():
                if any(pattern in x_tool for pattern in patterns):
                    return tool
        
        # Check user agent
        for tool, patterns in TOOL_SIGNATURES.items():
            if any(pattern in user_agent for pattern in patterns):
                return tool
        
        # Check referer
        for tool, patterns in TOOL_SIGNATURES.items():
            if any(pattern in referer for pattern in patterns):
                return tool
        
        return None

    def extract_workspace_id(self, request_data: dict[str, Any]) -> str | None:
        """Extract workspace ID from request metadata."""
        # Check common metadata fields
        metadata = request_data.get("metadata", {})
        workspace = (
            metadata.get("workspace_id")
            or metadata.get("workspace")
            or metadata.get("project_id")
            or metadata.get("project")
        )
        if workspace:
            return str(workspace)
        
        # Try to extract from messages if they contain path info
        messages = request_data.get("messages", [])
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str) and "workspace:" in content.lower():
                # Try to parse workspace ID from content
                lines = content.split("\n")
                for line in lines:
                    if line.lower().startswith("workspace:"):
                        return line.split(":", 1)[1].strip()
        
        return None

    def inject_memories(
        self,
        messages: list[dict[str, str]],
        user_id: str,
        *,
        workspace_id: str | None = None,
        tool_name: str | None = None,
    ) -> list[dict[str, str]]:
        """Inject auto-loaded memories into the message context."""
        if not self.enabled:
            return messages
        
        # Auto-load relevant memories
        memories = self.memory_store.auto_load_memories(
            user_id=user_id,
            workspace_id=workspace_id,
            tool_name=tool_name,
            max_memories=self.max_memories,
        )
        
        if not memories:
            return messages
        
        # Build memory context message
        memory_sections = {
            "preferences": [],
            "context": [],
            "learning": [],
            "history": [],
        }
        
        # Categorize memories for better organization
        for key, value in memories.items():
            # Try to infer category from key prefix
            if key.startswith("pref_") or key.startswith("style_"):
                memory_sections["preferences"].append(f"- {key}: {value}")
            elif key.startswith("learned_") or key.startswith("correction_"):
                memory_sections["learning"].append(f"- {key}: {value}")
            elif key.startswith("history_") or key.startswith("decision_"):
                memory_sections["history"].append(f"- {key}: {value}")
            else:
                memory_sections["context"].append(f"- {key}: {value}")
        
        # Build formatted memory context
        memory_context_parts = ["# Auto-loaded Memory Context\n"]
        
        if memory_sections["preferences"]:
            memory_context_parts.append("## User Preferences")
            memory_context_parts.extend(memory_sections["preferences"])
            memory_context_parts.append("")
        
        if memory_sections["context"]:
            memory_context_parts.append("## Workspace Context")
            memory_context_parts.extend(memory_sections["context"])
            memory_context_parts.append("")
        
        if memory_sections["learning"]:
            memory_context_parts.append("## Learned Patterns")
            memory_context_parts.extend(memory_sections["learning"])
            memory_context_parts.append("")
        
        if memory_sections["history"]:
            memory_context_parts.append("## Historical Context")
            memory_sections["history"].extend(memory_sections["history"])
            memory_context_parts.append("")
        
        memory_context = "\n".join(memory_context_parts)
        
        # Inject memory context as system message or prepend to first user message
        enriched_messages = messages.copy()
        
        # Find system message or create one
        has_system_msg = any(msg.get("role") == "system" for msg in enriched_messages)
        
        if has_system_msg:
            # Append to existing system message
            for msg in enriched_messages:
                if msg.get("role") == "system":
                    msg["content"] = f"{msg['content']}\n\n{memory_context}"
                    break
        else:
            # Prepend new system message
            enriched_messages.insert(0, {
                "role": "system",
                "content": memory_context,
            })
        
        log.debug(
            "Injected %d memories into context for user=%s workspace=%s tool=%s",
            len(memories), user_id, workspace_id, tool_name
        )
        
        return enriched_messages

    def process_request(
        self,
        request_data: dict[str, Any],
        user_id: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Process incoming chat request and inject memories."""
        if not self.enabled:
            return request_data
        
        # Detect tool and workspace
        tool_name = self.detect_tool(headers)
        workspace_id = self.extract_workspace_id(request_data)
        
        # Get messages
        messages = request_data.get("messages", [])
        if not messages:
            return request_data
        
        # Inject memories
        enriched_messages = self.inject_memories(
            messages=messages,
            user_id=user_id,
            workspace_id=workspace_id,
            tool_name=tool_name,
        )
        
        # Return updated request
        enriched_request = request_data.copy()
        enriched_request["messages"] = enriched_messages
        
        # Add metadata about memory injection
        if "metadata" not in enriched_request:
            enriched_request["metadata"] = {}
        enriched_request["metadata"]["memory_injected"] = True
        enriched_request["metadata"]["detected_tool"] = tool_name
        enriched_request["metadata"]["workspace_id"] = workspace_id
        
        return enriched_request

    def save_from_response(
        self,
        response: dict[str, Any],
        user_id: str,
        *,
        workspace_id: str | None = None,
        tool_name: str | None = None,
    ) -> None:
        """Extract and save learnings from model responses."""
        if not self.enabled:
            return
        
        # Look for explicit memory save markers in response
        content = ""
        if "choices" in response:
            choices = response["choices"]
            if choices and "message" in choices[0]:
                content = choices[0]["message"].get("content", "")
        
        # Parse memory save markers: [MEMORY:key=value]
        import re
        memory_pattern = r'\[MEMORY:(\w+)=(.*?)\]'
        matches = re.findall(memory_pattern, content)
        
        for key, value in matches:
            try:
                self.memory_store.save(
                    user_id=user_id,
                    key=key,
                    value=value,
                    category=MemoryCategory.LEARNING,
                    scope=MemoryScope.WORKSPACE if workspace_id else MemoryScope.GLOBAL,
                    workspace_id=workspace_id,
                    tool_name=tool_name,
                    priority=7,  # Learned memories get high priority
                )
                log.debug("Saved learning from response: %s=%s", key, value)
            except Exception as exc:
                log.warning("Failed to save memory from response: %s", exc)


def create_memory_middleware() -> MemoryMiddleware:
    """Factory function to create memory middleware instance."""
    return MemoryMiddleware()
