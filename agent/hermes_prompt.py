from __future__ import annotations

"""Hermes ChatML prompt format for reliable tool calling.

Implements the NousResearch Hermes-agent pattern: strict
``<|im_start|>...<|im_end|>`` ChatML format with embedded
``<tool_call>`` and ``<tool_response>`` tokens that dramatically
improves tool-use reliability on models fine-tuned with this format
(Qwen3-Coder and DeepSeek-R1 both respond to it).

Reference: https://github.com/NousResearch/hermes-agent
"""

import json
import logging
from typing import Any

log = logging.getLogger("qwen-agent")

# Sentinel markers for the ChatML format
_IM_START = "<|im_start|>"
_IM_END = "<|im_end|>"
_TOOL_CALL = "<tool_call>"
_TOOL_RESPONSE = "<tool_response>"


def build_chatml_system_prompt(tools: list[dict[str, Any]] | None = None) -> str:
    """Build the system prompt header with available tool definitions."""
    base = (
        "You are a helpful AI assistant with access to tools. "
        "When you need to use a tool, output the tool call in this format:\n\n"
        f"{_TOOL_CALL}\n"
        '{{"name": "<tool_name>", "arguments": {{...}}}}\n'
        f"{_IM_END}\n\n"
        "After the tool call, wait for the tool response before continuing."
    )

    if tools:
        tool_defs = json.dumps(tools, indent=2)
        base += f"\n\nAvailable tools:\n{tool_defs}"

    return base


def format_chatml_message(role: str, content: str) -> str:
    """Format a single message in ChatML format.

    Args:
        role: One of ``"system"``, ``"user"``, ``"assistant"``, ``"tool"``.
        content: The message content text.
    """
    return f"{_IM_START}{role}\n{content}{_IM_END}"


def format_tool_call(name: str, arguments: dict[str, Any]) -> str:
    """Format a tool call in Hermes ChatML format."""
    tool_json = json.dumps({"name": name, "arguments": arguments}, ensure_ascii=False)
    return f"{_TOOL_CALL}\n{tool_json}"


def format_tool_response(name: str, result: Any) -> str:
    """Format a tool response in Hermes ChatML format."""
    result_str = str(result) if not isinstance(result, str) else result
    return f"{_TOOL_RESPONSE}\n{name}: {result_str}"


def messages_to_chatml(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> str:
    """Convert OpenAI-format messages to a complete ChatML prompt string.

    The output can be sent directly to models fine-tuned on the Hermes
    ChatML format (Qwen3-Coder, DeepSeek-R1, Nemotron with ChatML support).

    Args:
        messages: List of ``{role, content}`` dicts in OpenAI format.
        tools: Optional tool/function definitions.

    Returns:
        Full ChatML-formatted prompt string ready for inference.
    """
    parts: list[str] = []

    # System prompt with tool definitions
    system_content = build_chatml_system_prompt(tools)
    parts.append(format_chatml_message("system", system_content))

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, list):
            # Handle multimodal content blocks — extract text
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        text_parts.append(
                            format_tool_call(
                                block.get("name", "unknown"),
                                block.get("input", {}),
                            )
                        )
                    elif block.get("type") == "tool_result":
                        text_parts.append(
                            format_tool_response(
                                block.get("tool_use_id", "unknown"),
                                block.get("content", ""),
                            )
                        )
            content = "\n".join(text_parts)

        parts.append(format_chatml_message(role, str(content)))

    # Append assistant start marker so the model knows to begin generation
    parts.append(f"{_IM_START}assistant\n")

    return "\n".join(parts)


def parse_tool_call_from_chatml(text: str) -> dict[str, Any] | None:
    """Try to extract a tool call from model output in ChatML format.

    Returns ``{name, arguments}`` dict or ``None`` if no tool call found.
    """
    import re as _re

    # Match <tool_call> followed by JSON until </im_end> or end of string
    pattern = rf"{re.escape(_TOOL_CALL)}\s*\n?(\{{.*?\}})(?:\s*{re.escape(_IM_END)}|$)"
    match = _re.search(pattern, text, _re.DOTALL)

    if not match:
        return None

    try:
        parsed = json.loads(match.group(1))
        if isinstance(parsed, dict) and "name" in parsed:
            return {
                "name": parsed["name"],
                "arguments": parsed.get("arguments", {}),
            }
    except (json.JSONDecodeError, TypeError):
        log.debug("hermes_prompt: failed to parse tool call JSON: %s", match.group(1)[:200])

    return None


def model_supports_chatml(model_name: str) -> bool:
    """Check if a model is known to support the Hermes ChatML format."""
    chatml_models = {
        "qwen", "qwen2", "qwen3", "deepseek", "nemotron",
        "hermes", "llama-3", "llama-3.1", "llama-3.2", "llama-3.3",
        "mistral", "mixtral",
    }
    lower = model_name.lower()
    return any(prefix in lower for prefix in chatml_models)
