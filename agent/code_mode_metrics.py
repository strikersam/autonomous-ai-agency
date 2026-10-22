from __future__ import annotations

"""Phase 2 of Code Mode: measure whether ``run_code`` pays for itself.

Each executed step is assigned to an arm. ``on`` steps get ``run_code`` in their
tool prompt. ``holdout`` steps (``AGENT_CODE_MODE_HOLDOUT_PERCENT`` of them,
chosen by a stable hash of session + step) do not, which gives a comparison
group from the same traffic. ``off`` means the operator switched Code Mode off;
those steps are recorded too but kept apart from the A/B comparison.

Per step we record what Code Mode is supposed to change: tool-selection LLM
calls, the prompt characters those calls sent (tokens estimated as chars/4),
wall time, how many selections failed to parse, and the step outcome. Per
``run_code`` program we record whether it ran and, if not, which kind of error
it hit. Samples hold numbers and short enums only, never prompt or tool text.

Samples live in a bounded in-memory ring and, when state persistence is on, in
the ``code_mode_samples`` collection with a 30-day TTL so a restart or deploy
does not wipe the experiment. :func:`summary` compares the arms and says
whether there is enough data to call it.
"""

import asyncio
import contextvars
import hashlib
import logging
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from statistics import mean, median, pstdev
from typing import Any

from packages.storage import state_persistence as _persist

log = logging.getLogger("qwen-proxy")

COLLECTION = "code_mode_samples"
TTL_DAYS = 30
MAX_MEMORY_SAMPLES = 2000
MIN_SAMPLES_PER_ARM = 30
ARM_ON, ARM_HOLDOUT, ARM_OFF = "on", "holdout", "off"

_ERROR_KINDS = (
    ("syntax error", "syntax"),
    ("is not supported", "unsupported"),
    ("not callable from run_code", "tool_not_allowed"),
    ("timed out", "timeout"),
    ("exceeded", "limit"),
    ("too large", "limit"),
    ("longer than", "limit"),
    ("more than", "limit"),
    ("would exceed", "limit"),
    ("switched off", "disabled"),
)


@dataclass
class StepStats:
    """Counters for one step, filled in by the executor tool loop."""

    arm: str
    started: float = field(default_factory=time.monotonic)
    llm_calls: int = 0
    prompt_chars: int = 0
    selection_errors: int = 0
    run_code_programs: int = 0
    run_code_ok: int = 0
    run_code_inner_calls: int = 0
    run_code_errors: dict[str, int] = field(default_factory=dict)

    def record_selection(self, messages: list[dict[str, Any]]) -> None:
        self.llm_calls += 1
        self.prompt_chars += sum(len(str(m.get("content", ""))) for m in messages)

    def record_program(self, ok: bool, inner_calls: int, error: str | None) -> None:
        self.run_code_programs += 1
        self.run_code_inner_calls += inner_calls
        if ok:
            self.run_code_ok += 1
            return
        kind = classify_error(error)
        self.run_code_errors[kind] = self.run_code_errors.get(kind, 0) + 1


_current: contextvars.ContextVar[StepStats | None] = contextvars.ContextVar("code_mode_step", default=None)


def classify_error(error: str | None) -> str:
    """Bucket a run_code error message into a short, text-free kind."""
    text = (error or "").lower()
    for needle, kind in _ERROR_KINDS:
        if needle in text:
            return kind
    return "runtime"


def assign_arm(session_id: str | None, step_id: Any) -> str:
    """Stable arm for one step: same session + step always lands in the same arm."""
    from agent.code_mode import code_mode_enabled, holdout_percent

    if not code_mode_enabled():
        return ARM_OFF
    pct = holdout_percent()
    if pct <= 0:
        return ARM_ON
    digest = hashlib.sha256(f"{session_id or ''}:{step_id}".encode()).digest()
    return ARM_HOLDOUT if digest[0] * 100 // 256 < pct else ARM_ON


def begin_step(arm: str) -> contextvars.Token:
    """Start counting for the step running in this task."""
    return _current.set(StepStats(arm=arm))


def current() -> StepStats | None:
    """The step being counted in this task, if any."""
    return _current.get()


