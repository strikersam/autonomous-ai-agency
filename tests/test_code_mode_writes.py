"""Code Mode phase 6: programs propose writes; the Verifier and a human decide.

AGENT_CODE_MODE_WRITES_ENABLED (default off) lets a run_code program call
edit_file / write_file. The calls write nothing. Each becomes a proposal that,
after the program, must pass the write gate's checks and then a human approval
in the governance approval store. Unanswered approvals expire, and expiry is a denial.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from agent.code_mode import CodeModeError, callable_tools
from agent.loop import AgentRunner
from agent.write_gate import MAX_PROPOSALS, queue_proposal
from packages.config import settings
from packages.config.control_registry import get_control
from packages.governance.approvals import ApprovalStore, get_approval_store, reset_approval_store

PASS = {"status": "pass", "issues": [], "confidence": 0.9}
FAIL = {"status": "fail", "issues": ["not what the step asked for"], "confidence": 0.9}
EDIT = "result = tools.edit_file(path='app.py', old_string='x = 1', new_string='x = 2')"


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    reset_approval_store(ApprovalStore())
    monkeypatch.setattr(settings, "agent_code_mode_writes_raw", "true")
    monkeypatch.setattr(settings, "governance_auto_approve_raw", "false")
    monkeypatch.setattr(settings, "governance_approval_ttl_s", 5)
    monkeypatch.setattr("agent.code_mode.code_mode_active", lambda: True)
    yield
    reset_approval_store(None)


def _runner(tmp_path: Path) -> tuple[AgentRunner, Path]:
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    (root / "app.py").write_text("x = 1\n", encoding="utf-8")
    return AgentRunner(ollama_base="http://localhost:11434", workspace_root=root), root


def _drive(runner: AgentRunner, code: str, verdicts: list[dict[str, Any]], monkeypatch,
           decide: bool | None = None) -> tuple[dict[str, Any], list[str]]:
    """One step running *code*; *decide* approves/denies the first approval request (None: leave it)."""
    selections = iter([{"tool": "run_code", "args": {"code": code}}, {"tool": "finish", "args": {"reason": "done"}}])
    verifier = iter(verdicts)
    roles: list[str] = []

    async def fake_chat_json(self_arg: object, model: str, messages: list) -> dict[str, Any]:
        is_verify = str(messages[0].get("content", "")).startswith("Check syntax and logic")
        roles.append("verify" if is_verify else "select")
        return next(verifier) if is_verify else next(selections)

    async def reviewer() -> None:
        store = get_approval_store()
        for _ in range(200):
            pending = store.pending()
            if pending:
                store.resolve(pending[0]["approval_id"], approved=bool(decide), resolved_by="alice@example.com")
                return
            await asyncio.sleep(0.02)

    async def main() -> dict[str, Any]:
        task = asyncio.create_task(reviewer()) if decide is not None else None
        result = await runner._execute_step(
            goal="tidy app.py", step={"id": 1, "description": "edit app.py", "files": [], "type": "analyze"},
            requested_model=None,
        )
        if task:
            task.cancel()
        return result

    monkeypatch.setattr(AgentRunner, "_chat_json", fake_chat_json)
    return asyncio.run(main()), roles


def _base_prompt_allows_edit(monkeypatch) -> None:
    """The base tool prompt advertises edit_file; make sure run_code sees it."""
    from agent import prompts

    text = prompts.build_tool_prompt(goal="g", step={"description": "s"}, observations=[], remaining_calls=3)[0]["content"]
    assert "- edit_file(" in text


def test_writes_are_off_by_default_and_a_live_high_risk_control():
    control = get_control("AGENT_CODE_MODE_WRITES_ENABLED")
    assert control is not None and control.live is True and control.default == "false"


def test_platform_override_turns_writes_on(monkeypatch):
    """Rule 37: the admin-panel override takes effect on the live setting."""
    from packages.config import control_overrides

    try:
        control_overrides.apply_overrides({"AGENT_CODE_MODE_WRITES_ENABLED": "true"})
        assert settings.agent_code_mode_writes is True
        control_overrides.apply_overrides({"AGENT_CODE_MODE_WRITES_ENABLED": "false"})
        assert settings.agent_code_mode_writes is False
    finally:
        control_overrides.apply_overrides({})


def test_allow_list_only_grows_when_asked():
    prompt = "- read_file(path)\n- edit_file(path, old_string, new_string)\n- write_file(workspace_id, path, content)\n"
    assert set(callable_tools(prompt)) == {"read_file"}
    assert set(callable_tools(prompt, writes=True)) == {"read_file", "edit_file", "write_file"}


def test_switched_off_a_program_cannot_write(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "agent_code_mode_writes_raw", "false")
    runner, root = _runner(tmp_path)
    result, roles = _drive(runner, EDIT, [], monkeypatch)
    assert (root / "app.py").read_text() == "x = 1\n"
    assert "not callable from run_code" in str(result["observations"])
    assert get_approval_store().pending() == [] and "verify" not in roles


def test_approved_proposal_is_written_after_the_verifier_and_a_human(tmp_path, monkeypatch):
    _base_prompt_allows_edit(monkeypatch)
    runner, root = _runner(tmp_path)
    result, roles = _drive(runner, EDIT, [PASS], monkeypatch, decide=True)
    assert (root / "app.py").read_text() == "x = 2\n"
    assert "verify" in roles and "app.py" in result["changed_files"]
    assert "queued" in str(result["observations"])  # the program saw a receipt, not a write
    decided = get_approval_store().all()
    assert decided[0]["status"] == "approved" and decided[0]["action"] == "code_mode.edit_file"
    assert "x = 2" in decided[0]["arguments"]["diff"]


def test_denied_proposal_is_not_written(tmp_path, monkeypatch):
    runner, root = _runner(tmp_path)
    result, _ = _drive(runner, EDIT, [PASS], monkeypatch, decide=False)
    assert (root / "app.py").read_text() == "x = 1\n"
    assert "approval" in str(result["observations"]) and "denied" in str(result["observations"])


def test_unanswered_approval_expires_and_denies(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "governance_approval_ttl_s", 0.3)
    runner, root = _runner(tmp_path)
    result, _ = _drive(runner, EDIT, [PASS], monkeypatch)
    assert (root / "app.py").read_text() == "x = 1\n"
    assert "expired" in str(result["observations"])


def test_verifier_rejection_never_asks_a_human(tmp_path, monkeypatch):
    runner, root = _runner(tmp_path)
    _drive(runner, EDIT, [FAIL], monkeypatch)
    assert (root / "app.py").read_text() == "x = 1\n"
    assert get_approval_store().all() == []


def test_proposals_are_capped_per_program():
    queue: list[dict[str, Any]] = []
    for i in range(MAX_PROPOSALS):
        assert queue_proposal(queue, "write_file", {"path": f"f{i}.py", "content": ""})["status"] == "queued"
    with pytest.raises(CodeModeError, match="at most"):
        queue_proposal(queue, "write_file", {"path": "one_more.py", "content": ""})
