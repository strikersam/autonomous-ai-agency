"""The configured remote skill repos must be fetched without a human trigger.

``SkillRegistry.refresh_remote()`` had four callers — ``GET /api/skills/discover``,
``POST /api/skills/refresh``, ``proxy.py`` and ``services/onboarding.py`` — and
none of them run at startup. A fresh deploy therefore left every configured
GitHub registry unfetched until someone happened to open the skills page, while
Doctor reported "N remote skill repos configured but none fetched yet" and told
the operator they "will appear after the first refresh" — a refresh nothing
triggered. Same defect shape as the dead ``RUN_HERMES_IN_PROCESS`` flag.
"""
from __future__ import annotations

import asyncio

import pytest

import services.background as bg


class _Registry:
    """Stands in for SkillRegistry, recording whether the fetch happened."""

    def __init__(self, added: int = 3, boom: Exception | None = None) -> None:
        self.added = added
        self.boom = boom
        self.calls = 0

    async def refresh_remote(self) -> int:
        self.calls += 1
        if self.boom is not None:
            raise self.boom
        return self.added


@pytest.fixture(autouse=True)
def clean_task():
    bg._skill_refresh_task = None
    yield
    task = bg._skill_refresh_task
    if task is not None and not task.done():
        task.cancel()
    bg._skill_refresh_task = None


def _install(monkeypatch, registry) -> None:
    monkeypatch.setattr(
        "agent.skill_registry.get_skill_registry_safe", lambda: registry
    )


class TestBootRefresh:
    @pytest.mark.asyncio
    async def test_it_fetches_the_remote_registries(self, monkeypatch) -> None:
        registry = _Registry(added=7)
        _install(monkeypatch, registry)

        task = bg._start_skill_registry_refresh()
        assert task is not None
        await task

        assert registry.calls == 1, (
            "without this the configured repos stay unfetched until a human "
            "opens the skills page"
        )

    @pytest.mark.asyncio
    async def test_boot_is_not_blocked_by_the_fetch(self, monkeypatch) -> None:
        """It must be fire-and-forget: this is one HTTP round trip per registry."""
        started = asyncio.Event()

        class _Slow(_Registry):
            async def refresh_remote(self) -> int:
                started.set()
                await asyncio.sleep(30)
                return 0

        _install(monkeypatch, _Slow())
        task = bg._start_skill_registry_refresh()

        assert task is not None
        assert not task.done(), "the scheduler must return before the fetch finishes"
        task.cancel()

    @pytest.mark.asyncio
    async def test_the_flag_switches_it_off(self, monkeypatch) -> None:
        _install(monkeypatch, _Registry())
        monkeypatch.setenv("SKILL_REGISTRY_REFRESH_ON_BOOT", "false")

        assert bg._start_skill_registry_refresh() is None

    @pytest.mark.asyncio
    async def test_no_registry_is_not_an_error(self, monkeypatch) -> None:
        """A deployment without a skill registry must still boot cleanly."""
        _install(monkeypatch, None)
        assert bg._start_skill_registry_refresh() is None

    @pytest.mark.asyncio
    async def test_it_is_idempotent(self, monkeypatch) -> None:
        """Web lifespan and worker_main can both call into one process."""
        class _Slow(_Registry):
            async def refresh_remote(self) -> int:
                await asyncio.sleep(30)
                return 0

        _install(monkeypatch, _Slow())
        first = bg._start_skill_registry_refresh()
        second = bg._start_skill_registry_refresh()

        assert first is second, "a second fetch would double the GitHub calls"
        if first:
            first.cancel()

    @pytest.mark.asyncio
    async def test_a_failed_fetch_never_propagates(self, monkeypatch) -> None:
        """Remote skills are optional; a rate limit must not surface as an error."""
        registry = _Registry(boom=RuntimeError("GitHub 403 rate limited"))
        _install(monkeypatch, registry)

        task = bg._start_skill_registry_refresh()
        assert task is not None
        await task  # must not raise

        assert task.exception() is None
        assert registry.calls == 1

    @pytest.mark.asyncio
    async def test_shutdown_cancels_an_in_flight_fetch(self, monkeypatch) -> None:
        class _Slow(_Registry):
            async def refresh_remote(self) -> int:
                await asyncio.sleep(30)
                return 0

        _install(monkeypatch, _Slow())
        task = bg._start_skill_registry_refresh()

        services = bg.BackgroundServices(
            runtime_manager=_NullRuntimeManager(),
            dispatcher=_NullDispatcher(),
            dispatcher_task=asyncio.create_task(asyncio.sleep(0)),
            skill_refresh_task=task,
        )
        await services.stop()

        assert task is not None and task.done(), (
            "a fetch left running past shutdown keeps the event loop alive"
        )


class _NullDispatcher:
    def stop(self) -> None:
        return None


class _NullRuntimeManager:
    async def stop(self) -> None:
        return None


def test_startup_actually_calls_it() -> None:
    """The guard against re-creating the very bug this fixes.

    ``refresh_remote`` existed and worked; what was missing was a caller at boot.
    A helper that nothing invokes is the same defect wearing a different name, so
    assert the wiring rather than trusting it.
    """
    import inspect

    src = inspect.getsource(bg.start_background_services)
    assert "_start_skill_registry_refresh()" in src, (
        "start_background_services must invoke the boot refresh, or the remote "
        "skill repos go unfetched exactly as before"
    )
    assert "_start_hermes_in_process()" in src, (
        "same for Hermes — the flag was dead because nothing called it"
    )
