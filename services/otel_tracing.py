from __future__ import annotations

"""OpenTelemetry Distributed Tracing (D3 roadmap item).

Instrumentation for distributed tracing across the proxy, agent, and
backend components.  Uses OpenTelemetry SDK with OTLP exporter.

Components:
- TracerFactory: creates and configures OpenTelemetry tracers
- FastAPI middleware: auto-instruments HTTP requests with span context
- Agent span helpers: create spans for each agent phase (plan/execute/verify)
- OTLP exporter: sends traces to a collector (default: localhost:4317)
- Trace ID correlation: links OTEL trace IDs with Langfuse observation IDs

Usage::

    from services.otel_tracing import get_tracer, span_context_from_request

    tracer = get_tracer("qwen-proxy")

    with tracer.start_as_current_span("agent.plan") as span:
        span.set_attribute("model", planner_model)
        plan = await agent.plan(...)
"""

import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable

log = logging.getLogger("qwen-proxy")

# ── Configuration ──────────────────────────────────────────────────────────────

_OTEL_ENABLED = os.environ.get("OTEL_ENABLED", "false").strip().lower() in ("true", "1", "yes")
_OTEL_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "local-llm-server")
_OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
_OTEL_SAMPLING_RATE = float(os.environ.get("OTEL_SAMPLING_RATE", "1.0"))


# ── No-op stubs (used when OTEL is disabled or SDK not installed) ────────────


class _NoOpSpan:
    """No-op span that silently discards all operations."""

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    async def __aenter__(self) -> _NoOpSpan:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_attributes(self, attrs: dict[str, Any]) -> None:
        pass

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def end(self) -> None:
        pass


