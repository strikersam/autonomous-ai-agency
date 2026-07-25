"""services/ceo_supervisor.py — the CEO's 24x7 babysitting loop.

Delegation alone does not keep an agency running. Work stalls: a runtime goes
to sleep mid-subtask, a provider starts returning 429s, a process is recycled
between the plan and the execution. Nothing in the fire-and-forget path
notices, and the goal sits open forever while the dashboard shows an agency
that looks busy.

The supervisor is the part that notices. It sweeps the ledger on a fixed
cadence and, for every goal the CEO still owns, does one of four things:

  * **Close it** when every subtask has been accepted.
  * **Re-drive it** when it has made no progress for longer than the stall
    threshold — the goal is re-planned and re-delegated from where it stopped.
  * **Abandon it** when the intervention budget or the age limit is spent, so a
    permanently broken goal cannot consume the agency's budget forever.
  * **Leave it alone** when it is genuinely in flight.

It also wakes sleeping runtimes on every sweep, so a Render free-tier spin-down
or an idle Hermes does not quietly become a permanent outage.

Every loop that runs unattended needs bounds, and this one has five: a sweep
interval, a stall threshold, a per-goal intervention cap, a per-goal age cap,
and a cap on how many goals a single sweep will re-drive. All five are in
:class:`SupervisorConfig` and all five are clamped when read from the
environment.

The re-drive claim is taken in the *shared* ledger, not just in this process:
``RUN_BACKGROUND_IN_WEB`` defaults to true, so a deployment running the
dedicated worker as well has two processes sweeping the same goals.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("agency.ceo.supervisor")


def _env_int(name: str, default: int, *, low: int, high: int) -> int:
    """Read a bounded int, clamping out-of-range values rather than raising."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(low, min(high, int(raw)))
    except ValueError:
        log.warning("%s=%r is not an integer; using %d", name, raw, default)
        return default


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SupervisorConfig:
    """Bounds for the unattended supervision loop."""

    #: Seconds between sweeps.
    interval_s: int = 180
    #: A goal whose last recorded progress is older than this is considered
    #: stalled. It must comfortably exceed how long a single senior subtask can
    #: legitimately run, or the supervisor will re-drive healthy work.
    stall_s: int = 1800
    #: How many times one goal may be re-driven before it is abandoned.
    max_interventions: int = 3
    #: A goal older than this is abandoned regardless of progress.
    max_goal_age_s: int = 86400
    #: How many stalled goals a single sweep will re-drive. Caps the burst of
    #: work one sweep can create after a long outage.
    max_redrives_per_sweep: int = 2
    #: Wake sleeping runtimes at the top of each sweep.
    wake_runtimes: bool = True

    @classmethod
    def from_env(cls) -> "SupervisorConfig":
        return cls(
            interval_s=_env_int("CEO_SUPERVISOR_INTERVAL_S", 180, low=30, high=3600),
            stall_s=_env_int("CEO_SUPERVISOR_STALL_S", 1800, low=60, high=86400),
            max_interventions=_env_int("CEO_SUPERVISOR_MAX_INTERVENTIONS", 3, low=0, high=10),
            max_goal_age_s=_env_int("CEO_SUPERVISOR_MAX_GOAL_AGE_S", 86400, low=300, high=604800),
            max_redrives_per_sweep=_env_int(
                "CEO_SUPERVISOR_MAX_REDRIVES_PER_SWEEP", 2, low=1, high=10
            ),
            wake_runtimes=_env_flag("CEO_SUPERVISOR_WAKE_RUNTIMES", True),
        )


def supervisor_enabled() -> bool:
    """True when the 24x7 supervisor should run in this process.

    Off under ``TESTING`` so unit tests never start a background sweeper.
    """
    if _env_flag("TESTING", False):
        return False
    return _env_flag("CEO_SUPERVISOR_ENABLED", True)


