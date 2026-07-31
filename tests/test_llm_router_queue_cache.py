"""Queue, bulkhead, deduplication, caching, context fitting, and budgets.

These are the mechanisms that keep a long-running agency alive rather than
merely correct: backpressure instead of unbounded growth, one slow provider
contained instead of draining the pool, and a conversation that outgrows its
context window shrunk rather than failed.
"""
from __future__ import annotations

import asyncio

import pytest

from packages.llm import budget as llm_budget
from packages.llm import cache as llm_cache
from packages.llm.cache import CacheManager, cosine_similarity, payload_key
from packages.llm.config import (
    BudgetConfig,
    CacheConfig,
    CacheLayerConfig,
)
from packages.llm.context import (
    ContextManager,
    chunk_document,
    prune,
    semantic_select,
    sliding_window,
    total_tokens,
)
from packages.llm.queue import Bulkhead, Deduplicator, RequestQueue, request_fingerprint
from packages.llm.types import LLMRequest, Priority, QueueFull, Usage


# ── Queue ───────────────────────────────────────────────────────────────────

async def test_queue_runs_jobs_and_reports_stats():
    queue = RequestQueue(max_depth=10, max_concurrency=2)

    async def job():
        await asyncio.sleep(0)
        return "done"

    results = await asyncio.gather(*[queue.submit(job) for _ in range(5)])
    assert results == ["done"] * 5
    assert queue.stats()["completed"] == 5
    assert queue.stats()["depth"] == 0


async def test_queue_applies_backpressure_when_full():
    queue = RequestQueue(max_depth=2, max_concurrency=1)
    release = asyncio.Event()

    async def blocked():
        await release.wait()
        return "ok"

    running = [asyncio.create_task(queue.submit(blocked)) for _ in range(2)]
    await asyncio.sleep(0.02)

    with pytest.raises(QueueFull):
        await queue.submit(blocked)

    release.set()
    assert await asyncio.gather(*running) == ["ok", "ok"]
    assert queue.stats()["rejected"] == 1


async def test_queue_limits_concurrency():
    queue = RequestQueue(max_depth=50, max_concurrency=3)
    peak = 0
    current = 0

    async def job():
        nonlocal peak, current
        current += 1
        peak = max(peak, current)
        await asyncio.sleep(0.01)
        current -= 1
        return None

    await asyncio.gather(*[queue.submit(job) for _ in range(20)])
    assert peak <= 3, f"concurrency limit breached: {peak} in flight"


async def test_queue_honours_timeout_and_cancellation():
    queue = RequestQueue(max_depth=10, max_concurrency=2)

    async def slow():
        await asyncio.sleep(5)

    with pytest.raises(asyncio.TimeoutError):
        await queue.submit(slow, timeout=0.05)
    assert queue.stats()["timed_out"] == 1

    task = asyncio.create_task(queue.submit(slow))
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert queue.stats()["cancelled"] == 1


async def test_queue_accepts_priorities():
    queue = RequestQueue(max_depth=20, max_concurrency=1)

    async def job():
        return "ok"

    assert await queue.submit(job, priority=Priority.CRITICAL) == "ok"
    assert await queue.submit(job, priority=Priority.BULK) == "ok"


async def test_critical_work_overtakes_queued_bulk_work():
    """Priority must actually reorder admission, not merely be accepted.

    A plain FIFO semaphore accepts the priority argument and ignores it, so
    this asserts the observable consequence: a CRITICAL job submitted last is
    served before BULK jobs that were already waiting.
    """
    queue = RequestQueue(max_depth=50, max_concurrency=1)
    order: list[str] = []
    release = asyncio.Event()

    async def blocker():
        await release.wait()
        return "blocker"

    async def tagged(name: str):
        order.append(name)
        return name

    held = asyncio.create_task(queue.submit(blocker, priority=Priority.NORMAL))
    await asyncio.sleep(0.02)                      # the single slot is taken

    waiting = [
        asyncio.create_task(queue.submit(lambda n=f"bulk{i}": tagged(n),
                                         priority=Priority.BULK))
        for i in range(3)
    ]
    await asyncio.sleep(0.02)                      # all three are queued
    late = asyncio.create_task(queue.submit(lambda: tagged("critical"),
                                            priority=Priority.CRITICAL))
    await asyncio.sleep(0.02)

    release.set()
    await asyncio.gather(held, late, *waiting)

    assert order[0] == "critical", f"priority ignored — ran {order}"
    assert set(order[1:]) == {"bulk0", "bulk1", "bulk2"}


