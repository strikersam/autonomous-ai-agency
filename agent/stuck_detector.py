"""Stuck detection for the agent tool loop — adapted from OpenHands.

OpenHands (github.com/OpenHands/OpenHands) stops agent runs that spin in
place: its ``StuckDetector`` scans recent events for repeating patterns.
This module adapts three of those heuristics to this repo's observation
dicts (``{"tool": str, "args": dict, "result": Any}``) so
``AgentRunner._execute_step`` can break out of a doomed tool loop instead
of burning the remaining LLM-call budget repeating itself.

Patterns detected (over the most recent observations of a step):

1. repeating action+observation — the same tool call with the same args
   producing the same result N times in a row
2. repeating action+error       — the same tool call failing N times in a row
   (results differ but all look like errors)
3. alternating pattern          — two observations alternating A,B,A,B,A,B

Fail open by design: ``check()`` never raises and returns ``None`` on any
malformed input, so stuck detection can never break a run.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("qwen-agent")

# Mirrors OpenHands' MAX_EVENTS_TO_SCAN_FOR_STUCK_DETECTION.
_MAX_OBSERVATIONS_TO_SCAN = 20
# Long tool results are compared by prefix — enough to distinguish genuinely
# different outputs without hashing megabytes of text every iteration.
_RESULT_SIGNATURE_CHARS = 512

_ERROR_RE = re.compile(r"\b(error|failed|failure|exception|traceback)\b", re.IGNORECASE)

# (tool, canonical-args, result-prefix) — the identity of one observation.
_Signature = tuple[str, str, str]


@dataclass(frozen=True)
class StuckThresholds:
    """Consecutive repetitions required before a pattern counts as stuck."""

    action_observation: int = 3
    action_error: int = 3
    alternating_pairs: int = 3


class StuckDetector:
    """Detects repeating patterns in a step's observation history."""

    def __init__(self, thresholds: StuckThresholds | None = None) -> None:
        self.thresholds = thresholds or StuckThresholds()

    def check(self, observations: list[dict[str, Any]]) -> str | None:
        """Return a human-readable reason when the loop looks stuck, else None."""
        try:
            recent = [
                obs
                for obs in (observations or [])[-_MAX_OBSERVATIONS_TO_SCAN:]
                if isinstance(obs, dict)
            ]
            signatures = [_signature(obs) for obs in recent]
            return (
                self._repeating_action_observation(signatures)
                or self._repeating_action_error(signatures)
                or self._alternating_pattern(signatures)
            )
        except Exception as exc:  # stuck detection must never break the run
            log.debug("stuck detection skipped: %s", exc)
            return None

    def _repeating_action_observation(self, signatures: list[_Signature]) -> str | None:
        n = self.thresholds.action_observation
        if len(signatures) < n:
            return None
        tail = signatures[-n:]
        if all(sig == tail[0] for sig in tail):
            return (
                f"the same tool call ({tail[0][0]}) returned the same result "
                f"{n} times in a row"
            )
        return None

    def _repeating_action_error(self, signatures: list[_Signature]) -> str | None:
        n = self.thresholds.action_error
        if len(signatures) < n:
            return None
        tail = signatures[-n:]
        same_action = all(sig[:2] == tail[0][:2] for sig in tail)
        all_errors = all(_ERROR_RE.search(sig[2]) for sig in tail)
        if same_action and all_errors:
            return f"the same tool call ({tail[0][0]}) failed {n} times in a row"
        return None

    def _alternating_pattern(self, signatures: list[_Signature]) -> str | None:
        pairs = self.thresholds.alternating_pairs
        window = pairs * 2
        if len(signatures) < window:
            return None
        tail = signatures[-window:]
        first, second = tail[0], tail[1]
        if first == second:
            return None  # identical repeats are the action_observation pattern
        if all(sig == (first if i % 2 == 0 else second) for i, sig in enumerate(tail)):
            return (
                f"two tool calls ({first[0]}, {second[0]}) alternated "
                f"{pairs} times without progress"
            )
        return None


def _signature(obs: dict[str, Any]) -> _Signature:
    """Canonical identity of one observation, ignoring incidental fields."""
    tool = str(obs.get("tool", ""))
    try:
        args = json.dumps(obs.get("args", {}), sort_keys=True, default=str)
    except Exception:
        args = str(obs.get("args", ""))
    result = str(obs.get("result", ""))[:_RESULT_SIGNATURE_CHARS]
    return (tool, args, result)