class _NoOpTracer:
    """No-op tracer that returns NoOpSpan instances."""

    def start_span(self, name: str, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()

    def start_as_current_span(self, name: str, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()


_NOOP_TRACER = _NoOpTracer()
_NOOP_SPAN = _NoOpSpan()


# ── Trace context dataclass ──────────────────────────────────────────────────


@dataclass
class TraceContext:
    """Portable trace context that can be passed across async boundaries."""

    trace_id: str
    span_id: str
    is_sampled: bool = True
    extra_attributes: dict[str, str] = field(default_factory=dict)


# ── Tracer factory ───────────────────────────────────────────────────────────


class TracerFactory:
    """Lazy-initialised OpenTelemetry tracer provider.

    Only imports the OTEL SDK when first accessed, so environments without
    the SDK installed can still import this module without errors.
    """

    def __init__(self) -> None:
        self._initialised = False
        self._tracers: dict[str, Any] = {}

    def get_tracer(self, name: str) -> Any:
        """Return a tracer for the given name. Falls back to NoOpTracer if OTEL is disabled."""
        if not _OTEL_ENABLED:
            return _NOOP_TRACER

        if name in self._tracers:
            return self._tracers[name]

        try:
            tracer = self._init_tracer(name)
            self._tracers[name] = tracer
            return tracer
        except ImportError:
            log.debug("OpenTelemetry SDK not installed — using no-op tracer")
            return _NOOP_TRACER
        except Exception as exc:
            log.warning("Failed to initialise OTEL tracer '%s': %s", name, exc)
            return _NOOP_TRACER

    def _init_tracer(self, name: str) -> Any:
        """Initialise the OTEL tracer provider on first use."""
        import opentelemetry.trace as otel_trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.semconv.resource import ResourceAttributes

        # Create resource with service metadata
        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: _OTEL_SERVICE_NAME,
            ResourceAttributes.SERVICE_VERSION: os.environ.get("APP_VERSION", "0.0.0"),
        })

        # Create tracer provider with batch exporter
        exporter = OTLPSpanExporter(
            endpoint=_OTEL_EXPORTER_OTLP_ENDPOINT,
            insecure=True,  # Use insecure for local collector
        )
        provider = TracerProvider(
            resource=resource,
            sampler=otel_trace.sampling.ALWAYS_ON if _OTEL_SAMPLING_RATE >= 1.0 else
                     otel_trace.sampling.TraceIdRatioBased(_OTEL_SAMPLING_RATE),
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        otel_trace.set_tracer_provider(provider)

        log.info(
            "OTEL tracer initialised: service=%s endpoint=%s sampling=%.2f",
            _OTEL_SERVICE_NAME, _OTEL_EXPORTER_OTLP_ENDPOINT, _OTEL_SAMPLING_RATE,
        )

        return otel_trace.get_tracer(name)

    def shutdown(self) -> None:
        """Gracefully shut down the tracer provider, flushing pending spans."""
        try:
            import opentelemetry.trace as otel_trace
            provider = otel_trace.get_tracer_provider()
            if hasattr(provider, "shutdown"):
                provider.shutdown()
        except Exception:  # nosec B110 — OTEL shutdown is best-effort
            pass


_factory: TracerFactory | None = None


def get_tracer(name: str = _OTEL_SERVICE_NAME) -> Any:
    """Return an OpenTelemetry tracer for the given name."""
    global _factory
    if _factory is None:
        _factory = TracerFactory()
    return _factory.get_tracer(name)


def shutdown_tracing() -> None:
    """Shut down tracing (flush pending spans)."""
    global _factory
    if _factory:
        _factory.shutdown()
        _factory = None


# ── FastAPI middleware ────────────────────────────────────────────────────────


def otel_middleware_factory() -> Any:
    """Create a FastAPI-compatible OTEL middleware.

    Usage::

        from services.otel_tracing import otel_middleware_factory
        from fastapi import FastAPI

        app = FastAPI()
        middleware = otel_middleware_factory()
        if middleware:
            app.add_middleware(middleware)
    """
    if not _OTEL_ENABLED:
        return None

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        return FastAPIInstrumentor
    except ImportError:
        log.debug("opentelemetry-instrumentation-fastapi not installed")
        return None


# ── Span context extraction ──────────────────────────────────────────────────


def span_context_from_request(request: Any) -> TraceContext | None:
    """Extract trace context from an incoming HTTP request.

    Looks for W3C Trace Context headers (traceparent, tracestate)
    and returns a TraceContext if found.
    """
    if not _OTEL_ENABLED:
        return None

    traceparent = request.headers.get("traceparent") if hasattr(request, "headers") else None
    if not traceparent:
        return None

    try:
        # Parse W3C traceparent: 00-<trace_id>-<span_id>-<flags>
        parts = traceparent.split("-")
        if len(parts) >= 4 and parts[0] == "00":
            return TraceContext(
                trace_id=parts[1],
                span_id=parts[2],
                is_sampled=parts[3] != "00",
            )
    except Exception:  # nosec B110 — OTEL SDK import optional
        pass

    return None


def span_context_to_headers(tc: TraceContext) -> dict[str, str]:
    """Convert a TraceContext to W3C trace context HTTP headers."""
    flags = "01" if tc.is_sampled else "00"
    return {
        "traceparent": f"00-{tc.trace_id}-{tc.span_id}-{flags}",
    }


# ── Agent span decorator ─────────────────────────────────────────────────────


def traced(name: str, *, attributes: dict[str, Any] | None = None):
    """Decorator to wrap an async function with an OTEL span.

    Usage::

        @traced("agent.plan", attributes={"phase": "planning"})
        async def plan(self, instruction: str) -> AgentPlan:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer("qwen-agent")
            if tracer is _NOOP_TRACER:
                return await func(*args, **kwargs)

            with tracer.start_as_current_span(name) as span:
                if attributes:
                    span.set_attributes(attributes)
                span.set_attribute("function", func.__name__)
                start = time.monotonic()
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(otel_status_ok())
                    return result
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(otel_status_error(str(exc)))
                    raise
                finally:
                    span.set_attribute("duration_ms", (time.monotonic() - start) * 1000)

        return wrapper
    return decorator


def otel_status_ok() -> Any:
    """Return an OTEL StatusCode.OK if available, else None."""
    try:
        from opentelemetry.trace import Status, StatusCode
        return Status(StatusCode.OK)
    except ImportError:
        return None


def otel_status_error(message: str) -> Any:
    """Return an OTEL StatusCode.ERROR if available, else None."""
    try:
        from opentelemetry.trace import Status, StatusCode
        return Status(StatusCode.ERROR, message)
    except ImportError:
        return None


# ── Trace ID correlation with Langfuse ────────────────────────────────────────


_current_trace_id: str | None = None


def set_current_trace_id(trace_id: str) -> None:
    """Set the current trace ID for Langfuse correlation."""
    global _current_trace_id
    _current_trace_id = trace_id


def get_current_trace_id() -> str | None:
    """Get the current trace ID for Langfuse correlation."""
    return _current_trace_id


def langfuse_metadata_with_trace() -> dict[str, str]:
    """Return metadata dict for Langfuse observation with current trace ID."""
    tid = get_current_trace_id()
    if tid:
        return {"otel_trace_id": tid}
    return {}
