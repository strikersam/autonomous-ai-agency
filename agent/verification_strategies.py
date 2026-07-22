"""agent/verification_strategies.py — opt-in parallel patterns for high-stakes work.

Two independent-agent strategies, additive to the single-runner
plan→execute→verify loop in ``agent/loop.py``:

- ``cross_verify``: after a primary ``AgentRunner`` attempt completes, an
  independent runner (a fresh instance, no shared state) re-checks the
  result before it's accepted. Auto-triggered for tasks touching the
  risky-module list this repo already treats specially (see
  ``.claude/skills/risky-module-review/SKILL.md``: ``admin_auth.py``,
  ``key_store.py``, ``agent/tools.py``, any auth/session/key path).
- ``race``: N independent attempts at the same instruction run concurrently;
  the reward scorer (falling back to a simple heuristic when unavailable)
  picks the winner.

Deliberately a standalone module rather than an extension of
``agent.coordinator.MultiAgentSwarm`` — that class is marked DEPRECATED
(blocked outside ``AGENCY_WORKFLOW_MODE=legacy``) in favour of
``WorkflowOrchestrator``, so new capability is layered on top of
``AgentRunner`` directly instead of growing the deprecated swarm.

Both strategies take a ``runner_factory`` callable (``() -> AgentRunner``)
so callers control construction (workspace root, tokens, models) and tests
can inject stub runners without touching real models or the filesystem.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Awaitable, Callable

log = logging.getLogger("qwen-agent")

RunnerFactory = Callable[[], Any]

# Mirrors .claude/skills/risky-module-review/SKILL.md's trigger list.
_RISKY_PATTERNS = (
    re.compile(r"admin_auth\.py$"),
    re.compile(r"key_store\.py$"),
    re.compile(r"agent/tools\.py$"),
    re.compile(r"auth", re.IGNORECASE),
    re.compile(r"session", re.IGNORECASE),
    re.compile(r"\bkey\b", re.IGNORECASE),
)


def touches_risky_module(paths: list[str]) -> bool:
    """True if any path matches the repo's risky-module trigger list."""
    return any(pattern.search(path) for path in paths for pattern in _RISKY_PATTERNS)


async def cross_verify(
    *,
    instruction: str,
    changed_files: list[str],
    runner_factory: RunnerFactory,
    max_steps: int = 2,
) -> dict[str, Any]:
    """Have an independent agent re-check a completed task's changed files.

    Returns {"cross_verified": bool, "issues": list[str], "raw": dict}.
    Never raises — a verifier failure is reported as issues, not an exception,
    since this runs after the primary work already completed.
    """
    review_instruction = (
        "Independently review the following change for correctness and safety. "
        f"Original task: {instruction}\n"
        f"Files changed: {', '.join(changed_files) or '(none)'}\n"
        "Report any bug, security issue, or deviation from the task. "
        "Do not modify any files — review only."
    )
    try:
        runner = runner_factory()
        result = await runner.run(
            instruction=review_instruction,
            history=[],
            requested_model=None,
            auto_commit=False,
            max_steps=max_steps,
        )
    except Exception as exc:
        log.warning("cross_verify: independent review failed to run: %s", exc)
        return {"cross_verified": False, "issues": [f"cross_verify_error: {exc}"], "raw": {}}

    issues = list(result.get("issues") or [])
    for step in result.get("steps", []) or []:
        issues.extend(step.get("issues") or [])
    status = str(result.get("status", "")).lower()
    passed = status in ("completed", "applied", "ok") and not issues
    return {"cross_verified": passed, "issues": issues, "raw": result}


def _score_attempt(result: dict[str, Any]) -> float:
    """Heuristic fallback score when the reward model is unavailable."""
    status = str(result.get("status", "")).lower()
    if status in ("failed", "error"):
        return 0.0
    steps = result.get("steps") or []
    if not steps:
        return 0.4 if status in ("completed", "applied", "ok") else 0.1
    applied = sum(1 for s in steps if s.get("status") == "applied")
    issue_count = sum(len(s.get("issues") or []) for s in steps)
    ratio = applied / len(steps)
    return max(0.0, min(1.0, ratio - 0.05 * issue_count))


async def _score_result(result: dict[str, Any], instruction: str) -> float:
    try:
        from services.reward_scorer import get_reward_scorer
        scorer = get_reward_scorer()
        if scorer and scorer.is_available:
            scored = await scorer.score(prompt=instruction, response=str(result)[:8000])
            return scored.score
    except Exception as exc:  # nosec B110 -- scoring is best-effort
        log.debug("race: reward scorer unavailable, using heuristic: %s", exc)
    return _score_attempt(result)


async def race(
    *,
    instruction: str,
    runner_factory: RunnerFactory,
    n: int = 2,
    max_steps: int = 3,
) -> dict[str, Any]:
    """Run *n* independent attempts at *instruction* concurrently; return the winner.

    Returns {"winner_index": int, "winner": dict, "attempts": list[dict], "scores": list[float]}.
    """
    if n < 1:
        raise ValueError("race requires n >= 1")

    async def _attempt(idx: int) -> dict[str, Any]:
        try:
            runner = runner_factory()
            return await runner.run(
                instruction=instruction, history=[], requested_model=None,
                auto_commit=False, max_steps=max_steps,
            )
        except Exception as exc:
            log.warning("race: attempt %d failed: %s", idx, exc)
            return {"status": "error", "error": str(exc)}

    attempts = await asyncio.gather(*(_attempt(i) for i in range(n)))
    scores = await asyncio.gather(*(_score_result(a, instruction) for a in attempts))
    winner_index = max(range(len(scores)), key=lambda i: scores[i])
    return {
        "winner_index": winner_index,
        "winner": attempts[winner_index],
        "attempts": list(attempts),
        "scores": list(scores),
    }
