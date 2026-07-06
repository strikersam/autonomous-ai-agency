"""Optional Langfuse traces for chat requests (commercial-equivalent metadata)."""

from __future__ import annotations

import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None

from commercial_equivalent import estimate_commercial_equivalent_usd

log = logging.getLogger("qwen-proxy")

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _env_val(name: str) -> str:
    """Read env; strip whitespace and a single pair of surrounding quotes (common copy-paste)."""
    raw = os.environ.get(name, "") or ""
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        v = v[1:-1].strip()
    return v


def _langfuse_enabled() -> bool:
    return bool(_env_val("LANGFUSE_PUBLIC_KEY") and _env_val("LANGFUSE_SECRET_KEY"))


def _base_url() -> str:
    host = _env_val("LANGFUSE_BASE_URL") or _env_val("LANGFUSE_HOST")
    if not host:
        host = "https://cloud.langfuse.com"
    return host.rstrip("/")


def _truncate_for_langfuse(obj: Any, max_chars: int = 48_000) -> Any:
    """Avoid oversized payloads that make Langfuse reject the event."""
    if obj is None:
        return None
    if isinstance(obj, str):
        if len(obj) <= max_chars:
            return obj
        return obj[: max_chars - 20] + "\n…[truncated]"
    try:
        s = json.dumps(obj, default=str)
    except TypeError:
        s = str(obj)
    if len(s) <= max_chars:
        return json.loads(s) if s.startswith(("{", "[")) else s
    return s[: max_chars - 20] + "\n…[truncated]"


def get_langfuse_client():  # type: ignore[no-untyped-def]
    if not _langfuse_enabled():
        return None
    try:
        from langfuse import Langfuse
    except ImportError:
        log.warning("Langfuse env vars set but langfuse package not installed")
        return None
    host = _base_url()
    pk, sk = _env_val("LANGFUSE_PUBLIC_KEY"), _env_val("LANGFUSE_SECRET_KEY")
    try:
        fa = int(_env_val("LANGFUSE_FLUSH_AT") or "0")
        if fa > 0:
            return Langfuse(public_key=pk, secret_key=sk, host=host, flush_at=fa)
    except (TypeError, ValueError):
        pass
    return Langfuse(public_key=pk, secret_key=sk, host=host)


def test_langfuse_connection() -> tuple[bool, str]:
    """Ping Langfuse API with project keys (Basic auth: public_key, secret_key)."""
    if not _langfuse_enabled():
        return False, "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set"
    base = _base_url()
    pk, sk = _env_val("LANGFUSE_PUBLIC_KEY"), _env_val("LANGFUSE_SECRET_KEY")
    health_paths = ("/api/public/health", "/api/public/projects")
    last_err = ""
    for path in health_paths:
        try:
            r = httpx.get(
                f"{base}{path}",
                auth=(pk, sk),
                timeout=15.0,
            )
            if r.status_code == 200:
                return True, f"OK {path} ({base})"
            last_err = f"{path}: HTTP {r.status_code} {r.text[:200]}"
        except Exception as e:
            last_err = f"{path}: {e}"
    return False, last_err or "request failed"


def _department_trace_tags(department: str) -> list[str]:
    d = (department or "").strip().replace(" ", "-")
    slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in d)[:64]
    if not slug:
        slug = "unknown"
    return [f"dept:{slug}"]


def _emit_langfuse_http_sync(
    *,
    email: str,
    department: str,
    key_id: str | None,
    model: str,
    messages: Any,
    output_text: str,
    prompt_tokens: int,
    completion_tokens: int,
    meta: dict[str, Any],
    task_name: str,
    session_id: str | None = None,
) -> None:
    base = _base_url()
    pk, sk = _env_val("LANGFUSE_PUBLIC_KEY"), _env_val("LANGFUSE_SECRET_KEY")
    trace_id = str(uuid.uuid4())
    gen_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    tags = _department_trace_tags(department)
    if session_id:
        tags = tags + [f"session:{session_id}"]

    trace_body: dict[str, Any] = {
        "id": trace_id,
        "timestamp": now,
        "name": task_name,
        "userId": email,
        "metadata": {"department": department},
        "tags": tags,
    }
    if session_id:
        trace_body["sessionId"] = session_id
    gen_body: dict[str, Any] = {
        "id": gen_id,
        "traceId": trace_id,
        "name": task_name,
        "startTime": now,
        "endTime": now,
        "model": model or "unknown",
        "input": _truncate_for_langfuse(messages),
        "output": _truncate_for_langfuse(output_text),
        "metadata": meta,
        "usage": {
            "input": prompt_tokens,
            "output": completion_tokens,
            "total": prompt_tokens + completion_tokens,
            "unit": "TOKENS",
        },
    }

    with httpx.Client(timeout=30.0) as client:
        t = client.post(f"{base}/api/public/traces", json=trace_body, auth=(pk, sk))
        if t.status_code >= 400:
            raise RuntimeError(f"trace HTTP {t.status_code}: {t.text[:500]}")
        g = client.post(f"{base}/api/public/generations", json=gen_body, auth=(pk, sk))
        if g.status_code >= 400:
            raise RuntimeError(f"generation HTTP {g.status_code}: {g.text[:500]}")


