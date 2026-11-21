"""Phase 6: trace correlation attributes of a run (packages/runs/tracing.py)."""
from __future__ import annotations

import pytest

from packages.runs import task_binding, tracing
from packages.runs.models import RunRecord
from tests._runs_task_fixtures import FakeRuntime, coordinator, queued_task, reset_process_state, sqlite_pair


class FakeSpan:
    def __init__(self) -> None:
        self.attrs: dict[str, str] = {}
        self.ended = False

    def set_attribute(self, key, value):
        self.attrs[key] = value

    def end(self):
        self.ended = True


class FakeTracer:
    def __init__(self) -> None:
        self.spans: list[FakeSpan] = []

    def start_span(self, name, **kwargs):
        span = FakeSpan()
        self.spans.append(span)
        return span


@pytest.fixture
def tracer(monkeypatch):
    fake = FakeTracer()
    import services.otel_tracing as otel
    monkeypatch.setattr(otel, "get_tracer", lambda name="x": fake)
    return fake


def test_correlation_attributes_are_set(tracer):
    run = RunRecord(run_id="run_c", parent_run_id="run_p", root_run_id="run_r", task_id="t1")
    span = tracing.open_run_span(run)
    assert span.attrs == {"run.id": "run_c", "run.parent_id": "run_p",
                          "run.root_id": "run_r", "task.id": "t1"}
    tracing.close_run_span(span, "failed")
    assert span.ended and span.attrs["run.state"] == "failed"


def test_a_root_run_is_its_own_root_and_leaves_out_unset_ids(tracer):
    span = tracing.open_run_span(RunRecord(run_id="run_a"))
    assert span.attrs == {"run.id": "run_a", "run.root_id": "run_a"}


def test_secret_shaped_values_are_redacted(tracer):
    secret = "sk-ant-api03-" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4"
    span = tracing.open_run_span(RunRecord(run_id="run_s", task_id=f"token={secret}"))
    assert secret not in span.attrs["task.id"]


def test_tracing_off_is_a_noop_and_never_raises():
    span = tracing.open_run_span(RunRecord(run_id="run_n"))
    tracing.close_run_span(span, "succeeded")
    assert tracing.span_ids(span) == (None, None)
    tracing.close_run_span(None)


def test_in_memory_exporter_sees_the_attributes():
    sdk = pytest.importorskip("opentelemetry.sdk.trace")
    export = pytest.importorskip("opentelemetry.sdk.trace.export")
    memory = pytest.importorskip("opentelemetry.sdk.trace.export.in_memory_span_exporter")
    exporter = memory.InMemorySpanExporter()
    provider = sdk.TracerProvider()
    provider.add_span_processor(export.SimpleSpanProcessor(exporter))
    span = provider.get_tracer("t").start_span("run.attempt")
    for key, value in tracing.run_attributes(RunRecord(run_id="run_m", task_id="t9")).items():
        span.set_attribute(key, value)
    assert tracing.span_ids(span)[0] and len(tracing.span_ids(span)[0]) == 32
    span.end()
    assert dict(exporter.get_finished_spans()[0].attributes)["run.id"] == "run_m"


@pytest.mark.anyio
async def test_the_binding_opens_and_closes_the_span(tmp_path, monkeypatch, tracer):
    reset_process_state(monkeypatch)
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "true")
    async with sqlite_pair(tmp_path) as (store, _):
        task = await queued_task(store)
        done = await coordinator(store, FakeRuntime()).execute(task.task_id)
        assert len(tracer.spans) == 1
        span = tracer.spans[0]
        assert span.attrs["run.id"] == done.current_run_id and span.attrs["task.id"] == task.task_id
        assert span.ended
        assert task_binding.active_bindings() == []


def test_a_span_whose_attributes_fail_is_ended_not_leaked(monkeypatch):
    from types import SimpleNamespace

    from packages.runs import tracing
    from packages.runs.models import RunRecord

    ended = []

    class _Span:
        def set_attribute(self, *_):
            raise RuntimeError("exporter broke")

        def end(self):
            ended.append(True)

    import services.otel_tracing as otel
    monkeypatch.setattr(otel, "get_tracer",
                        lambda *_: SimpleNamespace(start_span=lambda *_a, **_k: _Span()))
    assert tracing.open_run_span(RunRecord(owner_id="a")) is None
    assert ended == [True]