async def test_same_priority_stays_fifo():
    """Ties inside a band must not starve the earliest arrival."""
    queue = RequestQueue(max_depth=50, max_concurrency=1)
    order: list[str] = []
    release = asyncio.Event()

    async def blocker():
        await release.wait()

    async def tagged(name: str):
        order.append(name)

    held = asyncio.create_task(queue.submit(blocker, priority=Priority.NORMAL))
    await asyncio.sleep(0.02)

    queued = []
    for i in range(4):
        queued.append(asyncio.create_task(
            queue.submit(lambda n=f"job{i}": tagged(n), priority=Priority.NORMAL)
        ))
        await asyncio.sleep(0.01)                  # establish a clear arrival order

    release.set()
    await asyncio.gather(held, *queued)

    assert order == ["job0", "job1", "job2", "job3"], f"not FIFO within a band: {order}"


# ── Bulkhead ────────────────────────────────────────────────────────────────

async def test_bulkhead_isolates_one_provider_from_another():
    """A saturated provider must not consume another provider's capacity."""
    bulkhead = Bulkhead(default_limit=8)
    bulkhead.configure("slow", 1)
    bulkhead.configure("fast", 4)
    release = asyncio.Event()

    async def hold():
        async with bulkhead.slot("slow", timeout=5.0) as got:
            assert got
            await release.wait()

    holder = asyncio.create_task(hold())
    await asyncio.sleep(0.02)

    # "slow" is full, so its next caller is turned away quickly...
    async with bulkhead.slot("slow", timeout=0.05) as got_slow:
        assert got_slow is False
    # ...while "fast" is entirely unaffected.
    async with bulkhead.slot("fast", timeout=0.05) as got_fast:
        assert got_fast is True

    release.set()
    await holder


async def test_bulkhead_tracks_in_flight_and_rejections():
    bulkhead = Bulkhead()
    bulkhead.configure("demo", 1)
    release = asyncio.Event()

    async def hold():
        async with bulkhead.slot("demo", timeout=5.0):
            assert bulkhead.in_flight("demo") == 1
            await release.wait()

    task = asyncio.create_task(hold())
    await asyncio.sleep(0.02)
    async with bulkhead.slot("demo", timeout=0.05):
        pass
    release.set()
    await task

    assert bulkhead.snapshot()["rejected"]["demo"] == 1
    assert bulkhead.in_flight("demo") == 0


# ── Deduplication ───────────────────────────────────────────────────────────

async def test_identical_concurrent_requests_collapse_to_one_call():
    dedupe: Deduplicator[str] = Deduplicator(window_sec=30.0)
    calls = 0

    async def factory():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return "answer"

    results = await asyncio.gather(*[dedupe.run("same", factory) for _ in range(5)])
    assert calls == 1, "identical concurrent requests were not deduplicated"
    assert [r[0] for r in results] == ["answer"] * 5
    assert sum(1 for r in results if r[1]) == 4      # four joined an in-flight call


async def test_dedupe_failure_propagates_to_every_waiter():
    dedupe: Deduplicator[str] = Deduplicator(window_sec=30.0)

    async def failing():
        await asyncio.sleep(0.02)
        raise RuntimeError("upstream died")

    results = await asyncio.gather(
        *[dedupe.run("same", failing) for _ in range(3)], return_exceptions=True
    )
    assert all(isinstance(r, RuntimeError) for r in results)
    # A failed call must not poison the key for the next attempt.
    assert dedupe.stats()["in_flight"] == 0


def test_fingerprint_ignores_irrelevant_fields():
    base = {"model": "m", "messages": [{"role": "user", "content": "hi"}], "temperature": 0.0}
    assert request_fingerprint(base) == request_fingerprint({**base, "user": "someone"})
    assert request_fingerprint(base) != request_fingerprint({**base, "temperature": 0.9})