def current_arm() -> str | None:
    stats = _current.get()
    return stats.arm if stats else None


def end_step(token: contextvars.Token, status: str) -> dict[str, Any] | None:
    """Finish the step, store its sample, and return it."""
    stats = _current.get()
    _current.reset(token)
    if stats is None:
        return None
    sample = {
        "ts": time.time(),
        "arm": stats.arm,
        "status": str(status or "unknown")[:32],
        "wall_s": round(time.monotonic() - stats.started, 3),
        **{k: v for k, v in asdict(stats).items() if k not in ("arm", "started")},
    }
    try:
        get_store().add(sample)
    except Exception as exc:  # noqa: BLE001 - measurement must never mask the step's own outcome
        log.debug("code mode sample not recorded: %s", exc)
    return sample


class SampleStore:
    """Bounded in-memory ring of step samples, mirrored to the DB when available."""

    def __init__(self, maxlen: int = MAX_MEMORY_SAMPLES) -> None:
        self._samples: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def add(self, sample: dict[str, Any]) -> None:
        with self._lock:
            self._samples.append(sample)
        log.info(
            "code_mode_step arm=%s status=%s llm_calls=%d prompt_chars=%d programs=%d",
            sample["arm"], sample["status"], sample["llm_calls"], sample["prompt_chars"],
            sample["run_code_programs"],
        )
        _persist.fire_and_forget(self._write(sample))

    def memory(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._samples)

    async def _write(self, sample: dict[str, Any]) -> None:
        col = _persist.collection(COLLECTION)
        if col is None:
            return
        try:
            await _persist.ensure_ttl_index(COLLECTION, col, "expires_at")
            expires = datetime.now(timezone.utc) + timedelta(days=TTL_DAYS)
            await col.insert_one({**sample, **_persist.expiry_fields(expires)})
        except Exception as exc:  # noqa: BLE001 - the memory copy still serves this worker
            _persist.warn_limited("code-mode-write", "code mode sample not persisted: %s", exc)

    async def load(self, limit: int = 5000) -> list[dict[str, Any]]:
        """Samples from the DB (newest *limit*), or the memory ring when there is none."""
        col = _persist.collection(COLLECTION)
        if col is None:
            return self.memory()
        try:
            docs = await asyncio.wait_for(
                col.find({}, {"_id": 0}).sort("ts", -1).limit(limit).to_list(length=limit), timeout=5,
            )
        except Exception as exc:  # noqa: BLE001 - fall back to this worker's samples
            log.debug("code mode samples unreadable from DB: %s", exc)
            return self.memory()
        return docs or self.memory()


_store: SampleStore | None = None
_store_lock = threading.Lock()


def get_store() -> SampleStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = SampleStore()
        return _store


def reset_store() -> None:
    """Drop the singleton (tests)."""
    global _store
    with _store_lock:
        _store = None


_INT_FIELDS = ("llm_calls", "prompt_chars", "selection_errors", "run_code_programs", "run_code_ok", "run_code_inner_calls")


def _clean(row: Any) -> dict[str, Any] | None:
    """Coerce one stored sample to the expected types; ``None`` when it cannot be read.

    Samples come back from a 30-day DB mirror, so one malformed document must not
    take the whole comparison down.
    """
    if not isinstance(row, dict):
        return None
    try:
        clean: dict[str, Any] = {k: int(row.get(k) or 0) for k in _INT_FIELDS}
        clean["wall_s"] = float(row.get("wall_s") or 0)
        errors = row.get("run_code_errors") or {}
        clean["run_code_errors"] = {str(k): int(v) for k, v in errors.items()} if isinstance(errors, dict) else {}
    except (TypeError, ValueError):
        return None
    clean["arm"] = row.get("arm")
    clean["status"] = row.get("status")
    return clean