# Backward-compatible alias
_emit_langfuse_http = _emit_langfuse_http_sync


def _emit_sdk(
    lf: Any,
    *,
    email: str,
    department: str,
    model: str,
    session_id: str | None = None,
    messages: Any,
    output_text: str,
    prompt_tokens: int,
    completion_tokens: int,
    meta: dict[str, Any],
    task_name: str,
) -> None:
    msg_in = _truncate_for_langfuse(messages)
    out = _truncate_for_langfuse(output_text)
    try:
        trace = lf.trace(
            name=task_name,
            user_id=email,
            metadata={"department": department},
            tags=_department_trace_tags(department),
        )
    except TypeError:
        trace = lf.trace(
            name=task_name,
            user_id=email,
            metadata={"department": department},
        )
    trace.generation(
        name=task_name,
        model=model or "unknown",
        input=msg_in,
        output=out,
        usage={
            "input": prompt_tokens,
            "output": completion_tokens,
            "total": prompt_tokens + completion_tokens,
        },
        metadata=meta,
    )
    lf.flush()


def emit_chat_observation(
    *,
    email: str,
    department: str,
    key_id: str | None,
    model: str,
    messages: Any,
    output_text: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int = 0,
    ttft_ms: int = 0,
    routing_meta: dict[str, Any] | None = None,
    task_name: str = "chat completion",
    session_id: str | None = None,
) -> None:
    """Record one generation in Langfuse (SDK first, then REST fallback).

    Args:
        latency_ms:    Total wall-clock time from request receipt to last byte (ms).
        ttft_ms:       Time to first token (ms). 0 if not measured.
        routing_meta:  Optional dict from ``RoutingDecision.to_meta()`` — records
                       model selection mode, task category, selection source, etc.
                       Pass ``None`` to omit routing fields (legacy callers).
        task_name:     The name of the action (e.g. "chat completion", "agent planning").
    """
    if not _langfuse_enabled():
        return
    cost_usd, eq = estimate_commercial_equivalent_usd(model, prompt_tokens, completion_tokens)

    # Real infrastructure cost (electricity + amortised hardware)
    infra_meta: dict[str, Any] = {}
    if latency_ms > 0:
        try:
            from infra_cost import compute_request_cost
            infra = compute_request_cost(latency_ms)
            infra_meta = infra.as_dict()
        except Exception:
            pass

    tokens_per_sec = 0.0
    if latency_ms > 0 and completion_tokens > 0:
        tokens_per_sec = round(completion_tokens / (latency_ms / 1000.0), 2)

    meta: dict[str, Any] = {
        "department": department,
        "local_model": model,
        "estimated_commercial_equivalent_usd": round(cost_usd, 6),
        "estimated_savings_vs_commercial_usd": round(cost_usd, 6),
        "latency_ms": latency_ms,
        "ttft_ms": ttft_ms,
        "tokens_per_sec": tokens_per_sec,
        **infra_meta,
    }
    if key_id:
        meta["key_id"] = key_id
    if eq:
        meta["commercial_reference_model"] = eq.commercial_name
    if routing_meta:
        meta.update(routing_meta)

    # Local Metrics Persistence (for Dashboard)
    mongo_url = os.environ.get("MONGO_URL")
    if mongo_url and MongoClient:
        try:
            db_name = os.environ.get("DB_NAME", "llm_wiki_dashboard")
            client = MongoClient(mongo_url, serverSelectionTimeoutMS=2000)
            db = client[db_name]
            db.local_metrics.insert_one({
                "timestamp": datetime.now(timezone.utc),
                "email": email,
                "department": department,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms": latency_ms,
                "cost_usd": round(cost_usd, 6),
                "task_name": task_name,
                "trace_id": meta.get("trace_id") or str(uuid.uuid4())
            })
            client.close()
        except Exception as e:
            log.debug("Local metrics persistence failed: %s", e)

    use_http = _env_val("LANGFUSE_USE_HTTP_ONLY").lower() in ("1", "true", "yes")
    if use_http:
        try:
            _emit_langfuse_http(
                email=email,
                department=department,
                key_id=key_id,
                model=model,
                messages=messages,
                output_text=output_text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                meta=meta,
                task_name=task_name,
            )
        except Exception as e:
            log.warning("Langfuse HTTP-only emit failed: %s", e)
        return

    lf = get_langfuse_client()
    if lf is None:
        return
    try:
        _emit_sdk(
            lf,
            email=email,
            department=department,
            model=model,
            messages=messages,
            output_text=output_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            meta=meta,
            task_name=task_name,
        )
    except Exception as e:
        log.info("Langfuse SDK emit failed, trying HTTP API: %s", e)
        try:
            _emit_langfuse_http(
                email=email,
                department=department,
                key_id=key_id,
                model=model,
                messages=messages,
                output_text=output_text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                meta=meta,
                task_name=task_name,
            )
        except Exception as e2:
            log.warning("Langfuse HTTP fallback failed: %s", e2)


