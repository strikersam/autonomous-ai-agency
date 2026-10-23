"""Tool-loop writes pass the Verifier before they touch disk (CLAUDE.md rule 16).

The executor's tool loop offers edit_file / write_file / apply_diff. They used to
go straight to ``_run_tool`` and write, skipping the syntax, safety and Verifier
checks the step's main edit path runs first. agent/write_gate.py now applies them
only after a ``pass``.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from agent.loop import AgentRunner
from agent.write_gate import proposed_content

PASS = {"status": "pass", "issues": [], "confidence": 0.9}
FAIL = {"status": "fail", "issues": ["changes behaviour nobody asked for"], "confidence": 0.9}


def _runner(tmp_path: Path) -> tuple[AgentRunner, Path]:
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    (root / "app.py").write_text("x = 1\n", encoding="utf-8")
    return AgentRunner(ollama_base="http://localhost:11434", workspace_root=root), root


def _drive(runner: AgentRunner, tool: str, args: dict[str, Any], verdicts: list[dict[str, Any]],
           monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], list[str]]:
    """One step: the executor picks *tool*, the Verifier answers from *verdicts*, then finish."""
    selections = iter([{"tool": tool, "args": args}, {"tool": "finish", "args": {"reason": "done"}}])
    verifier = iter(verdicts)
    roles: list[str] = []

    async def fake_chat_json(self_arg: object, model: str, messages: list) -> dict[str, Any]:
        is_verify = str(messages[0].get("content", "")).startswith("Check syntax and logic")
        roles.append("verify" if is_verify else "select")
        return next(verifier) if is_verify else next(selections)

    monkeypatch.setattr(AgentRunner, "_chat_json", fake_chat_json)
    result = asyncio.run(runner._execute_step(
        goal="tidy app.py",
        step={"id": 1, "description": "edit app.py", "files": [], "type": "analyze"},
        requested_model=None,
    ))
    return result, roles


def test_rejected_edit_is_never_written(tmp_path, monkeypatch):
    runner, root = _runner(tmp_path)
    result, roles = _drive(runner, "edit_file", {"path": "app.py", "old_string": "x = 1", "new_string": "x = 2"},
                           [FAIL], monkeypatch)
    assert (root / "app.py").read_text() == "x = 1\n"
    assert "verify" in roles
    observed = [o["result"] for o in result["observations"] if o.get("tool") == "edit_file"]
    assert "not applied" in str(observed[0]) and "changes behaviour" in str(observed[0])
    assert "app.py" not in result["changed_files"]


def test_passing_edit_is_written_and_tracked_for_the_commit(tmp_path, monkeypatch):
    runner, root = _runner(tmp_path)
    result, _ = _drive(runner, "edit_file", {"path": "app.py", "old_string": "x = 1", "new_string": "x = 2"},
                       [PASS], monkeypatch)
    assert (root / "app.py").read_text() == "x = 2\n"
    assert "app.py" in result["changed_files"]  # rule 20: _commit_step commits changed_files


def test_syntax_error_is_refused_without_asking_the_verifier(tmp_path, monkeypatch):
    runner, root = _runner(tmp_path)
    result, roles = _drive(runner, "write_file", {"path": "app.py", "content": "def broken(:\n"}, [], monkeypatch)
    assert (root / "app.py").read_text() == "x = 1\n"
    assert "verify" not in roles
    assert "syntax" in str(result["observations"]).lower()


def test_unusable_verifier_reply_counts_as_a_refusal(tmp_path, monkeypatch):
    runner, root = _runner(tmp_path)
    _drive(runner, "apply_diff", {"path": "new.py", "new_content": "y = 3\n"}, [{"nonsense": True}], monkeypatch)
    assert not (root / "new.py").exists()


def test_proposed_content_previews_without_writing():
    assert proposed_content("edit_file", {"old_string": "a", "new_string": "b"}, "a a") == ("b a", "")
    assert proposed_content("edit_file", {"old_string": "zz", "new_string": "b"}, "a")[0] is None
    assert proposed_content("write_file", {"content": "c"}, "old") == ("c", "")
    assert proposed_content("apply_diff", {}, "old")[0] is None


def test_large_file_edit_is_previewed_against_the_whole_file(tmp_path, monkeypatch):
    """Codex P2 on #1823: read_file caps at 12,000 chars; an edit past that was refused."""
    runner, root = _runner(tmp_path)
    body = "# filler\n" * 3000 + "x = 1\n"
    (root / "app.py").write_text(body, encoding="utf-8")
    _drive(runner, "edit_file", {"path": "app.py", "old_string": "x = 1", "new_string": "x = 2"}, [PASS], monkeypatch)
    assert (root / "app.py").read_text().endswith("x = 2\n")


def test_unreadable_file_refuses_the_write_instead_of_using_a_blank_baseline(tmp_path):
    """Codex P1/P2 on #1823: a denied or failed read must not become ''."""
    from agent.write_gate import PreviewUnavailable, _current_text

    class Runner:
        def __init__(self, reply):
            self.reply = reply

        async def _dispatch_tool(self, tool, args):
            if isinstance(self.reply, Exception):
                raise self.reply
            return self.reply

    for reply in ("[governance] deny: reads of secrets/ (rule r)", "[tool error: sandbox unreachable]", RuntimeError("boom")):
        with pytest.raises(PreviewUnavailable):
            asyncio.run(_current_text(Runner(reply), "app.py"))
    assert asyncio.run(_current_text(Runner(FileNotFoundError("x")), "new.py")) == ""


def test_denied_read_never_reaches_the_verifier(tmp_path, monkeypatch):
    runner, root = _runner(tmp_path)

    async def deny(self_arg, tool, args, **kwargs):
        if tool == "read_file":
            return "[governance] deny: read of app.py (rule r)"
        raise AssertionError("nothing else may be dispatched")

    monkeypatch.setattr(AgentRunner, "_dispatch_tool", deny)
    result, roles = _drive(runner, "write_file", {"path": "app.py", "content": "x = 9\n"}, [], monkeypatch)
    assert (root / "app.py").read_text() == "x = 1\n" and "verify" not in roles
    assert "could not be read" in str(result["observations"])


def test_sandbox_write_uses_write_file_with_the_verified_bytes(tmp_path, monkeypatch):
    """Codex P2 on #1823: edit_file through the registry would hit the host copy, not the sandbox."""
    from agent.write_gate import gated_write

    calls: list[tuple[str, dict[str, Any]]] = []

    class SandboxRunner:
        _mcp = object()

        async def _dispatch_tool(self, tool, args):
            return "x = 1\n"

        def _local_syntax_check(self, path, content):
            return []

        def _local_safety_check(self, path, content):
            return []

        async def _chat_json(self, model, messages):
            return PASS

        async def _run_tool(self, tool, args, **kwargs):
            calls.append((tool, args))
            return {"path": args["path"], "bytes": len(args["content"])}

    outcome = asyncio.run(gated_write(
        SandboxRunner(), "edit_file", {"path": "app.py", "old_string": "x = 1", "new_string": "x = 2"},
        goal="g", step={"id": 1, "description": "d"}, verifier_model="m", user_id=None, memory_store=None,
    ))
    assert calls == [("write_file", {"path": "app.py", "content": "x = 2\n"})] and outcome.applied_path == "app.py"
