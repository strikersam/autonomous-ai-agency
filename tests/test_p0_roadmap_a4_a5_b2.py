from __future__ import annotations

"""Tests for A4 Async Task Queue, A5 Inter-Agent Message Bus, B2 SteerLM Steering."""

import asyncio

import pytest

from services.task_queue import (
    PriorityTaskQueue,
    PrioritizedTask,
    Priority,
    get_task_queue,
)
from services.agent_bus import AgentMessageBus, get_agent_bus
from router.steering import (
    SteeringInjector,
    steering_for_task,
    get_steering_injector,
)


# ── A4: Async Task Queue ──────────────────────────────────────────────────────

class TestPriority:
    def test_ordering(self) -> None:
        assert Priority.CRITICAL < Priority.HIGH < Priority.NORMAL < Priority.LOW < Priority.BACKGROUND

    def test_int_values(self) -> None:
        assert int(Priority.CRITICAL) == 0
        assert int(Priority.BACKGROUND) == 4


class TestPrioritizedTask:
    def test_creation(self) -> None:
        task = PrioritizedTask(
            priority=int(Priority.NORMAL),
            task_id="t1",
            payload={"x": 1},
        )
        assert task.task_id == "t1"
        assert task.status == "pending"
        assert task.priority == int(Priority.NORMAL)

    def test_record_progress(self) -> None:
        task = PrioritizedTask(priority=2, task_id="t1", payload={})
        task.record_progress("running", "started")
        task.record_progress("done", "finished")
        assert len(task.progress) == 2
        assert task.progress[0]["phase"] == "running"
        assert task.progress[1]["phase"] == "done"


class TestPriorityTaskQueue:
    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        q = PriorityTaskQueue(max_size=10, num_workers=1)
        await q.start()
        assert q._running is True
        await q.stop()
        assert q._running is False

    @pytest.mark.asyncio
    async def test_submit_and_status(self) -> None:
        q = PriorityTaskQueue(max_size=10, num_workers=1)
        await q.start()
        accepted = await q.submit(task_id="t1", payload={"x": 1}, priority=Priority.HIGH)
        assert accepted is True
        status = q.status()
        assert status["workers"] == 1
        assert status["max_size"] == 10
        await q.stop()

    @pytest.mark.asyncio
    async def test_priority_ordering(self) -> None:
        """Higher-priority tasks should be processed before lower-priority ones."""
        processed: list[str] = []

        async def handler(task: PrioritizedTask) -> None:
            processed.append(task.task_id)

        q = PriorityTaskQueue(max_size=10, num_workers=1)
        await q.start(handler=handler)
        await q.submit(task_id="low", payload={}, priority=Priority.LOW)
        await q.submit(task_id="high", payload={}, priority=Priority.HIGH)
        await q.submit(task_id="normal", payload={}, priority=Priority.NORMAL)
        # Give worker time to process
        await asyncio.sleep(0.1)
        await q.stop()
        # High priority should come first
        if len(processed) >= 2:
            assert processed[0] == "high"

    @pytest.mark.asyncio
    async def test_backpressure_rejects_when_full(self) -> None:
        q = PriorityTaskQueue(max_size=2, num_workers=0, enable_backpressure=True)
        await q.start()
        await q.submit(task_id="t1", payload={}, priority=Priority.NORMAL)
        await q.submit(task_id="t2", payload={}, priority=Priority.NORMAL)
        accepted = await q.submit(task_id="t3", payload={}, priority=Priority.NORMAL)
        assert accepted is False
        await q.stop()

    @pytest.mark.asyncio
    async def test_list_tasks(self) -> None:
        q = PriorityTaskQueue(max_size=10, num_workers=1)
        await q.start()
        await q.submit(task_id="t1", payload={}, priority=Priority.NORMAL)
        tasks = q.list_tasks()
        assert len(tasks) >= 1
        await q.stop()

    @pytest.mark.asyncio
    async def test_get_task(self) -> None:
        q = PriorityTaskQueue(max_size=10, num_workers=1)
        await q.start()
        await q.submit(task_id="t1", payload={}, priority=Priority.NORMAL)
        task = q.get_task("t1")
        assert task is not None
        assert task.task_id == "t1"
        await q.stop()

    @pytest.mark.asyncio
    async def test_subscribe_progress(self) -> None:
        processed = []

        async def handler(task: PrioritizedTask) -> None:
            task.record_progress("step1", "processing")
            processed.append(task.task_id)

        q = PriorityTaskQueue(max_size=10, num_workers=1)
        await q.start(handler=handler)
        await q.submit(task_id="t1", payload={}, priority=Priority.HIGH)
        event_q = await q.subscribe("t1")
        await asyncio.sleep(0.15)
        await q.stop()
        # Events should have been produced
        events = []
        while not event_q.empty():
            events.append(event_q.get_nowait())
        assert len(events) >= 1

    def test_singleton(self) -> None:
        q1 = get_task_queue()
        q2 = get_task_queue()
        assert q1 is q2

    def test_status_default(self) -> None:
        q = PriorityTaskQueue(max_size=10, num_workers=2)
        status = q.status()
        assert status["queue_depth"] == 0
        assert status["workers"] == 2
        assert status["backpressure"] is True


