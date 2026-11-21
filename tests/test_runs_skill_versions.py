"""Phase 6: skill version pinning on the run record (packages/runs/skill_versions.py)."""
from __future__ import annotations

import httpx
import pytest

from packages.runs import skill_versions, task_binding
from packages.runs.models import RunRecord
from tests._runs_task_fixtures import (FakeRuntime, coordinator, queued_task,
                                       reset_process_state, sqlite_pair)


def _skill(base, name: str, body: str) -> None:
    (base / name).mkdir(parents=True)
    (base / name / "SKILL.md").write_text(body, encoding="utf-8")


def test_declared_version_wins_and_default_is_a_stable_hash(tmp_path):
    _skill(tmp_path, "pinned", "---\nname: pinned\nversion: 2.1.0\n---\nbody\n")
    _skill(tmp_path, "plain", "---\nname: plain\n---\nbody\n")
    first = skill_versions.resolve_skill_versions((tmp_path,))
    assert first["pinned"] == "2.1.0"
    assert first["plain"].startswith("sha-") and len(first["plain"]) == 16
    assert skill_versions.resolve_skill_versions((tmp_path,)) == first


def test_version_outside_frontmatter_is_ignored():
    assert skill_versions.parse_version("# title\nversion: 9\n") is None
    assert skill_versions.parse_version("---\nname: x\n---\nversion: 9\n") is None


def test_the_real_skill_dirs_resolve_every_skill():
    resolved = skill_versions.resolve_skill_versions()
    assert resolved and all(v for v in resolved.values())


def test_pin_keeps_the_recorded_versions_after_the_file_changes(tmp_path):
    _skill(tmp_path, "alpha", "---\nname: alpha\n---\nv1\n")
    recorded = skill_versions.pin(None, skill_versions.resolve_skill_versions((tmp_path,)))
    (tmp_path / "alpha" / "SKILL.md").write_text("---\nname: alpha\n---\nv2\n", encoding="utf-8")
    now = skill_versions.resolve_skill_versions((tmp_path,))
    assert now["alpha"] != recorded["alpha"]
    assert skill_versions.pin(recorded, now) == recorded


def test_old_documents_without_the_field_still_validate():
    run = RunRecord.model_validate({"run_id": "run_x"})
    assert run.skill_versions == {}


@pytest.mark.anyio
async def test_a_resumed_run_keeps_its_pin_while_a_skill_changes(tmp_path, monkeypatch):
    reset_process_state(monkeypatch)
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "true")
    skills = tmp_path / "skills"
    _skill(skills, "alpha", "---\nname: alpha\n---\nv1\n")
    monkeypatch.setattr(skill_versions, "SKILL_DIRS", (skills,))
    async with sqlite_pair(tmp_path) as (store, _):
        task = await queued_task(store)
        runtime = FakeRuntime(lambda spec: _raise(httpx.ConnectError("Connection refused")))
        first = await coordinator(store, runtime).execute(task.task_id)
        run_store = task_binding.run_store_for(store)
        pinned = (await run_store.get(first.current_run_id)).skill_versions
        assert set(pinned) == {"alpha"}
        (skills / "alpha" / "SKILL.md").write_text("---\nname: alpha\n---\nv2\n", encoding="utf-8")
        second = await coordinator(store, FakeRuntime()).execute(task.task_id)
        assert second.current_run_id == first.current_run_id
        assert (await run_store.get(second.current_run_id)).skill_versions == pinned


async def _raise(exc: Exception):
    raise exc
