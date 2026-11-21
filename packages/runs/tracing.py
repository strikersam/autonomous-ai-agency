"""packages/runs/tracing.py — correlate a durable run with its trace.

``open_run_span`` starts one span per run attempt through ``services.otel_tracing``
(a no-op span when tracing is off) and sets ``run.id``, ``run.parent_id``,
``run.root_id`` and ``task.id`` on it. Every attribute value goes through
``redact_secrets`` first, so a secret-shaped id or label never reaches the exporter.

One trace per run attempt: a child run is a separate trace linked to its tree by
the ``run.root_id`` attribute (query by it to see the whole tree). Stitching child
runs into the root's trace id needs context propagation across the dispatcher
hand-off and is left for a later phase. Tracing never fails a run.
"""
from __future__ import annotations

import logging
from typing import Any

from packages.runs.models import RunRecord
from packages.security.redact import redact_secrets

log = logging.getLogger("qwen-proxy")

TRACER_NAME = "runs"


def run_attributes(run: RunRecord) -> dict[str, str]:
    """The correlation attributes of *run*, redacted, with unset ids left out."""
    raw = {
        "run.id": run.run_id,
        "run.parent_id": run.parent_run_id,
        "run.root_id": run.root_run_id or run.run_id,
        "task.id": run.task_id,
    }
    return {key: redact_secrets(str(value)) for key, value in raw.items() if value}


def open_run_span(run: RunRecord) -> Any:
    """Start the run's span and set its attributes; a no-op span when tracing is off. Never raises."""
    try:
        from services.otel_tracing import get_tracer

        span = get_tracer(TRACER_NAME).start_span("run.attempt")
        for key, value in run_attributes(run).items():
            span.set_attribute(key, value)
        return span
    except Exception:
        log.debug("run tracing: could not open the span of run %s", run.run_id, exc_info=True)
        return None


def span_ids(span: Any) -> tuple[str | None, str | None]:
    """Hex ``(trace_id, span_id)`` of a real span, ``(None, None)`` for a no-op one."""
    try:
        ctx = span.get_span_context()
        if not ctx.is_valid:
            return None, None
        return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
    except Exception:
        return None, None


def close_run_span(span: Any, state: str | None = None) -> None:
    """End the span, tagging the state the run settled in. Never raises."""
    if span is None:
        return
    try:
        if state:
            span.set_attribute("run.state", state)
        span.end()
    except Exception:
        log.debug("run tracing: could not end a run span", exc_info=True)
