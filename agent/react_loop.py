from __future__ import annotations

"""Multi-Hop ReAct Loop for the agent execution phase (A2 roadmap item).

Implements the ReAct (Reason + Act) pattern where the model interleaves
reasoning steps with tool calls, accumulating a structured scratchpad across
tool invocations within a single step.

Reference: https://github.com/NousResearch/hermes-agent (ReAct pattern)
"""

import json
import logging
import time
from typing import Any

log = logging.getLogger("qwen-agent")


class ReactScratchpad:
    """Structured scratchpad that accumulates across tool calls within a step.

    Each entry records the model's thought, the action taken, and the
    observation received — forming a persistent reasoning trace.
    """

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []
        self._start_time: float = time.time()

    def record_thought(self, thought: str) -> None:
        """Record a reasoning step before taking action."""
        self.entries.append({
            "type": "thought",
            "content": thought,
            "timestamp": time.time() - self._start_time,
        })

    def record_action(self, tool: str, args: dict[str, Any]) -> None:
        """Record a tool call action."""
        self.entries.append({
            "type": "action",
            "tool": tool,
            "args": args,
            "timestamp": time.time() - self._start_time,
        })

    def record_observation(self, result: Any) -> None:
        """Record the result of a tool call."""
        result_str = str(result)
        self.entries.append({
            "type": "observation",
            "result": result_str[:2000],
            "timestamp": time.time() - self._start_time,
        })

    def to_prompt_context(self, max_entries: int = 8) -> str:
        """Format recent scratchpad entries as context for the next LLM call.

        Returns a compact string suitable for appending to the tool prompt.
        """
        recent = self.entries[-max_entries:]
        if not recent:
            return ""
        lines = ["[Reasoning trace so far]"]
        for entry in recent:
            t = entry["type"]
            if t == "thought":
                lines.append(f"  Thought: {entry['content']}")
            elif t == "action":
                lines.append(f"  Action: {entry['tool']}({json.dumps(entry['args'])})")
            elif t == "observation":
                obs = entry.get("result", "")
                lines.append(f"  Observation: {obs[:300]}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full scratchpad for persistence."""
        return {
            "entries": self.entries,
            "duration_ms": int((time.time() - self._start_time) * 1000),
        }

    def clear(self) -> None:
        """Reset the scratchpad for a new step."""
        self.entries.clear()
        self._start_time = time.time()


def build_react_prompt(
    *,
    goal: str,
    step: dict[str, Any],
    scratchpad: ReactScratchpad,
    tool_descriptions: str,
) -> str:
    """Build a ReAct-formatted prompt for the executor.

    Intended caller: WorkflowOrchestrator agents or custom sub-agents that
    prefer the ReAct (Thought → Action → Observation) format over the
    default JSON tool-call format used by AgentRunner._execute_step.

    The ReAct format interleaves reasoning, actions, and observations:
    Thought: <model reasons about what to do next>
    Action: <tool_name>(<args>)
    Observation: <result of tool call>
    ... (repeat until finished, then output Final Answer)

    Returns a system prompt string for the executor that instructs it
    to follow the ReAct pattern.
    """
    trace_context = scratchpad.to_prompt_context()

    return (
        f"You are executing ONE coding step using the ReAct (Reason + Act) pattern.\n\n"
        f"Goal: {goal}\n\n"
        f"Step: {json.dumps(step, indent=2)}\n\n"
        f"Available tools:\n{tool_descriptions}\n\n"
        f"{trace_context}\n\n"
        "Follow this exact pattern for each action:\n\n"
        "Thought: <your reasoning about what to do next>\n"
        "Action: <tool_name>(<json_args>)\n"
        "PAUSE\n\n"
        "After receiving the observation, continue with another Thought/Action/PAUSE cycle.\n"
        "When you have completed the step, output:\n\n"
        "Thought: I have completed the step.\n"
        "Final Answer: <summary of what was done>\n\n"
        "Rules:\n"
        "- Always produce a Thought before every Action.\n"
        "- One Action per response — wait for the observation.\n"
        "- Use exact tool names from the available tools list.\n"
        "- Only output Final Answer when the step is truly complete."
    )


def parse_react_response(text: str) -> dict[str, str] | None:
    """Parse a ReAct-format response into structured components.

    Intended caller: WorkflowOrchestrator agents or custom sub-agents that
    use ``build_react_prompt`` and need to parse the model's ReAct response.

    Returns ``{thought, action, tool, args, final}`` dict or ``None`` if
    the response cannot be parsed.
    """
    import re as _re

    result: dict[str, str] = {}

    # Extract Thought
    thought_match = _re.search(r"Thought:\s*(.+?)(?:\n|$)", text)
    if thought_match:
        result["thought"] = thought_match.group(1).strip()

    # Check for Final Answer
    final_match = _re.search(r"Final Answer:\s*(.+)", text, _re.DOTALL)
    if final_match:
        result["final"] = final_match.group(1).strip()
        return result

    # Extract Action — use greedy matching for args to handle nested parens/braces
    # Example: write_file({"path": "a.py", "content": "x = (1+2)"})
    action_match = _re.search(r"Action:\s*(.+?)\(([\s\S]*)\)", text)
    if action_match:
        tool_name = action_match.group(1).strip()
        args_raw = action_match.group(2).strip()
        result["action"] = action_match.group(0).strip()
        result["tool"] = tool_name
        try:
            # Try JSON parse first
            result["args"] = json.dumps(json.loads(args_raw))
        except (json.JSONDecodeError, ValueError):
            result["args"] = args_raw
        return result

    return result if result else None
