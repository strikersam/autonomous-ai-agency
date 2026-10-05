"""Production regressions from 2026-10-04, after Bedrock gpt-oss took the load.

* gpt-oss writes ``<reasoning>…</reasoning>`` inline before its JSON answer (or
  only that, when it runs out of tokens); 28 steps in 30 min failed with
  "Model did not return a JSON object".
* The reconciler re-queued the same FAILED tasks every ~10 min at "retry 0/5":
  it never counted the retry, so the cap never tripped.
"""
from __future__ import annotations

import time

import pytest

from agent.loop import AgentRunner
from tasks.models import Task, TaskStatus
from tasks.store import TaskStore


@pytest.fixture
def runner(tmp_path) -> AgentRunner:
    return AgentRunner(ollama_base="http://localhost:1", workspace_root=str(tmp_path))


def test_inline_reasoning_is_stripped_before_parsing(runner):
    raw = '<reasoning>We need to run list_files.</reasoning>{"tool": "list_files", "args": {"path": "."}}'
    assert runner._extract_json(raw) == {"tool": "list_files", "args": {"path": "."}}


def test_unclosed_reasoning_with_braces_inside_is_not_parsed_as_the_answer(runner):
    with pytest.raises(Exception):
        runner._extract_json('<reasoning>maybe {"tool": "x"} would work but')


async def test_reasoning_only_reply_re_asks_the_original_question(runner, monkeypatch):
    calls: list[list[dict]] = []
    replies = iter(["<reasoning>We need to read the file.</reasoning>",
                    '{"tool": "read_file", "args": {"path": "a.py"}}'])

    async def _fake_chat_text(self, model, messages):  # noqa: ANN001
        calls.append(messages)
        return next(replies)

    monkeypatch.setattr(AgentRunner, "_chat_text", _fake_chat_text)
    original = [{"role": "user", "content": "pick a tool"}]
    assert await runner._chat_json("m", original) == {"tool": "read_file", "args": {"path": "a.py"}}
    assert calls[1] == original  # not "reformat this reasoning as JSON"


async def test_reconciler_counts_each_retry_until_the_cap():
    store = TaskStore()
    task = Task(owner_id="u", title="t", status=TaskStatus.FAILED)
    task.updated_at = time.time() - 10 * 24 * 3600
    await store.create(task)

    runs = 0
    for _ in range(10):
        if await store.reconcile_stranded_tasks(active_task_ids=set(), auto_retry_cap=3):
            runs += 1
        doc = store._mem[task.task_id]
        doc["status"] = TaskStatus.FAILED.value               # the retry failed again
        doc["updated_at"] = time.time() - 10 * 24 * 3600      # and has cooled down
    assert runs == 3
    assert store._mem[task.task_id]["auto_retry_count"] == 3