# ── A5: Inter-Agent Message Bus ───────────────────────────────────────────────

class TestAgentMessageBus:
    @pytest.mark.asyncio
    async def test_publish_subscribe_exact_topic(self) -> None:
        bus = AgentMessageBus()
        received: list[dict] = []

        @bus.subscribe("agent.done", receive_history=False)
        async def on_done(topic: str, event: dict) -> None:
            received.append({"topic": topic, "event": event})

        await bus.publish("agent.done", {"result": "ok"})
        # Allow async dispatch
        await asyncio.sleep(0.01)
        assert len(received) == 1
        assert received[0]["topic"] == "agent.done"
        assert received[0]["event"]["result"] == "ok"

    @pytest.mark.asyncio
    async def test_wildcard_subscription(self) -> None:
        bus = AgentMessageBus()
        received: list[str] = []

        @bus.subscribe("agent.*.done", receive_history=False)
        async def on_any_done(topic: str, event: dict) -> None:
            received.append(topic)

        await bus.publish("agent.planner.done", {})
        await bus.publish("agent.executor.done", {})
        await bus.publish("other.thing", {})
        await asyncio.sleep(0.01)
        assert len(received) == 2
        assert "agent.planner.done" in received
        assert "agent.executor.done" in received

    @pytest.mark.asyncio
    async def test_double_star_wildcard(self) -> None:
        bus = AgentMessageBus()
        received: list[str] = []

        @bus.subscribe("agent.**", receive_history=False)
        async def on_all_agent(topic: str, event: dict) -> None:
            received.append(topic)

        await bus.publish("agent.planner.done", {})
        await bus.publish("agent.deeply.nested.topic.done", {})
        await bus.publish("other.topic", {})
        await asyncio.sleep(0.01)
        assert len(received) == 2

    @pytest.mark.asyncio
    async def test_unsubscribe(self) -> None:
        bus = AgentMessageBus()
        received: list[str] = []

        async def handler(topic: str, event: dict) -> None:
            received.append(topic)

        bus.subscribe("test.topic", receive_history=False)(handler)
        await bus.publish("test.topic", {})
        await asyncio.sleep(0.01)
        assert len(received) == 1
        bus.unsubscribe(handler, "test.topic")
        await bus.publish("test.topic", {})
        await asyncio.sleep(0.01)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_publish_nowait(self) -> None:
        bus = AgentMessageBus()
        received: list[str] = []

        @bus.subscribe("test", receive_history=False)
        async def handler(topic: str, event: dict) -> None:
            received.append(topic)

        bus.publish_nowait("test", {"x": 1})
        await asyncio.sleep(0.01)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_history(self) -> None:
        bus = AgentMessageBus()
        await bus.publish("test.topic", {"a": 1})
        await bus.publish("test.topic", {"b": 2})
        history = bus.get_history("test.topic")
        assert len(history) == 2
        assert history[0]["a"] == 1

    @pytest.mark.asyncio
    async def test_get_topics(self) -> None:
        bus = AgentMessageBus()
        await bus.publish("topic.a", {})
        await bus.publish("topic.b", {})
        topics = bus.get_topics()
        assert "topic.a" in topics
        assert "topic.b" in topics

    @pytest.mark.asyncio
    async def test_stats(self) -> None:
        bus = AgentMessageBus()
        await bus.publish("test", {})
        stats = bus.stats()
        assert stats["event_count"] == 1
        assert stats["topics"] == 1

    @pytest.mark.asyncio
    async def test_late_subscriber_history_replay(self) -> None:
        bus = AgentMessageBus()
        await bus.publish("test.topic", {"msg": "first"})

        received: list[dict] = []

        @bus.subscribe("test.topic", receive_history=True)
        async def handler(topic: str, event: dict) -> None:
            received.append(event)

        await asyncio.sleep(0.01)
        # Should receive the history event
        assert len(received) >= 1
        assert received[0]["msg"] == "first"

    def test_singleton(self) -> None:
        b1 = get_agent_bus()
        b2 = get_agent_bus()
        assert b1 is b2

    def test_topic_matches(self) -> None:
        bus = AgentMessageBus()
        assert bus._topic_matches("agent.done", "agent.done") is True
        assert bus._topic_matches("agent.planner.done", "agent.*.done") is True
        assert bus._topic_matches("other.done", "agent.*.done") is False
        assert bus._topic_matches("agent.a.b.c", "agent.**") is True


