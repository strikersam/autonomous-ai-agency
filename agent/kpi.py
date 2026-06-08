"""agent/kpi.py — Autonomy KPIs: evidence capture and metrics tracking.

Tracks key autonomy indicators across the agent loop and workflow engine
so the system can prove it is actually working — not just claiming to work.

Golden Path step #14 (Evidence Capture) and #15 (Autonomy KPIs).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AutonomyCounter:
    """Thread-safe counter for a single KPI metric."""

    _value: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, delta: int = 1) -> int:
        with self._lock:
            self._value += delta
            return self._value

    def get(self) -> int:
        with self._lock:
            return self._value


@dataclass
class AutonomySnapshot:
    """Point-in-time snapshot of all autonomy KPIs."""

    total_sessions: int = 0
    total_plans: int = 0
    steps_applied: int = 0
    steps_failed: int = 0
    steps_skipped: int = 0
    commits_made: int = 0
    prs_created: int = 0
    approval_gates_passed: int = 0
    approval_gates_rejected: int = 0
    slices_executed: int = 0
    slices_failed: int = 0
    safety_blocks: int = 0
    uptime_seconds: int = 0
    events_logged: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_sessions": self.total_sessions,
            "total_plans": self.total_plans,
            "steps_applied": self.steps_applied,
            "steps_failed": self.steps_failed,
            "steps_skipped": self.steps_skipped,
            "commits_made": self.commits_made,
            "prs_created": self.prs_created,
            "approval_gates_passed": self.approval_gates_passed,
            "approval_gates_rejected": self.approval_gates_rejected,
            "slices_executed": self.slices_executed,
            "slices_failed": self.slices_failed,
            "safety_blocks": self.safety_blocks,
            "uptime_seconds": self.uptime_seconds,
            "events_logged": self.events_logged,
        }


class AutonomyTracker:
    """Singleton tracker for autonomy KPIs.

    Usage::

        from agent.kpi import get_tracker
        tracker = get_tracker()
        tracker.record_step_applied()
    """

    def __init__(self) -> None:
        self._start_time = time.time()
        self.total_sessions = AutonomyCounter()
        self.total_plans = AutonomyCounter()
        self.steps_applied = AutonomyCounter()
        self.steps_failed = AutonomyCounter()
        self.steps_skipped = AutonomyCounter()
        self.commits_made = AutonomyCounter()
        self.prs_created = AutonomyCounter()
        self.approval_gates_passed = AutonomyCounter()
        self.approval_gates_rejected = AutonomyCounter()
        self.slices_executed = AutonomyCounter()
        self.slices_failed = AutonomyCounter()
        self.safety_blocks = AutonomyCounter()
        self.events_logged = AutonomyCounter()

    # ── Recording helpers ──────────────────────────────────────────────────

    def record_session(self) -> None:
        self.total_sessions.inc()

    def record_plan(self) -> None:
        self.total_plans.inc()

    def record_step_applied(self, count: int = 1) -> None:
        self.steps_applied.inc(count)

    def record_step_failed(self) -> None:
        self.steps_failed.inc()

    def record_step_skipped(self) -> None:
        self.steps_skipped.inc()

    def record_commit(self) -> None:
        self.commits_made.inc()

    def record_pr_created(self) -> None:
        self.prs_created.inc()

    def record_approval_gate_passed(self) -> None:
        self.approval_gates_passed.inc()

    def record_approval_gate_rejected(self) -> None:
        self.approval_gates_rejected.inc()

    def record_slice_executed(self) -> None:
        self.slices_executed.inc()

    def record_slice_failed(self) -> None:
        self.slices_failed.inc()

    def record_safety_block(self) -> None:
        self.safety_blocks.inc()

    def record_events(self, count: int = 1) -> None:
        self.events_logged.inc(count)

    # ── Snapshot ───────────────────────────────────────────────────────────

    def snapshot(self) -> AutonomySnapshot:
        """Return a point-in-time snapshot of all KPIs."""
        return AutonomySnapshot(
            total_sessions=self.total_sessions.get(),
            total_plans=self.total_plans.get(),
            steps_applied=self.steps_applied.get(),
            steps_failed=self.steps_failed.get(),
            steps_skipped=self.steps_skipped.get(),
            commits_made=self.commits_made.get(),
            prs_created=self.prs_created.get(),
            approval_gates_passed=self.approval_gates_passed.get(),
            approval_gates_rejected=self.approval_gates_rejected.get(),
            slices_executed=self.slices_executed.get(),
            slices_failed=self.slices_failed.get(),
            safety_blocks=self.safety_blocks.get(),
            uptime_seconds=int(time.time() - self._start_time),
            events_logged=self.events_logged.get(),
        )

    def reset(self) -> None:
        """Reset all counters (test helper)."""
        self.__init__()  # type: ignore[misc]


# ── Singleton ─────────────────────────────────────────────────────────────

_tracker: AutonomyTracker | None = None


def get_tracker() -> AutonomyTracker:
    """Return the shared AutonomyTracker singleton (lazy-init)."""
    global _tracker
    if _tracker is None:
        _tracker = AutonomyTracker()
    return _tracker


def reset_tracker() -> None:
    """Reset the singleton (test helper)."""
    global _tracker
    _tracker = None
