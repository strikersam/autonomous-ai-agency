"""The lessons store is never read or written on the event loop.

The stall watchdog named this in production (2026-11-13): ``harness_spec.refine``
→ ``lessons.recent`` → a synchronous pymongo read, blocking the loop for 8.7s.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from agent import harness_spec, lessons


async def _ticks_while(coro) -> tuple[object, int]:
    ticks = 0
    done = asyncio.Event()

    async def ticker() -> None:
        nonlocal ticks
        while not done.is_set():
            await asyncio.sleep(0.01)
            ticks += 1

    task = asyncio.create_task(ticker())
    try:
        result = await coro
    finally:
        done.set()
        await task
    return result, ticks


def _slow(result=None):
    def fn(*args, **kwargs):
        time.sleep(0.3)  # stands in for a slow database round trip
        return result
    return fn


async def test_recording_a_run_outcome_keeps_the_loop_responsive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lessons, "record_step_failures", _slow())
    monkeypatch.setattr(lessons, "record_run_success", lambda *a, **k: None)
    _, ticks = await _ticks_while(lessons.record_run_outcome_async("goal", []))
    assert ticks >= 8


async def test_reading_lessons_keeps_the_loop_responsive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lessons, "recent_lessons_block", _slow("LESSONS"))
    result, ticks = await _ticks_while(lessons.recent_lessons_block_async(query="q"))
    assert result == "LESSONS" and ticks >= 8


async def test_recording_a_timeout_keeps_the_loop_responsive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lessons, "record_task_timeout", _slow())
    _, ticks = await _ticks_while(lessons.record_task_timeout_async("t", "g", "m"))
    assert ticks >= 8


async def test_refining_the_spec_keeps_the_loop_responsive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(harness_spec, "refine", _slow([]))
    result, ticks = await _ticks_while(harness_spec.refine_async(tmp_path))
    assert result == [] and ticks >= 8


def test_coroutines_use_the_off_loop_wrappers() -> None:
    import agent.loop as loop_module
    import tasks.service as service_module

    loop_src = Path(loop_module.__file__).read_text(encoding="utf-8")
    assert "await record_run_outcome_async(" in loop_src
    assert "await refine_async(" in loop_src
    assert "await recent_lessons_block_async(" in loop_src
    for sync_call in ("record_step_failures(plan.goal", "refine(self.tools.root)", "= recent_lessons_block("):
        assert sync_call not in loop_src, f"{sync_call} still runs on the event loop"
    service_src = Path(service_module.__file__).read_text(encoding="utf-8")
    assert "await record_task_timeout_async(" in service_src


def test_the_ceo_playbook_reads_its_stores_off_the_loop() -> None:
    import agent.ceo_playbook as playbook

    src = Path(playbook.__file__).read_text(encoding="utf-8")
    assert "await asyncio.to_thread(_learn_and_read)" in src
    assert "beliefs(doc), recent_lessons_block())" not in src


def test_enrichment_and_spec_persistence_run_off_the_loop() -> None:
    """Both reach the lessons store or the refine lock, so neither may block the loop."""
    import agent.loop as loop_module
    import runtimes.adapters.internal_agent as adapter_module

    loop_src = Path(loop_module.__file__).read_text(encoding="utf-8")
    assert loop_src.count("await asyncio.to_thread(self._inject_enrichment,") == 2
    assert "        self._inject_enrichment(" not in loop_src.replace("await asyncio.to_thread(self._inject_enrichment,", "")
    adapter_src = Path(adapter_module.__file__).read_text(encoding="utf-8")
    assert adapter_src.count("await asyncio.to_thread(persist_spec,") == 2
    assert "    persist_spec(worktree_path" not in adapter_src


def test_the_playbook_serialises_load_learn_save() -> None:
    import agent.ceo_playbook as playbook

    src = Path(playbook.__file__).read_text(encoding="utf-8")
    assert "with _LEARN_LOCK:" in src