@dataclass
class SweepReport:
    """What one sweep observed and did. Returned for tests and diagnostics."""

    scanned: int = 0
    closed: int = 0
    redriven: int = 0
    abandoned: int = 0
    in_flight: int = 0
    runtimes_woken: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "closed": self.closed,
            "redriven": self.redriven,
            "abandoned": self.abandoned,
            "in_flight": self.in_flight,
            "runtimes_woken": self.runtimes_woken,
            "errors": self.errors[:10],
        }


class CEOSupervisor:
    """Sweeps the CEO ledger and drives open goals to closure."""

    def __init__(self, config: SupervisorConfig | None = None) -> None:
        self.config = config or SupervisorConfig.from_env()
        self._running = False
        self._sweeps = 0
        self._last_report: SweepReport | None = None
        self._last_sweep_at: float = 0.0
        #: Goals this process is currently re-driving. Without it, a re-drive
        #: that takes longer than the sweep interval would be started again on
        #: the next sweep, duplicating the work it was meant to rescue.
        self._driving: set[str] = set()
        #: Strong references to in-flight re-drive tasks. ``asyncio`` only keeps
        #: a weak reference to a running task, so a task held nowhere else can
        #: be garbage collected mid-flight; ``add_done_callback`` does not keep
        #: it alive either.
        self._tasks: set[asyncio.Task] = set()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def run_forever(self) -> None:
        """Sweep on the configured cadence until cancelled.

        A failing sweep is logged and the loop continues: the supervisor is the
        component that keeps everything else alive, so it must be the last
        thing to die.
        """
        self._running = True
        log.info(
            "CEO supervisor started (interval=%ds, stall=%ds, max_interventions=%d)",
            self.config.interval_s, self.config.stall_s, self.config.max_interventions,
        )
        try:
            while self._running:
                try:
                    report = await self.sweep()
                    if report.closed or report.redriven or report.abandoned:
                        log.info("CEO supervisor sweep: %s", report.as_dict())
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001 — the loop must survive
                    log.warning("CEO supervisor sweep failed: %s", exc, exc_info=True)
                await self._sleep(self.config.interval_s)
        except asyncio.CancelledError:
            log.info("CEO supervisor stopped")
            raise
        finally:
            self._running = False

    def stop(self) -> None:
        self._running = False

    async def _sleep(self, seconds: float) -> None:
        """Inter-sweep delay, behind a method so tests can shorten it.

        Patching ``asyncio.sleep`` through this module would replace it for the
        whole process — ``services.ceo_supervisor.asyncio`` *is* the stdlib
        module — which would silently speed up every other coroutine on the loop.
        """
        await asyncio.sleep(seconds)

    def is_driving(self, goal_id: str) -> bool:
        """True when this process already has a re-drive in flight for *goal_id*."""
        return goal_id in self._driving

    def request_redrive(self, goal: Any, ledger: Any = None) -> bool:
        """Start a re-drive of *goal*, honouring the intervention budget.

        Returns ``False`` when the goal has spent its budget or is already being
        driven. Keeping the budget check and the ``_driving`` claim together in
        one public method means the HTTP layer cannot accidentally bypass either
        — the manual re-drive route is not a way around the cap.
        """
        if goal.interventions >= self.config.max_interventions:
            return False
        if self.is_driving(goal.goal_id):
            return False
        if ledger is None:
            from services.ceo_ledger import get_ceo_ledger

            ledger = get_ceo_ledger()
        return self._spawn_redrive(ledger, goal)

    def get_status(self) -> dict[str, Any]:
        """Status for the health endpoint and dashboard."""
        return {
            "running": self._running,
            "sweeps": self._sweeps,
            "last_sweep_at": self._last_sweep_at or None,
            "last_sweep_age_s": (
                round(time.time() - self._last_sweep_at, 1) if self._last_sweep_at else None
            ),
            "driving": sorted(self._driving),
            "config": {
                "interval_s": self.config.interval_s,
                "stall_s": self.config.stall_s,
                "max_interventions": self.config.max_interventions,
                "max_goal_age_s": self.config.max_goal_age_s,
                "max_redrives_per_sweep": self.config.max_redrives_per_sweep,
            },
            "last_report": self._last_report.as_dict() if self._last_report else None,
        }

    # ── One sweep ─────────────────────────────────────────────────────────

    async def sweep(self) -> SweepReport:
        """Run a single supervision pass over the open goals."""
        report = SweepReport()
        self._sweeps += 1
        self._last_sweep_at = time.time()

        if self.config.wake_runtimes:
            report.runtimes_woken = await self._wake_runtimes()

        try:
            from services.ceo_ledger import get_ceo_ledger

            ledger = get_ceo_ledger()
            open_goals = ledger.open_goals(limit=100)
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"ledger unavailable: {exc}")
            self._last_report = report
            return report

        report.scanned = len(open_goals)
        now = time.time()
        redrives = 0

        for goal in open_goals:
            if goal.goal_id in self._driving:
                report.in_flight += 1
                continue
            try:
                action = self._classify(goal, now=now, redrives_used=redrives)
                if action == "close":
                    self._close(ledger, goal)
                    report.closed += 1
                elif action == "abandon":
                    self._abandon(ledger, goal, now=now)
                    report.abandoned += 1
                elif action == "redrive":
                    if self._spawn_redrive(ledger, goal):
                        redrives += 1
                        report.redriven += 1
                    else:
                        # Another sweeper won the claim — not our goal this round.
                        report.in_flight += 1
                else:
                    report.in_flight += 1
            except Exception as exc:  # noqa: BLE001 — one bad goal must not stop the sweep
                report.errors.append(f"{goal.goal_id}: {exc}")

        self._last_report = report
        return report

    def _classify(self, goal: Any, *, now: float, redrives_used: int) -> str:
        """Decide what to do with one open goal.

        Order matters. Closure is checked first so a goal that finished just
        before a stall window is never re-driven. Abandonment is checked before
        re-drive so an exhausted goal cannot buy another attempt by also being
        stalled.
        """
        done, total = goal.progress()
        if total and done == total:
            return "close"
        if now - goal.created_at > self.config.max_goal_age_s:
            return "abandon"
        if goal.interventions >= self.config.max_interventions:
            return "abandon"
        if now - goal.last_progress_at < self.config.stall_s:
            return "in_flight"
        if redrives_used >= self.config.max_redrives_per_sweep:
            return "in_flight"
        return "redrive"

    def _close(self, ledger: Any, goal: Any) -> None:
        goal.state = "closed"
        goal.verdict = goal.verdict or "OK"
        goal.notes.append("Closed by supervisor: all subtasks accepted.")
        goal.last_progress_at = time.time()
        ledger.upsert(goal)
        log.info("CEO supervisor closed goal %s (%s)", goal.goal_id, goal.goal[:80])

    def _abandon(self, ledger: Any, goal: Any, *, now: float) -> None:
        age_h = (now - goal.created_at) / 3600.0
        reason = (
            f"age {age_h:.1f}h exceeded limit"
            if now - goal.created_at > self.config.max_goal_age_s
            else f"intervention budget spent ({goal.interventions}/{self.config.max_interventions})"
        )
        goal.state = "abandoned"
        goal.verdict = goal.verdict or "FAILED"
        goal.notes.append(f"Abandoned by supervisor: {reason}.")
        goal.last_progress_at = now
        ledger.upsert(goal)
        log.warning(
            "CEO supervisor abandoned goal %s — %s. Goal: %s",
            goal.goal_id, reason, goal.goal[:120],
        )

    def _spawn_redrive(self, ledger: Any, goal: Any) -> bool:
        """Mark a stalled goal as intervened and start re-driving it.

        The re-drive runs as a detached task so one slow goal cannot hold up
        the rest of the sweep. ``_driving`` is claimed synchronously, before the
        task starts, so a sweep that fires while the re-drive is still running
        skips the goal instead of starting a second one.
        """
        # Claim the goal in the *shared* ledger before doing anything. With two
        # sweeping processes (web + worker both run background services), the
        # in-process _driving set below is not a claim either of them can see;
        # only this compare-and-set decides who owns the re-drive.
        if not ledger.claim_intervention(goal.goal_id, expected=goal.interventions):
            log.info(
                "CEO supervisor: goal %s claimed by another sweeper, skipping",
                goal.goal_id,
            )
            return False
        goal.interventions += 1
        goal.last_progress_at = time.time()
        goal.notes.append(
            f"Supervisor intervention #{goal.interventions}: re-driving stalled goal."
        )
        ledger.upsert(goal)
        self._driving.add(goal.goal_id)
        log.warning(
            "CEO supervisor re-driving stalled goal %s (intervention %d/%d): %s",
            goal.goal_id, goal.interventions, self.config.max_interventions, goal.goal[:100],
        )
        task = asyncio.create_task(self._redrive(goal))
        # Hold a strong reference until completion so the task is not garbage
        # collected mid-flight, and always release the claim when it finishes.
        self._tasks.add(task)

        def _done(finished: asyncio.Task, gid: str = goal.goal_id) -> None:
            self._tasks.discard(finished)
            self._driving.discard(gid)

        task.add_done_callback(_done)
        return True

    async def _redrive(self, goal: Any) -> None:
        """Re-delegate a stalled goal through the CEO, reusing its ledger entry.

        The original workspace and user id are replayed so the intervention acts
        on the same checkout and keeps the same attribution — without them the
        re-drive silently fell back to the process working directory, which for a
        company-scoped goal is the wrong repository.

        Credentials are **not** replayed: the ledger deliberately stores no
        tokens, so a re-drive runs with the server's own repo access. A goal that
        only succeeded because of a caller's elevated GitHub token will therefore
        fail its push step on re-drive rather than silently acting with different
        permissions than the operator expects.
        """
        try:
            from services.ceo_dispatcher import get_ceo_dispatcher

            ceo = get_ceo_dispatcher()
            await ceo.delegate(
                goal.request or goal.goal,
                goal=goal.goal,
                goal_id=goal.goal_id,
                complexity=goal.complexity,
                domain=goal.domain,
                workspace_root=goal.workspace_root or None,
                user_id=goal.user_id or None,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("CEO supervisor re-drive of %s failed: %s", goal.goal_id, exc)
            try:
                from services.ceo_ledger import get_ceo_ledger

                ledger = get_ceo_ledger()
                current = ledger.get(goal.goal_id)
                if current is not None and not current.is_closed:
                    current.notes.append(f"Re-drive failed: {exc}")
                    ledger.upsert(current)
            except Exception:  # noqa: BLE001 — diagnostics only
                log.debug("CEO supervisor could not record re-drive failure")

    async def _wake_runtimes(self) -> list[str]:
        """Force-wake sleeping runtimes so idle infrastructure self-recovers."""
        try:
            from services.ceo_dispatcher import get_ceo_dispatcher

            return await get_ceo_dispatcher().wake_sleeping_runtimes(force=True)
        except Exception as exc:  # noqa: BLE001
            log.debug("CEO supervisor wake skipped: %s", exc)
            return []


# ── Singleton ─────────────────────────────────────────────────────────────────

_supervisor: CEOSupervisor | None = None


def get_ceo_supervisor() -> CEOSupervisor:
    """Return the shared supervisor, constructing it on first use."""
    global _supervisor
    if _supervisor is None:
        _supervisor = CEOSupervisor()
    return _supervisor


def set_ceo_supervisor(instance: CEOSupervisor | None) -> None:
    """Install (or clear) the singleton — used by startup wiring and tests."""
    global _supervisor
    _supervisor = instance


def reset_ceo_supervisor() -> None:
    """Drop the singleton (test helper)."""
    set_ceo_supervisor(None)
