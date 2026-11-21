"""Shared fixtures of the reliability suite: deterministic executors, a run API client and
the failover stubs. Nothing here touches the network or a real model."""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from packages.runs.composer import Composer
from packages.runs.composition import ChildJob, ChildOutcome, CompositionSpec, Step
from packages.runs.store import RunStore

ENV_KEYS = ("AGENCY_KILL_SWITCH", "RUNS_MAX_CHILDREN", "RUNS_MAX_DEPTH", "RUNS_MAX_PARALLEL")
SECRET = "sk-" + "a1B2c3D4e5" * 4


class FakeExec:
    """Deterministic child executor: per step key (delay s, ok, out, cost, tokens)."""

    def __init__(self, plan: dict[str, dict[str, Any]] | None = None) -> None:
        self.plan, self.calls, self.running, self.peak = plan or {}, [], 0, 0

    async def __call__(self, job: ChildJob) -> ChildOutcome:
        cfg = self.plan.get(job.step.key, {})
        self.calls.append(job.step.key)
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            await asyncio.sleep(cfg.get("delay", 0.0))
        finally:
            self.running -= 1
        ok = cfg.get("ok", True)
        return ChildOutcome(success=ok, output=cfg.get("out", f"out:{job.step.key}"),
                            error=None if ok else "boom", cost_usd=cfg.get("cost", 0.0),
                            tokens=cfg.get("tokens", 0))


def step(key: str, **kw: Any) -> Step:
    """A task step titled after its key."""
    return Step(key=key, title=key, **kw)


async def compose(spec: CompositionSpec, plan: dict[str, dict[str, Any]] | None = None, *,
                  store: RunStore | None = None, executor: Any = None):
    """Start and run *spec*; returns ``(composer, store, executor, root, result)``."""
    store = store or RunStore()
    ex = executor or FakeExec(plan)
    composer = Composer(store, ex, cancel_poll_s=0.01)
    root = await composer.start(spec)
    return composer, store, ex, root, await composer.run(root.run_id, spec)


async def wait_for(predicate, timeout: float = 3.0) -> None:
    """Poll the async *predicate* until true or fail the test."""
    async def poll() -> None:
        while not await predicate():
            await asyncio.sleep(0.01)
    await asyncio.wait_for(poll(), timeout)


class StubProvider:
    """A provider record as ``packages.ai.failover_client`` reads it."""

    def __init__(self, pid: str, models: list[str]) -> None:
        self.id, self.base_url, self.models = pid, f"https://{pid}.invalid/v1", models
        self.api_key, self.tier, self.is_healthy = "k", "free", True


class StubManager:
    """Minimal ``BrainFailoverManager`` over a fixed provider list."""

    def __init__(self, providers: list[StubProvider]) -> None:
        self.providers, self.successes, self.failures = providers, [], []

    def max_attempts(self) -> int:
        return max(len(self.providers), 1)

    def next_provider(self, *, exclude=None, requested_model=None):
        return next((p for p in self.providers if p.id not in (exclude or set()) and p.is_healthy), None)

    def get_providers(self):
        return self.providers

    def resolve_model(self, provider, requested_model):
        return provider.models[0]

    def record_success(self, provider_id, latency_ms=0.0):
        self.successes.append(provider_id)

    def record_failure(self, provider_id, reason, status=None):
        self.failures.append((provider_id, reason))


def install_scripted_transport(monkeypatch, providers: list[StubProvider],
                               responses: list[Any]) -> tuple[StubManager, list[str]]:
    """Replace the failover manager and the HTTP client by a scripted response sequence."""
    monkeypatch.delenv("LLM_ROUTER_ENABLED", raising=False)
    manager = StubManager(providers)
    monkeypatch.setattr("services.brain_failover.get_failover_manager", lambda: manager)
    calls: list[str] = []
    script = list(responses)

    class _Client:
        def __init__(self, *a: Any, **k: Any) -> None: ...

        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *a: Any) -> bool:
            return False

        async def post(self, url: str, json: Any = None, headers: Any = None) -> Any:
            calls.append(url)
            nxt = script.pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            return nxt

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    return manager, calls


def ok_body(text: str) -> httpx.Response:
    """A 200 OpenAI style chat completion."""
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": text}}],
                                     "usage": {"prompt_tokens": 1, "completion_tokens": 1}})
