"""A stub file named after the task is never an approved fix (production 2026-10-15).

The judge approved ``tasks/task_4a47fb5d8ac50c34.py``, a "minimal valid task
file" an agent wrote to make a timeout go away.
"""

from __future__ import annotations

from agent.loop import AgentRunner
from agent.pr_gate import placeholder_files


def test_files_named_after_a_task_id_are_placeholders():
    assert placeholder_files(["tasks/task_4a47fb5d8ac50c34.py", "agent/loop.py"]) == [
        "tasks/task_4a47fb5d8ac50c34.py"
    ]
    assert placeholder_files(["./task_76a911b967ba6395.json"]) == ["./task_76a911b967ba6395.json"]
    assert placeholder_files(["tasks/task_service.py", "tests/test_task_store.py"]) == []


def test_an_approval_of_a_placeholder_is_overridden():
    judge = {"verdict": "APPROVED", "security": "PASS", "correctness": "PASS", "notes": "fine"}
    steps = [{"status": "applied", "changed_files": ["tasks/task_4a47fb5d8ac50c34.py"]}]
    out = AgentRunner._reject_placeholders(judge, steps)
    assert out["verdict"] == "REJECTED" and out["correctness"] == "FAIL"
    assert "tasks/task_4a47fb5d8ac50c34.py" in out["notes"]


def test_a_real_change_keeps_its_verdict():
    judge = {"verdict": "APPROVED", "notes": "fine"}
    steps = [{"status": "applied", "changed_files": ["agent/loop.py"]}]
    assert AgentRunner._reject_placeholders(judge, steps) is judge


def test_the_judge_is_told_to_reject_stubs():
    import inspect

    from agent import loop

    assert "placeholder" in inspect.getsource(loop.AgentRunner).split("You are a code-review judge")[1][:1500]