# ── Cache ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_singletons():
    llm_cache.reset()
    llm_budget.reset()
    yield
    llm_cache.reset()
    llm_budget.reset()


def _cache() -> CacheManager:
    return CacheManager(CacheConfig(
        response=CacheLayerConfig(enabled=True, ttl_sec=60.0, max_entries=3),
        semantic=CacheLayerConfig(enabled=True, ttl_sec=60.0, max_entries=10),
        semantic_threshold=0.95,
    ))


def test_response_cache_round_trip_and_stats():
    cache = _cache()
    key = payload_key({"model": "m", "messages": [{"role": "user", "content": "hi"}]})
    assert cache.get_response(key) is None
    cache.put_response(key, {"text": "hello"})
    assert cache.get_response(key)["text"] == "hello"

    stats = cache.stats()
    response_layer = next(
        layer for layer in stats["layers"] if layer["name"] == "response"
    )
    assert response_layer["hits"] == 1 and response_layer["misses"] == 1


def test_cache_evicts_least_recently_used():
    cache = _cache()
    for i in range(4):
        cache.put_response(f"k{i}", {"text": str(i)})
    assert cache.get_response("k0") is None      # evicted
    assert cache.get_response("k3") is not None


def test_cache_entries_expire():
    cache = CacheManager(CacheConfig(
        response=CacheLayerConfig(enabled=True, ttl_sec=-1.0, max_entries=10),
    ))
    cache.put_response("k", {"text": "stale"})
    assert cache.get_response("k") is None


@pytest.mark.parametrize("kwargs,expected", [
    ({"temperature": 0.0}, True),
    ({"temperature": 0.1}, True),
    ({"temperature": 0.3}, False),   # the LLMRequest default is NOT cacheable
    ({"temperature": 0.9}, False),
    ({"temperature": 0.0, "stream": True}, False),
    ({"temperature": 0.0, "tools": [{"type": "function"}]}, False),
    ({"temperature": 0.0, "cacheable": False}, False),
])
def test_cacheability_policy(kwargs, expected):
    """Caching a sampled or tool-bearing response would change behaviour.

    The default request temperature (0.3) is deliberately above the threshold:
    an agent asking for variety must keep getting it. This mirrors the legacy
    ``packages/ai/response_cache.py`` rule, which is stricter still.
    """
    request = LLMRequest(messages=[{"role": "user", "content": "hi"}], **kwargs)
    assert _cache().is_cacheable(request) is expected


def test_semantic_cache_matches_near_duplicates_only():
    cache = _cache()
    cache.put_semantic("k", [1.0, 0.0, 0.0], {"text": "answer"})

    assert cache.get_semantic([1.0, 0.0, 0.0])["text"] == "answer"     # identical
    assert cache.get_semantic([0.0, 1.0, 0.0]) is None                 # orthogonal


def test_cosine_similarity_edges():
    assert cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine_similarity([], [1, 0]) == 0.0
    assert cosine_similarity([0, 0], [1, 0]) == 0.0


# ── Context management ──────────────────────────────────────────────────────

def test_prune_truncates_tool_blobs_and_drops_duplicates():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "same"},
        {"role": "user", "content": "same"},
        {"role": "tool", "content": "x" * 9000},
    ]
    pruned, removed = prune(messages, max_tool_chars=100)
    assert removed == 2
    assert len(pruned) == 3
    assert "truncated" in pruned[-1]["content"]
    # Truncation keeps the head, which is where the signal is.
    assert pruned[-1]["content"].startswith("x" * 100)


def test_sliding_window_keeps_system_and_the_task_defining_first_turn():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "THE TASK: build the thing"},
        *[{"role": "user", "content": f"step {i} " + "z" * 400} for i in range(30)],
    ]
    kept, dropped = sliding_window(messages, budget_tokens=800, keep_recent=2)

    assert kept[0]["role"] == "system"
    assert "THE TASK" in kept[1]["content"], "the first turn defines the task; never drop it"
    assert dropped, "nothing was dropped despite overflow"
    assert total_tokens(kept) < total_tokens(messages)


