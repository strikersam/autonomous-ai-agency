"""★7 Adaptive Loop Halting — velocity-based agent run termination.

Complements StuckDetector (tool-loop pattern detection) with a higher-level
progress monitor that watches the STEP loop, not the tool loop.

Halts a run when the plan is clearly not converging, preventing unnecessary
token burn on plans that have become unreachable:

  1. Consecutive failure gate — if N steps in a row fail, the plan is likely
     blocked on an unresolvable dependency.
  2. Velocity gate — if the ratio of applied steps to steps attempted drops
     below a threshold after a minimum number of attempts, the run is spending
     tokens without making progress.

Both thresholds are tunable via environment variables so operators can adjust
for long-running plans vs. quick single-step tasks.

Wire into the per-step loop immediately after each step result:

    halter = AdaptiveHalter()
    for step in plan.steps:
        result = await _execute_step(...)
        reason = halter.record(result["status"])
        if reason:
            log.warning("adaptive halt: %s", reason)
            break
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("qwen-agent")

_DEFAULT_CONSECUTIVE_FAILURES: int = int(
    os.environ.get("AGENT_HALT_CONSECUTIVE_FAILURES", "3")
)
_DEFAULT_MIN_VELOCITY: float = float(
    os.environ.get("AGENT_HALT_MIN_VELOCITY", "0.25")
)
_DEFAULT_MIN_STEPS_BEFORE_CHECK: int = int(
    os.environ.get("AGENT_HALT_MIN_STEPS", "4")
)


class AdaptiveHalter:
    """Tracks step-level progress and signals when a run should halt early.

    The halter is stateful and intended to be created once per ``AgentRunner.run()``
    call.  It is *not* thread-safe — it assumes serial step execution.
    """

    def __init__(
        self,
        consecutive_failure_threshold: int | None = None,
        min_velocity: float | None = None,
        min_steps_before_check: int | None = None,
    ) -> None:
        self._max_consecutive_fail: int = (
            consecutive_failure_threshold
            if consecutive_failure_threshold is not None
            else _DEFAULT_CONSECUTIVE_FAILURES
        )
        self._min_velocity: float = (
            min_velocity if min_velocity is not None else _DEFAULT_MIN_VELOCITY
        )
        self._min_steps: int = (
            min_steps_before_check
            if min_steps_before_check is not None
            else _DEFAULT_MIN_STEPS_BEFORE_CHECK
        )
        self._total_steps: int = 0
        self._applied_steps: int = 0
        self._consecutive_failures: int = 0

    @property
    def velocity(self) -> float:
        """Ratio of applied steps to steps attempted (0.0–1.0).

        Returns 1.0 when no steps have been recorded yet so the run is never
        halted before the first step completes.
        """
        if self._total_steps == 0:
            return 1.0
        return self._applied_steps / self._total_steps

    def record(self, status: str) -> str | None:
        """Record one step outcome; return a halt reason or None to continue.

        ``status`` should be ``"applied"`` for success, any other value (typically
        ``"failed"``) for failure.  Returns a human-readable halt reason string
        when the halter decides to stop, or ``None`` to continue normally.

        Fail-open: never raises; unexpected ``status`` values are treated as failures.
        """
        try:
            self._total_steps += 1
            if status == "applied":
                self._applied_steps += 1
                self._consecutive_failures = 0
            else:
                self._consecutive_failures += 1

            # Consecutive failure gate
            if self._consecutive_failures >= self._max_consecutive_fail:
                return (
                    f"{self._consecutive_failures} consecutive step failures — "
                    f"plan likely blocked; halting to prevent further token spend"
                )

            # Velocity gate (only after min_steps to avoid premature halts)
            if self._total_steps >= self._min_steps and self.velocity < self._min_velocity:
                return (
                    f"step velocity {self.velocity:.2f} "
                    f"({self._applied_steps}/{self._total_steps} applied) "
                    f"below minimum {self._min_velocity:.2f} — halting run"
                )

            return None
        except Exception as exc:
            log.debug("adaptive halter check failed (non-fatal): %s", exc)
            return None

    def as_dict(self) -> dict[str, Any]:
        """Return current halter state for logging / telemetry."""
        return {
            "total_steps": self._total_steps,
            "applied_steps": self._applied_steps,
            "consecutive_failures": self._consecutive_failures,
            "velocity": self.velocity,
        }