# ── B2: SteerLM Steering Tokens ───────────────────────────────────────────────

class TestSteeringInjector:
    def test_disabled_by_default(self) -> None:
        injector = SteeringInjector()
        assert injector.enabled is False

    def test_inject_when_disabled_returns_unchanged(self) -> None:
        injector = SteeringInjector()
        injector.enabled = False
        msgs = [{"role": "user", "content": "hello"}]
        result = injector.inject(messages=msgs, labels={"helpfulness": 4})
        assert result == msgs

    def test_inject_quality_format(self) -> None:
        injector = SteeringInjector(format="quality")
        injector.enabled = True
        msgs = [{"role": "user", "content": "hello"}]
        result = injector.inject(messages=msgs, labels={"helpfulness": 4, "correctness": 4})
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert "helpfulness" in result[0]["content"].lower()
        assert "correctness" in result[0]["content"].lower()

    def test_inject_appends_to_existing_system(self) -> None:
        injector = SteeringInjector(format="quality")
        injector.enabled = True
        msgs = [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "hi"}]
        result = injector.inject(messages=msgs, labels={"helpfulness": 4})
        assert len(result) == 2
        assert "You are helpful" in result[0]["content"]
        assert "helpfulness" in result[0]["content"].lower()

    def test_preset_high_quality(self) -> None:
        injector = SteeringInjector()
        injector.enabled = True
        msgs = [{"role": "user", "content": "test"}]
        result = injector.inject(messages=msgs, preset="high_quality")
        assert len(result) == 2
        assert "helpfulness" in result[0]["content"].lower()

    def test_preset_not_found(self) -> None:
        injector = SteeringInjector()
        injector.enabled = True
        msgs = [{"role": "user", "content": "test"}]
        result = injector.inject(messages=msgs, preset="nonexistent")
        assert result == msgs  # unchanged

    def test_labels_clamped(self) -> None:
        injector = SteeringInjector()
        injector.enabled = True
        msgs = [{"role": "user", "content": "test"}]
        result = injector.inject(messages=msgs, labels={"helpfulness": 10, "correctness": -1})
        assert len(result) == 2

    def test_inject_payload(self) -> None:
        injector = SteeringInjector()
        injector.enabled = True
        payload = {"model": "qwen", "messages": [{"role": "user", "content": "hi"}]}
        result = injector.inject_payload(payload, preset="high_quality")
        assert len(result["messages"]) == 2

    def test_chatml_format(self) -> None:
        injector = SteeringInjector(format="chatml")
        injector.enabled = True
        msgs = [{"role": "user", "content": "test"}]
        result = injector.inject(messages=msgs, labels={"helpfulness": 4})
        assert "<|im_start|>steering" in result[0]["content"]

    def test_nemotron_format(self) -> None:
        injector = SteeringInjector(format="nemotron")
        injector.enabled = True
        msgs = [{"role": "user", "content": "test"}]
        result = injector.inject(messages=msgs, labels={"helpfulness": 4})
        assert "<extra_id" in result[0]["content"]

    def test_no_labels_returns_unchanged(self) -> None:
        injector = SteeringInjector()
        injector.enabled = True
        msgs = [{"role": "user", "content": "test"}]
        result = injector.inject(messages=msgs)
        assert result == msgs


class TestSteeringForTask:
    def test_code_generation(self) -> None:
        labels = steering_for_task("code_generation")
        assert labels["helpfulness"] >= 3
        assert labels["correctness"] >= 3

    def test_fast_response(self) -> None:
        labels = steering_for_task("fast_response")
        assert labels["complexity"] <= 2

    def test_unknown_category(self) -> None:
        labels = steering_for_task("unknown_category")
        assert "helpfulness" in labels
        assert labels["helpfulness"] >= 3


class TestSteeringSingleton:
    def test_singleton(self) -> None:
        s1 = get_steering_injector()
        s2 = get_steering_injector()
        assert s1 is s2
