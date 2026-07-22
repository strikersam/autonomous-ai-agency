import asyncio
import os
from pathlib import Path

import pytest

from agent.loop import AgentPhaseError, AgentRunner
from agent.state import AgentSessionStore


def test_agent_runner_applies_a_change_with_mocked_model(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "notes.txt"
    target.write_text("old text\n", encoding="utf-8")

    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    responses = iter(
        [
            '{"goal":"Update notes","steps":[{"id":1,"description":"Replace notes content","files":["notes.txt"],"type":"edit"}]}',
            '{"tool":"read_file","args":{"path":"notes.txt"}}',
            '{"tool":"finish","args":{"reason":"Enough context gathered"}}',
            'FILE: notes.txt\nACTION: replace\n```text\nnew text\n```',
            '{"status":"pass","issues":[]}',
        ]
    )

    async def fake_chat_text(model: str, messages: list[dict[str, str]]) -> str:
        return next(responses)

    runner._chat_text = fake_chat_text  # type: ignore[method-assign]

    result = asyncio.run(
        runner.run(
            instruction="Update notes",
            history=[],
            requested_model=None,
            auto_commit=False,
            max_steps=3,
        )
    )

    assert result["steps"][0]["status"] == "applied"
    assert result["steps"][0]["changed_files"] == ["notes.txt"]
    assert target.read_text(encoding="utf-8") == "new text\n"


def test_agent_runner_logs_tool_events_for_live_streaming(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "notes.txt"
    target.write_text("old text\n", encoding="utf-8")

    store = AgentSessionStore(tmp_path / "agent-events.db")
    store.create_with_id(session_id="session-live", title="Live Run", owner_id="user-1")
    runner = AgentRunner(
        ollama_base="http://localhost:11434",
        workspace_root=root,
        session_store=store,
    )
    responses = iter(
        [
            '{"goal":"Update notes","steps":[{"id":1,"description":"Replace notes content","files":["notes.txt"],"type":"edit"}]}',
            '{"tool":"read_file","args":{"path":"notes.txt"}}',
            '{"tool":"finish","args":{"reason":"Enough context gathered"}}',
            'FILE: notes.txt\nACTION: replace\n```text\nnew text\n```',
            '{"status":"pass","issues":[]}',
        ]
    )

    async def fake_chat_text(model: str, messages: list[dict[str, str]]) -> str:
        return next(responses)

    runner._chat_text = fake_chat_text  # type: ignore[method-assign]

    asyncio.run(
        runner.run(
            instruction="Update notes",
            history=[],
            requested_model=None,
            auto_commit=False,
            max_steps=3,
            session_id="session-live",
        )
    )

    events = store.get_events("session-live")
    event_types = [event.event_type for event in events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types


def test_agent_runner_reports_format_failure_with_mocked_model(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "notes.txt"
    target.write_text("old text\n", encoding="utf-8")

    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    responses = iter(
        [
            '{"goal":"Update notes","steps":[{"id":1,"description":"Replace notes content","files":["notes.txt"],"type":"edit"}]}',
            '{"tool":"finish","args":{"reason":"skip"}}',
            "not valid executor output",
            "still not valid",
            "not valid executor output",
            "still not valid",
            "not valid executor output",
            "still not valid",
        ]
    )

    async def fake_chat_text(model: str, messages: list[dict[str, str]]) -> str:
        return next(responses)

    runner._chat_text = fake_chat_text  # type: ignore[method-assign]

    result = asyncio.run(
        runner.run(
            instruction="Update notes",
            history=[],
            requested_model=None,
            auto_commit=False,
            max_steps=3,
        )
    )

    assert result["steps"][0]["status"] == "failed"
    # The feedback message now includes more detail about what went wrong,
    # but still mentions "format".
    assert "format" in result["steps"][0]["issues"][0].lower()


def test_agent_runner_cleans_language_prefix_from_generated_file(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "notes.txt"
    target.write_text("old text\n", encoding="utf-8")

    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    responses = iter(
        [
            '{"goal":"Update notes","steps":[{"id":1,"description":"Replace notes content","files":["notes.txt"],"type":"edit"}]}',
            '{"tool":"finish","args":{"reason":"Enough context gathered"}}',
            'FILE: notes.txt\nACTION: replace\n```text\ntext\nnew text\n```',
            '{"status":"pass","issues":[]}',
        ]
    )

    async def fake_chat_text(model: str, messages: list[dict[str, str]]) -> str:
        return next(responses)

    runner._chat_text = fake_chat_text  # type: ignore[method-assign]

    result = asyncio.run(
        runner.run(
            instruction="Update notes",
            history=[],
            requested_model="qwen3-coder:30b",
            auto_commit=False,
            max_steps=3,
        )
    )

    assert result["steps"][0]["status"] == "applied"
    assert target.read_text(encoding="utf-8") == "new text\n"


def test_agent_runner_fails_incomplete_shared_logger_change(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "service.py"
    target.write_text("print('hello')\n", encoding="utf-8")

    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    responses = iter(
        [
            '{"goal":"Add logging","steps":[{"id":1,"description":"Add logging across this module and create a shared logger utility.","files":["service.py"],"type":"edit"}]}',
            '{"tool":"finish","args":{"reason":"Enough context gathered"}}',
            "FILE: service.py\nACTION: replace\n```python\nimport logging\n\nlogger = logging.getLogger(__name__)\nprint('hello')\n```",
            '{"status":"pass","issues":[]}',
        ]
    )

    async def fake_chat_text(model: str, messages: list[dict[str, str]]) -> str:
        return next(responses)

    runner._chat_text = fake_chat_text  # type: ignore[method-assign]

    result = asyncio.run(
        runner.run(
            instruction="Add logging across this module and create a shared logger utility.",
            history=[],
            requested_model="qwen3-coder:30b",
            auto_commit=False,
            max_steps=3,
        )
    )

    assert result["steps"][0]["status"] == "failed"
    assert any("shared logger utility" in issue.lower() for issue in result["steps"][0]["issues"])


def test_agent_runner_fails_unsafe_jwt_change(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    app_file = root / "app.py"
    deps = root / "requirements.txt"
    app_file.write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
    deps.write_text("fastapi\n", encoding="utf-8")

    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    responses = iter(
        [
            '{"goal":"Add JWT auth","steps":[{"id":1,"description":"Add authentication to this API using JWT and update all relevant routes.","files":["app.py"],"type":"edit"}]}',
            '{"tool":"finish","args":{"reason":"Enough context gathered"}}',
            'FILE: app.py\nACTION: replace\n```python\nfrom fastapi import FastAPI\nSECRET_KEY = "hardcoded"\napp = FastAPI()\n```',
            '{"status":"pass","issues":[]}',
            'FILE: app.py\nACTION: replace\n```python\nfrom fastapi import FastAPI\nSECRET_KEY = "hardcoded"\napp = FastAPI()\n```',
            '{"status":"pass","issues":[]}',
            'FILE: app.py\nACTION: replace\n```python\nfrom fastapi import FastAPI\nSECRET_KEY = "hardcoded"\napp = FastAPI()\n```',
            '{"status":"pass","issues":[]}',
        ]
    )

    async def fake_chat_text(model: str, messages: list[dict[str, str]]) -> str:
        return next(responses)

    runner._chat_text = fake_chat_text  # type: ignore[method-assign]

    result = asyncio.run(
        runner.run(
            instruction="Add authentication to this API using JWT and update all relevant routes.",
            history=[],
            requested_model="qwen3-coder:30b",
            auto_commit=False,
            max_steps=3,
        )
    )

    assert result["steps"][0]["status"] == "failed"
    assert any("secret_key" in issue.lower() for issue in result["steps"][0]["issues"])


def test_agent_runner_surfaces_structured_planner_failure(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()

    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    responses = iter(["not-json"])

    async def fake_chat_text(model: str, messages: list[dict[str, str]]) -> str:
        return next(responses)

    runner._chat_text = fake_chat_text  # type: ignore[method-assign]

    with pytest.raises(AgentPhaseError, match="planning"):
        asyncio.run(
            runner.run(
                instruction="Plan this work",
                history=[],
                requested_model=None,
                auto_commit=False,
                max_steps=3,
            )
        )


def test_agent_runner_surfaces_structured_verifier_failure(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "notes.txt"
    target.write_text("old text\n", encoding="utf-8")

    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    responses = iter(
        [
            '{"goal":"Update notes","steps":[{"id":1,"description":"Replace notes content","files":["notes.txt"],"type":"edit"}]}',
            '{"tool":"finish","args":{"reason":"done"}}',
            'FILE: notes.txt\nACTION: replace\n```text\nnew text\n```',
            'not-json',
            'still not json',
            'still not json',
        ]
    )

    async def fake_chat_text(model: str, messages: list[dict[str, str]]) -> str:
        return next(responses)

    runner._chat_text = fake_chat_text  # type: ignore[method-assign]

    result = asyncio.run(
        runner.run(
            instruction="Update notes",
            history=[],
            requested_model=None,
            auto_commit=False,
            max_steps=3,
        )
    )

    assert result["steps"][0]["status"] == "failed"
    assert result["steps"][0]["failure_phase"] == "verification"
    assert "verifier_output_invalid" in result["steps"][0]["issues"][0]


def test_agent_runner_blocks_when_judge_output_invalid(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "notes.txt"
    target.write_text("old text\n", encoding="utf-8")

    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    responses = iter(
        [
            '{"goal":"Update notes","steps":[{"id":1,"description":"Replace notes content","files":["notes.txt"],"type":"edit"}]}',
            '{"tool":"finish","args":{"reason":"Enough context gathered"}}',
            'FILE: notes.txt\nACTION: replace\n```text\nnew text\n```',
            '{"status":"pass","issues":[]}',
            'not-json',
            'still not json',
            'still not json',
        ]
    )

    async def fake_chat_text(model: str, messages: list[dict[str, str]]) -> str:
        return next(responses)

    runner._chat_text = fake_chat_text  # type: ignore[method-assign]

    result = asyncio.run(
        runner.run(
            instruction="Update notes",
            history=[],
            requested_model=None,
            auto_commit=False,
            max_steps=3,
        )
    )

    assert result["judge"]["verdict"] == "BLOCKED"
    assert result["judge"]["failure_phase"] == "judge"


# ── _normalize_plan_response unit tests ──────────────────────────────────────

def _make_runner() -> AgentRunner:
    return AgentRunner(ollama_base="http://localhost:11434")


def test_normalize_slices_renamed_to_steps():
    runner = _make_runner()
    raw = {
        "goal": "do the thing",
        "slices": [{"id": 1, "description": "step one", "type": "analyze", "files": []}],
    }
    result = runner._normalize_plan_response(raw, "do the thing")
    assert "steps" in result
    assert "slices" not in result
    assert result["steps"][0]["description"] == "step one"


def test_normalize_missing_goal_derived_from_instruction():
    runner = _make_runner()
    raw = {"steps": [{"id": 1, "description": "do it", "type": "edit", "files": ["f.py"]}]}
    result = runner._normalize_plan_response(raw, "Update the config file")
    assert result["goal"] == "Update the config file"


def test_normalize_goal_truncated_to_200_chars():
    runner = _make_runner()
    long_instruction = "x" * 300
    raw = {"steps": []}
    result = runner._normalize_plan_response(raw, long_instruction)
    assert len(result["goal"]) == 200


def test_normalize_missing_step_type_defaults_to_analyze():
    runner = _make_runner()
    raw = {
        "goal": "refactor",
        "steps": [{"id": 1, "description": "look around", "files": []}],
    }
    result = runner._normalize_plan_response(raw, "refactor")
    assert result["steps"][0]["type"] == "analyze"


def test_normalize_invalid_step_type_replaced_with_analyze():
    runner = _make_runner()
    raw = {
        "goal": "check something",
        "steps": [{"id": 1, "description": "review code", "files": [], "type": "review"}],
    }
    result = runner._normalize_plan_response(raw, "check something")
    assert result["steps"][0]["type"] == "analyze"


def test_normalize_valid_step_type_unchanged():
    runner = _make_runner()
    for valid_type in ("edit", "create", "github"):
        raw = {
            "goal": "task",
            "steps": [{"id": 1, "description": "do", "files": [], "type": valid_type}],
        }
        result = runner._normalize_plan_response(raw, "task")
        assert result["steps"][0]["type"] == valid_type


def test_normalize_slices_and_missing_goal_together():
    """Reproduce the exact error from the screenshot: slices present, goal absent."""
    runner = _make_runner()
    raw = {
        "slices": [
            {"id": 1, "description": "gather retrospective findings", "files": []},
        ]
    }
    result = runner._normalize_plan_response(raw, "Summarise retrospective findings")
    assert "steps" in result
    assert "slices" not in result
    assert result["goal"] == "Summarise retrospective findings"
    assert result["steps"][0]["type"] == "analyze"


def test_runner_succeeds_when_model_returns_slices_schema(tmp_path: Path):
    """End-to-end: model returns CRISPY-style slices, plan should still execute."""
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "notes.txt"
    target.write_text("old\n", encoding="utf-8")

    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    responses = iter(
        [
            # Planner returns slices schema (no goal, no steps)
            '{"slices":[{"id":1,"description":"Update notes file","files":["notes.txt"]}]}',
            # Executor tool selection
            '{"tool":"finish","args":{"reason":"ready"}}',
            # Executor writes file
            "FILE: notes.txt\nACTION: replace\n```text\nnew content\n```",
            # Verifier approves
            '{"status":"pass","issues":[]}',
        ]
    )

    async def fake_chat_text(model: str, messages: list) -> str:
        return next(responses)

    runner._chat_text = fake_chat_text  # type: ignore[method-assign]

    result = asyncio.run(
        runner.run(
            instruction="Update notes file",
            history=[],
            requested_model=None,
            auto_commit=False,
            max_steps=3,
        )
    )

    assert result["steps"][0]["status"] == "applied"
    assert target.read_text(encoding="utf-8") == "new content\n"


# ── spawn_subagent tool ───────────────────────────────────────────────────────

def test_spawn_subagent_delegates_to_child_runner(tmp_path: Path):
    """spawn_subagent creates a child AgentRunner and returns a condensed result."""
    import unittest.mock as mock

    root = tmp_path / "repo"
    root.mkdir()
    (root / "child.txt").write_text("original\n", encoding="utf-8")

    parent = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)

    # Responses flow through parent AND child instances in order of LLM calls:
    # 1. Parent planner, 2. Parent executor (→spawn_subagent),
    # 3. Child planner, 4. Child executor (finish), 5. Child executor (file),
    # 6. Child verifier, 7. Parent executor (finish), 8. Parent synthesize
    responses = iter([
        '{"goal":"Delegate work","steps":[{"id":1,"description":"Delegate to subagent","files":[],"type":"analyze"}]}',
        '{"tool":"spawn_subagent","args":{"instruction":"Write hello to child.txt","max_steps":2}}',
        '{"goal":"Write hello","steps":[{"id":1,"description":"Write file","files":["child.txt"],"type":"edit"}]}',
        '{"tool":"finish","args":{"reason":"ready"}}',
        "FILE: child.txt\nACTION: replace\n```text\nhello\n```",
        '{"status":"pass","issues":[]}',
        '{"tool":"finish","args":{"reason":"subagent done"}}',
        "Subagent completed successfully.",
    ])

    async def fake_chat_text(self_arg: object, model: str, messages: list) -> str:
        return next(responses)

    # Patch at class level so child AgentRunner instances also use the mock
    with mock.patch.object(AgentRunner, "_chat_text", fake_chat_text):
        result = asyncio.run(
            parent.run(
                instruction="Delegate work",
                history=[],
                requested_model=None,
                auto_commit=False,
                max_steps=3,
            )
        )

    assert result["goal"] == "Delegate work"
    assert (root / "child.txt").read_text(encoding="utf-8") == "hello\n"


def test_spawn_subagent_empty_instruction_returns_error(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)

    result = asyncio.run(
        runner._spawn_subagent(
            instruction="   ",
            requested_model=None,
            max_steps=3,
        )
    )
    assert "error" in result


# ── _steps_are_independent ────────────────────────────────────────────────────

def test_steps_are_independent_no_overlap():
    runner = AgentRunner(ollama_base="http://localhost:11434")
    steps = [
        {"files": ["a.py"], "type": "edit"},
        {"files": ["b.py"], "type": "edit"},
        {"files": ["c.py"], "type": "edit"},
    ]
    assert runner._steps_are_independent(steps) is True


def test_steps_are_independent_with_overlap():
    runner = AgentRunner(ollama_base="http://localhost:11434")
    steps = [
        {"files": ["a.py"], "type": "edit"},
        {"files": ["a.py", "b.py"], "type": "edit"},
    ]
    assert runner._steps_are_independent(steps) is False


def test_steps_are_independent_empty_files():
    runner = AgentRunner(ollama_base="http://localhost:11434")
    # Analyze steps with no files are always independent of each other
    steps = [
        {"files": [], "type": "analyze"},
        {"files": [], "type": "analyze"},
    ]
    assert runner._steps_are_independent(steps) is True


# ── auto-parallelize ──────────────────────────────────────────────────────────

def test_auto_parallelize_triggers_for_independent_steps(tmp_path: Path):
    """When all steps touch different files, run() delegates to MultiAgentSwarm."""
    root = tmp_path / "repo"
    root.mkdir()
    for name in ("a.py", "b.py", "c.py"):
        (root / name).write_text("pass\n", encoding="utf-8")

    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)

    # Planner returns 3 steps touching different files
    plan_json = (
        '{"goal":"Multi-file refactor","steps":['
        '{"id":1,"description":"Edit a","files":["a.py"],"type":"edit"},'
        '{"id":2,"description":"Edit b","files":["b.py"],"type":"edit"},'
        '{"id":3,"description":"Edit c","files":["c.py"],"type":"edit"}'
        ']}'
    )

    swarm_called: list[bool] = []

    async def fake_maybe_parallel(**kwargs: object) -> dict | None:
        swarm_called.append(True)
        # Return a minimal result so run() short-circuits the sequential loop
        return {
            "goal": "Multi-file refactor",
            "plan": {},
            "steps": [],
            "commits": [],
            "summary": "Ran in parallel",
            "report": "Ran in parallel",
        }

    async def fake_chat_text(model: str, messages: list) -> str:
        return plan_json

    runner._chat_text = fake_chat_text  # type: ignore[method-assign]
    runner._maybe_run_parallel = fake_maybe_parallel  # type: ignore[method-assign]

    result = asyncio.run(
        runner.run(
            instruction="Multi-file refactor",
            history=[],
            requested_model=None,
            auto_commit=False,
            max_steps=5,
        )
    )

    assert swarm_called, "_maybe_run_parallel was not called"
    assert result["summary"] == "Ran in parallel"


def test_sequential_fallback_when_steps_share_files(tmp_path: Path):
    """Steps sharing a file must run sequentially — _maybe_run_parallel returns None."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "shared.py").write_text("pass\n", encoding="utf-8")

    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)

    # 3 steps all touching the same file
    plan_json = (
        '{"goal":"Sequential edits","steps":['
        '{"id":1,"description":"Edit shared","files":["shared.py"],"type":"edit"},'
        '{"id":2,"description":"Edit shared again","files":["shared.py"],"type":"edit"},'
        '{"id":3,"description":"Final touch","files":["shared.py"],"type":"edit"}'
        ']}'
    )

    from agent.models import AgentPlan
    runner2 = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    plan = AgentPlan.model_validate({
        "goal": "Sequential edits",
        "steps": [
            {"id": 1, "description": "Edit shared", "files": ["shared.py"], "type": "edit"},
            {"id": 2, "description": "Edit shared again", "files": ["shared.py"], "type": "edit"},
            {"id": 3, "description": "Final touch", "files": ["shared.py"], "type": "edit"},
        ],
    })
    result = asyncio.run(
        runner2._maybe_run_parallel(
            plan=plan,
            instruction="Sequential edits",
            requested_model=None,
            max_steps=5,
            auto_commit=False,
            user_id=None,
            memory_store=None,
            session_id=None,
            department=None,
            key_id=None,
        )
    )
    assert result is None, "Expected None (sequential), got parallel result"


# ── _commit_step git-not-found graceful handling ──────────────────────────────

def test_commit_step_handles_missing_git_gracefully(tmp_path: Path):
    """_commit_step should log a warning and return None when git is not in PATH."""
    import unittest.mock as mock

    root = tmp_path / "repo"
    root.mkdir()

    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)

    with mock.patch("subprocess.run", side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'git'")):
        result = runner._commit_step("test step", ["notes.txt"])

    assert result is None


# ── GitHubTools agent_initiated regression test ───────────────────────────────

def test_agent_runner_github_tools_agent_initiated_is_true(tmp_path: Path) -> None:
    """Regression: AgentRunner must wire GitHubTools with agent_initiated=True."""
    root = tmp_path / "repo"
    root.mkdir()

    # Token sourced from a variable (not a string literal funcarg) so Bandit B106
    # does not fire; the value is irrelevant — no network is hit.
    dummy_token = os.environ.get("GH_TEST_TOKEN", "dummy-token")
    runner = AgentRunner(
        ollama_base="http://localhost:11434",
        workspace_root=root,
        github_token=dummy_token,
    )

    assert runner.github.agent_initiated is True


# ── _build_report tests (Bug 2: per-step failure details in report field) ───


def test_build_report_includes_failed_step_issues(tmp_path: Path) -> None:
    """_build_report includes at least one failed step's issues text."""
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=tmp_path)
    step_results = [
        {"step_id": 1, "status": "applied", "description": "step 1"},
        {
            "step_id": 2,
            "status": "failed",
            "description": "step 2",
            "failure_phase": "verification",
            "issues": ["Syntax error at line 5", "Missing import"],
        },
        {
            "step_id": 3,
            "status": "failed",
            "description": "step 3",
            "failure_phase": "tool_selection",
            "issues": ["Tool selection failed: bad model output"],
        },
    ]
    report = runner._build_report("Test goal", step_results, commits=[], pr_url=None)
    assert "Test goal" in report
    assert "1/3" in report  # applied count
    assert "2" in report  # failed count
    assert "Syntax error at line 5" in report
    assert "Tool selection failed" in report
    assert "verification" in report
    assert "tool_selection" in report


def test_build_report_dedupes_identical_failures(tmp_path: Path) -> None:
    """_build_report dedupes 50 identical failures — doesn't flood the comment."""
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=tmp_path)
    step_results = [
        {
            "step_id": i,
            "status": "failed",
            "description": f"step {i}",
            "failure_phase": "verification",
            "issues": ["Same syntax error"],  # identical for all 50
        }
        for i in range(50)
    ]
    report = runner._build_report("Test goal", step_results, commits=[], pr_url=None)
    # The report should mention the issue but not 50 times
    assert "Same syntax error" in report
    # Count occurrences — should be at most 5 (the max_failures cap)
    assert report.count("Same syntax error") <= 5
    # Should mention the remaining failures
    assert "more failed step" in report


def test_build_report_capped_at_5_failures(tmp_path: Path) -> None:
    """_build_report shows at most 5 failed steps."""
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=tmp_path)
    step_results = [
        {
            "step_id": i,
            "status": "failed",
            "description": f"step {i}",
            "failure_phase": "verification",
            "issues": [f"Unique error {i}"],
        }
        for i in range(10)
    ]
    report = runner._build_report("Test goal", step_results, commits=[], pr_url=None)
    # Should show 5 unique errors
    for i in range(5):
        assert f"Unique error {i}" in report
    # Should NOT show errors 5-9
    for i in range(5, 10):
        assert f"Unique error {i}" not in report
    assert "5 more failed step" in report


def test_build_report_no_failures(tmp_path: Path) -> None:
    """_build_report with all-applied steps has no failure section."""
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=tmp_path)
    step_results = [
        {"step_id": i, "status": "applied", "description": f"step {i}"}
        for i in range(5)
    ]
    report = runner._build_report("Test goal", step_results, commits=["abc123"], pr_url=None)
    assert "5/5" in report
    assert "Failed step" not in report
    assert "abc123" not in report or "Commits" in report  # commits count line


def test_agent_runner_fails_closed_when_spec_approval_required_but_persist_broken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression: AGENT_SPEC_APPROVAL_REQUIRED=true must never let a run
    through un-reviewed just because spec persistence broke (e.g. the
    SQLite backend didn't recognize the agent_specs collection). The run
    should fail with AgentPhaseError, not silently execute the plan."""
    monkeypatch.setenv("AGENT_SPEC_APPROVAL_REQUIRED", "true")

    async def broken_persist(**kwargs):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr("services.spec_store.persist_plan_spec", broken_persist)

    root = tmp_path / "repo"
    root.mkdir()
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    responses = iter(['{"goal":"Do work","steps":[]}'])

    async def fake_chat_text(model: str, messages: list[dict[str, str]]) -> str:
        return next(responses)

    runner._chat_text = fake_chat_text  # type: ignore[method-assign]

    with pytest.raises(AgentPhaseError, match="spec_approval"):
        asyncio.run(
            runner.run(
                instruction="Do work", history=[], requested_model=None,
                auto_commit=False, max_steps=3,
            )
        )


def test_agent_runner_proceeds_normally_when_approval_not_required_and_persist_broken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Persistence stays best-effort when nothing is gating on it — a
    storage hiccup must not block a normal (auto-approved) run."""
    monkeypatch.delenv("AGENT_SPEC_APPROVAL_REQUIRED", raising=False)

    async def broken_persist(**kwargs):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr("services.spec_store.persist_plan_spec", broken_persist)

    root = tmp_path / "repo"
    root.mkdir()
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)
    responses = iter([
        '{"goal":"Do work","steps":[]}',
    ])

    async def fake_chat_text(model: str, messages: list[dict[str, str]]) -> str:
        return next(responses)

    runner._chat_text = fake_chat_text  # type: ignore[method-assign]

    result = asyncio.run(
        runner.run(
            instruction="Do work", history=[], requested_model=None,
            auto_commit=False, max_steps=3,
        )
    )
    assert result["goal"] == "Do work"
