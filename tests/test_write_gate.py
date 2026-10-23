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


class _Sandbox:
    def __init__(self, files: dict[str, str], fail_read: str | None = None):
        self.files, self.fail_read, self.calls = files, fail_read, []

    async def call_tool(self, name, args):
        self.calls.append((name, dict(args)))
        if name == "read_file":
            from agent.mcp_client import MCPFileNotFoundError, MCPUnavailableError

            if self.fail_read:
                raise MCPUnavailableError(self.fail_read)
            if args["path"] not in self.files:
                raise MCPFileNotFoundError(f"read_file({args['path']}): file not found")
            return self.files[args["path"]]
        if name == "write_file":
            self.files[args["path"]] = args["content"]
            return "ok"
        raise AssertionError(name)


class _SandboxRunner:
    def __init__(self, sandbox):
        self._mcp = sandbox
        self.host_reads = 0
        self.events: list[tuple[str, dict[str, Any]]] = []

    def _log_event(self, session_id, kind, payload):
        self.events.append((kind, payload))

    async def _dispatch_tool(self, tool, args):
        self.host_reads += 1
        return "HOST COPY\n"

    def _local_syntax_check(self, path, content):
        return []

    def _local_safety_check(self, path, content):
        return []

    async def _chat_json(self, model, messages):
        return PASS

    async def _run_tool(self, tool, args, **kwargs):
        raise AssertionError("a sandbox write must not go through the host dispatch")


def _gate(runner, tool, args):
    from agent.write_gate import gated_write

    return asyncio.run(gated_write(runner, tool, args, goal="g", step={"id": 1, "description": "d"},
                                   verifier_model="m", user_id=None, memory_store=None))


def test_sandbox_write_uses_the_sandbox_baseline_and_writes_the_verified_bytes():
    """Codex P2 on #1823/#1824: baseline and write both stay in the sandbox."""
    box = _Sandbox({"app.py": "x = 1\n"})
    runner = _SandboxRunner(box)
    outcome = _gate(runner, "edit_file", {"path": "app.py", "old_string": "x = 1", "new_string": "x = 2"})
    assert box.files["app.py"] == "x = 2\n" and outcome.applied_path == "app.py"
    assert runner.host_reads == 0  # the host copy is never consulted


def test_sandbox_read_failure_refuses_instead_of_using_the_host_copy():
    box = _Sandbox({"app.py": "x = 1\n"}, fail_read="read_file(app.py) failed: connection reset")
    runner = _SandboxRunner(box)
    outcome = _gate(runner, "write_file", {"path": "app.py", "content": "x = 9\n"})
    assert box.files["app.py"] == "x = 1\n" and outcome.applied_path is None
    assert "could not be read" in str(outcome.result) and runner.host_reads == 0


def test_sandbox_new_file_counts_as_empty_and_is_created():
    box = _Sandbox({})
    _gate(_SandboxRunner(box), "write_file", {"path": "new.py", "content": "y = 1\n"})
    assert box.files["new.py"] == "y = 1\n"


def test_sandbox_write_is_governed_as_the_requested_tool(monkeypatch):
    """Codex P1 on #1824: a policy denying edit_file must not be dodged by writing via write_file."""
    from packages.governance.policy import PolicyEngine, reset_policy_engine

    monkeypatch.setattr("packages.governance.enforcement.governance_enabled", lambda: True)
    reset_policy_engine(PolicyEngine({"mode": "enforce", "baseline": {"tool": {"deny": ["edit_file"]}}}))
    try:
        box = _Sandbox({"app.py": "x = 1\n"})
        outcome = _gate(_SandboxRunner(box), "edit_file", {"path": "app.py", "old_string": "x = 1", "new_string": "x = 2"})
    finally:
        reset_policy_engine(None)
    assert box.files["app.py"] == "x = 1\n" and outcome.applied_path is None
    assert "deny" in str(outcome.result) and ("write_file", {"path": "app.py", "content": "x = 2\n"}) not in box.calls


@pytest.mark.parametrize("message", [
    "read_file(not found/a.py) failed: Permission denied",  # the path itself says "not found"
    "read_file(a.py) failed: Sandbox abc not found",          # the sandbox is gone
    "read_file(a.py) failed: bash: command not found",
])
def test_only_a_typed_not_found_counts_as_a_new_file(message):
    """Verifier FAIL on #1824: a substring match on the message turned failures into blank baselines."""
    box = _Sandbox({"not found/a.py": "x = 1\n", "a.py": "x = 1\n"}, fail_read=message)
    outcome = _gate(_SandboxRunner(box), "write_file", {"path": "a.py", "content": "x = 9\n"})
    assert outcome.applied_path is None and "could not be read" in str(outcome.result)


def test_e2b_read_maps_only_a_missing_file_to_not_found():
    from agent.mcp_client import MCPFileNotFoundError, MCPUnavailableError
    from services.e2b_sandbox import E2BSandboxSession

    class FileNotFoundException(Exception):  # the E2B SDK's class name
        pass

    class Files:
        def __init__(self, exc):
            self.exc = exc

        async def read(self, path):
            raise self.exc

    class Box:
        def __init__(self, exc):
            self.files = Files(exc)

    session = object.__new__(E2BSandboxSession)
    with pytest.raises(MCPFileNotFoundError):
        asyncio.run(session._read_file(Box(FileNotFoundException("missing")), {"path": "a.py"}))
    with pytest.raises(MCPUnavailableError) as other:
        asyncio.run(session._read_file(Box(RuntimeError("Sandbox abc not found")), {"path": "a.py"}))
    assert not isinstance(other.value, FileNotFoundError)


def test_sandbox_write_appears_in_the_session_tool_log():
    """Codex P2 on #1824: the direct sandbox write must still emit tool_call/tool_result."""
    box = _Sandbox({"app.py": "x = 1\n"})
    runner = _SandboxRunner(box)
    _gate(runner, "edit_file", {"path": "app.py", "old_string": "x = 1", "new_string": "x = 2"})
    kinds = [(k, p["tool"]) for k, p in runner.events]
    assert ("tool_call", "edit_file") in kinds and ("tool_result", "edit_file") in kinds


def test_review_chunks_survive_the_scrubber_whole():
    """Verifier FAIL on #1824: redaction lengthened 1,800-char chunks past the 2,000 cut."""
    from agent.write_gate import review_chunks
    from packages.governance.audit import scrub

    diff = "".join(f"+postgres://u:p{i}@h/db\n" for i in range(300)) + "+" + "a" * 9000 + "\n"
    chunks = review_chunks(diff)
    scrubbed = [scrub({"v": c})["v"] for c in chunks]
    assert "".join(chunks) == diff and all(len(c) <= 2000 and "[truncated" not in c for c in scrubbed)


def test_read_limit_ignores_bad_max_chars():
    from agent.loop import _read_limit

    assert [_read_limit(v) for v in (None, "abc", -5, 0, "40")] == [12000, 12000, 12000, 12000, 40]