def test_chunk_document_splits_with_overlap():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 200 for i in range(10))
    chunks = chunk_document(text, chunk_tokens=500, overlap_tokens=50)
    assert len(chunks) > 1
    assert all(chunks)
    # Nothing is silently discarded.
    assert sum(len(c) for c in chunks) >= len(text) * 0.9


def test_chunk_document_handles_a_single_giant_paragraph():
    chunks = chunk_document("x" * 50_000, chunk_tokens=1000)
    assert len(chunks) > 1


def test_semantic_select_returns_relevant_history():
    dropped = [
        {"role": "user", "content": "the deployment pipeline uses Render webhooks"},
        {"role": "user", "content": "lunch was good"},
        {"role": "user", "content": "cats are fine animals"},
    ]
    picked = semantic_select(dropped, "tell me about the deployment pipeline", limit=1)
    assert len(picked) == 1
    assert "Render" in picked[0]["content"]


async def test_fit_is_a_no_op_when_the_conversation_already_fits():
    manager = ContextManager()
    messages = [{"role": "user", "content": "short"}]
    result = await manager.fit(messages, context_window=32768, max_output_tokens=1000)
    assert result.modified is False
    assert result.messages == messages


async def test_fit_shrinks_an_overflowing_conversation():
    manager = ContextManager(keep_recent=2)
    # Distinct content, so pruning's duplicate rule cannot absorb the overflow
    # and the sliding window is genuinely exercised.
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "THE TASK"},
        *[{"role": "assistant", "content": f"turn {i} " + "y" * 4000} for i in range(20)],
    ]
    result = await manager.fit(messages, context_window=8192, max_output_tokens=1000,
                              query="THE TASK")

    assert result.final_tokens < result.original_tokens
    assert "sliding_window" in result.strategies_applied
    assert result.needs_larger_model is False


async def test_fit_inserts_a_summary_when_one_is_available():
    async def summarise(dropped):
        return f"Summary of {len(dropped)} dropped turns."

    manager = ContextManager(keep_recent=1, summarise=summarise)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "task"},
        *[{"role": "assistant", "content": f"turn {i} " + "y" * 4000} for i in range(20)],
    ]
    result = await manager.fit(messages, context_window=8192, max_output_tokens=1000)

    assert "summary" in result.strategies_applied
    assert any("Summary of" in str(m.get("content")) for m in result.messages)


async def test_summariser_failure_does_not_fail_the_request():
    async def broken(_dropped):
        raise RuntimeError("summariser unavailable")

    manager = ContextManager(keep_recent=1, summarise=broken)
    messages = [
        {"role": "system", "content": "sys"},
        *[{"role": "user", "content": "y" * 4000} for _ in range(20)],
    ]
    result = await manager.fit(messages, context_window=8192, max_output_tokens=1000)
    assert result.messages, "a broken summariser must not empty the conversation"
    assert "summary" not in result.strategies_applied


def test_message_text_is_never_rewritten():
    """The line ADR-008 draws against lossy token compression."""
    code = "def f():\n    return {'a': 1}\n"
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": code}]
    pruned, _removed = prune(messages)
    assert pruned[1]["content"] == code


# ── Budgets ─────────────────────────────────────────────────────────────────

def test_budget_records_across_every_dimension():
    tracker = llm_budget.BudgetTracker(BudgetConfig())
    tracker.record(usage=Usage(prompt_tokens=100, completion_tokens=50), cost_usd=0.01,
                   provider="nvidia", model="glm", agent="planner", workflow="wf")

    snapshot = tracker.snapshot()
    assert snapshot["total"]["total_tokens"] == 150
    assert snapshot["by_agent"]["planner"]["requests"] == 1
    assert snapshot["by_provider"]["nvidia"]["cost_usd"] == pytest.approx(0.01)
    assert snapshot["by_model"]["glm"]["prompt_tokens"] == 100
    assert snapshot["by_workflow"]["wf"]["requests"] == 1


def test_budget_alerts_fire_once_per_threshold():
    alerts = []
    tracker = llm_budget.BudgetTracker(BudgetConfig(daily_usd=1.0, alert_at=[0.5], enforce=False))
    tracker.on_alert(alerts.append)

    tracker.record(usage=Usage(), cost_usd=0.60, provider="p", model="m")
    tracker.record(usage=Usage(), cost_usd=0.10, provider="p", model="m")

    assert len(alerts) == 1
    assert alerts[0]["threshold"] == 0.5
    assert alerts[0]["period"] == "daily"