def _arm_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"steps": 0}
    calls = [int(r.get("llm_calls", 0)) for r in rows]
    chars = [int(r.get("prompt_chars", 0)) for r in rows]
    return {
        "steps": len(rows),
        "llm_calls_mean": round(mean(calls), 2),
        "llm_calls_median": median(calls),
        "llm_calls_stdev": round(pstdev(calls), 3),
        "prompt_tokens_est_mean": round(mean(chars) / 4),
        "wall_s_mean": round(mean(float(r.get("wall_s", 0)) for r in rows), 2),
        "success_rate": round(sum(1 for r in rows if r.get("status") == "applied") / len(rows), 3),
        "selection_error_rate": round(sum(int(r.get("selection_errors", 0)) for r in rows) / max(sum(calls), 1), 3),
    }


def _program_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    programs = sum(int(r.get("run_code_programs", 0)) for r in rows)
    errors: dict[str, int] = {}
    for r in rows:
        for kind, n in (r.get("run_code_errors") or {}).items():
            errors[kind] = errors.get(kind, 0) + int(n)
    return {
        "programs": programs,
        "steps_using_run_code": sum(1 for r in rows if r.get("run_code_programs")),
        "ok_rate": round(sum(int(r.get("run_code_ok", 0)) for r in rows) / programs, 3) if programs else None,
        "inner_calls_per_program": (
            round(sum(int(r.get("run_code_inner_calls", 0)) for r in rows) / programs, 2) if programs else None
        ),
        "errors_by_kind": errors,
    }


def summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare the ``on`` and ``holdout`` arms; ``off`` is reported separately."""
    rows = [c for c in (_clean(s) for s in samples) if c is not None]
    by_arm = {arm: [r for r in rows if r["arm"] == arm] for arm in (ARM_ON, ARM_HOLDOUT, ARM_OFF)}
    on, hold = _arm_stats(by_arm[ARM_ON]), _arm_stats(by_arm[ARM_HOLDOUT])
    enough = on["steps"] >= MIN_SAMPLES_PER_ARM and hold["steps"] >= MIN_SAMPLES_PER_ARM
    out: dict[str, Any] = {
        "arms": {ARM_ON: on, ARM_HOLDOUT: hold, ARM_OFF: _arm_stats(by_arm[ARM_OFF])},
        "run_code": _program_stats(by_arm[ARM_ON]),
        "min_samples_per_arm": MIN_SAMPLES_PER_ARM,
        "enough_data": enough,
        "skipped_samples": len(samples) - len(rows),
    }
    if on["steps"] and hold["steps"]:
        out["delta_on_vs_holdout"] = {
            "llm_calls_mean": round(on["llm_calls_mean"] - hold["llm_calls_mean"], 2),
            "prompt_tokens_est_mean": on["prompt_tokens_est_mean"] - hold["prompt_tokens_est_mean"],
            "wall_s_mean": round(on["wall_s_mean"] - hold["wall_s_mean"], 2),
            "success_rate": round(on["success_rate"] - hold["success_rate"], 3),
        }
        if enough:
            out["verdict"] = _verdict(out["delta_on_vs_holdout"], on, hold)
    return out


def _verdict(delta: dict[str, Any], on: dict[str, Any], hold: dict[str, Any]) -> str:
    """Plan rule: Code Mode earns its place only if it cuts calls without losing success.

    A difference counts only when it beats ~95% sampling error (1.96 standard
    errors), so at 30 steps per arm one unlucky step cannot flip the verdict an
    operator acts on.
    """
    n_on, n_hold = on["steps"], hold["steps"]
    p_on, p_hold = on["success_rate"], hold["success_rate"]
    se_success = (p_on * (1 - p_on) / n_on + p_hold * (1 - p_hold) / n_hold) ** 0.5
    se_calls = (on["llm_calls_stdev"] ** 2 / n_on + hold["llm_calls_stdev"] ** 2 / n_hold) ** 0.5
    if delta["success_rate"] < -max(0.02, 1.96 * se_success):
        return "worse: fewer steps succeed with run_code"
    if delta["llm_calls_mean"] >= -max(0.1, 1.96 * se_calls):
        return "no gain: run_code is not cutting calls (beyond noise)"
    if delta["prompt_tokens_est_mean"] <= 0:
        return "better: fewer calls and tokens, success held"
    return "mixed: fewer calls but more prompt tokens"
