"""The durable session log persists payloads verbatim; tool args and results must be scrubbed first."""
from __future__ import annotations

import asyncio
from typing import Any

from agent.loop import AgentRunner

SECRET = "AKIA" + "Q" * 16


class _Store:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, Any]]] = []

    def append_event(self, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((session_id, event_type, payload))


def _runner(tmp_path) -> tuple[AgentRunner, _Store]:
    store = _Store()
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=tmp_path, session_store=store)
    runner._current_session_id = "s1"
    return runner, store


def test_tool_args_and_results_are_scrubbed_before_persisting(tmp_path):
    (tmp_path / "cfg.py").write_text(f"KEY = '{SECRET}'\n" + "x" * 5000, encoding="utf-8")
    runner, store = _runner(tmp_path)
    asyncio.run(runner._run_tool("write_file", {"path": "new.py", "content": f"K = '{SECRET}'\n"}))
    asyncio.run(runner._run_tool("read_file", {"path": "cfg.py"}))
    kinds = [kind for _, kind, _ in store.events]
    assert kinds.count("tool_call") == 2 and kinds.count("tool_result") == 2
    assert SECRET not in repr(store.events)
    assert all(len(repr(p)) < 3000 for _, _, p in store.events)  # file bodies are truncated
    assert store.events[0][2]["tool"] == "write_file" and store.events[0][2]["args"]["path"] == "new.py"


def test_other_event_types_pass_through_unchanged(tmp_path):
    runner, store = _runner(tmp_path)
    payload = {"tokens_used": 42, "summary": "done"}
    runner._log_event("s1", "step_complete", payload)
    assert store.events == [("s1", "step_complete", payload)]