def test_budget_is_advisory_unless_enforcement_is_on():
    """An agency that silently halts at month-end is worse than an overspend."""
    advisory = llm_budget.BudgetTracker(BudgetConfig(daily_usd=1.0, enforce=False))
    advisory.record(usage=Usage(), cost_usd=5.0, provider="p", model="m")
    advisory.check_affordable()          # must not raise

    enforced = llm_budget.BudgetTracker(BudgetConfig(daily_usd=1.0, enforce=True))
    enforced.record(usage=Usage(), cost_usd=5.0, provider="p", model="m")
    with pytest.raises(Exception, match="daily budget exceeded"):
        enforced.check_affordable()


def test_cache_key_separates_requests_with_different_routing_constraints():
    """A free-only request must not be served a paid provider's cached answer.

    The key hashed only the prompt shape, so two requests with incompatible
    provider constraints collided — a silent policy breach, since the stored
    body names the provider the caller rejected.
    """
    base = {"model": "", "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.0}
    free_only = payload_key({**base, "allow_paid": False})
    paid_ok = payload_key({**base, "allow_paid": True})
    excluded = payload_key({**base, "allow_paid": False, "exclude_providers": ["nvidia"]})

    assert free_only != paid_ok
    assert free_only != excluded


def test_dedupe_fingerprint_separates_routing_constraints():
    """Two requests with different provider constraints must not share a call."""
    base = {"model": "", "messages": [{"role": "user", "content": "hi"}]}
    assert request_fingerprint({**base, "allow_paid": False}) != \
        request_fingerprint({**base, "allow_paid": True})
    assert request_fingerprint({**base, "exclude_providers": ["a"]}) != \
        request_fingerprint({**base, "exclude_providers": ["b"]})


# ── Memory bounds — the platform is meant to run for weeks ───────────────────

def test_metrics_label_cardinality_is_bounded():
    """Caller-supplied labels must not grow the registry without bound.

    The gateway accepts an `x-agent` header, so an external client could
    otherwise add one series per request for the life of the process.
    """
    from packages.llm.metrics import MAX_SERIES_PER_METRIC, MetricsRegistry

    registry = MetricsRegistry()
    for i in range(MAX_SERIES_PER_METRIC + 500):
        registry.record_request(
            provider="p", model="m", outcome="success",
            latency_sec=0.1, agent=f"agent-{i}",
        )

    assert len(registry.requests.values) <= MAX_SERIES_PER_METRIC + 1
    # Nothing is lost: the overflow series carries the excess.
    total = sum(registry.requests.values.values())
    assert total == MAX_SERIES_PER_METRIC + 500


def test_metrics_sanitizes_hostile_label_values():
    from packages.llm.metrics import sanitize_label

    assert len(sanitize_label("x" * 5000)) <= 64
    assert "\n" not in sanitize_label("line\nbreak")


def test_budget_prunes_old_periods_and_caps_dimensions():
    """Daily buckets and free-form dimensions must not accumulate forever."""
    from packages.llm import budget as budget_module

    tracker = budget_module.BudgetTracker(BudgetConfig())
    for day in range(budget_module.MAX_DAILY_BUCKETS + 40):
        tracker._dims.daily[f"2026-{(day % 12) + 1:02d}-{(day % 28) + 1:02d}-{day}"]
    tracker._prune()
    assert len(tracker._dims.daily) <= budget_module.MAX_DAILY_BUCKETS

    for i in range(budget_module.MAX_DIMENSION_KEYS + 200):
        tracker.record(usage=Usage(prompt_tokens=1), cost_usd=0.0,
                       provider="p", model="m", agent=f"agent-{i}")
    assert len(tracker._dims.agent) <= budget_module.MAX_DIMENSION_KEYS + 1
    # Every call is still counted, folded into "other" past the cap.
    assert tracker.snapshot()["total"]["requests"] == budget_module.MAX_DIMENSION_KEYS + 200