# ── Agency-wide observation emitter ──────────────────────────────────────────

def emit_agency_observation(
    *,
    operation: str,
    actor: str = "system",
    task_id: str | None = None,
    task_title: str | None = None,
    task_type: str | None = None,
    status: str = "ok",
    duration_ms: int = 0,
    model: str | None = None,
    input_text: str | None = None,
    output_text: str | None = None,
    metadata: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Record an agency platform operation in Langfuse.

    Unlike ``emit_chat_observation`` (which is chat-specific), this function
    traces ANY agency operation: CEO directives, task execution, SAM voice,
    workflow orchestrator phases, scheduler ticks, runtime dispatch, etc.

    The trace appears in Langfuse under the ``operation`` name with tags
    ``agency`` + the operation type, so you can filter the dashboard by
    agency subsystem.

    Args:
        operation:    Short name — "ceo_directive", "task_execute", "sam_voice",
                      "orchestrator_phase", "scheduler_tick", "runtime_dispatch"
        actor:        Who triggered it — "system", "ceo", "user", "scheduler"
        task_id:      Task ID if this is a task-related operation
        task_title:   Task title (truncated to 100 chars for readability)
        task_type:    Task type — "code_generation", "code_review", etc.
        status:       "ok", "failed", "blocked", "deferred", "skipped"
        duration_ms:  How long the operation took
        model:        LLM model used (if applicable)
        input_text:   Input prompt/instruction (truncated to 2000 chars)
        output_text:  Output result (truncated to 2000 chars)
        metadata:     Additional context dict
        error:        Error message if status="failed"
    """
    if not _langfuse_enabled():
        return

    # Build the metadata payload
    meta: dict[str, Any] = {
        "operation": operation,
        "actor": actor,
        "status": status,
        "source": "agency_platform",
        "trace_id": str(uuid.uuid4()),
    }
    if task_id:
        meta["task_id"] = task_id
    if task_title:
        meta["task_title"] = task_title[:100]
    if task_type:
        meta["task_type"] = task_type
    if model:
        meta["model"] = model
    if error:
        meta["error"] = error[:500]
    if metadata:
        meta.update(metadata)

    # Truncate input/output for Langfuse payload limits
    safe_input = _truncate_for_langfuse(input_text, 2000) if input_text else None
    safe_output = _truncate_for_langfuse(output_text, 2000) if output_text else None

    # Use the HTTP emitter directly (no LLM token counting needed for
    # agency operations — they're not chat completions)
    try:
        _emit_langfuse_http(
            email=f"{actor}@agency.internal",
            department=operation,
            key_id=None,
            model=model or "agency-internal",
            messages=[{"role": "user", "content": safe_input or "(no input)"}],
            output_text=safe_output or "(no output)",
            prompt_tokens=0,
            completion_tokens=0,
            meta=meta,
            task_name=f"agency:{operation}",
        )
    except Exception as e:
        log.debug("Langfuse agency observation emit failed (non-fatal): %s", e)
