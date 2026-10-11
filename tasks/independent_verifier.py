"""tasks/independent_verifier.py — rule 49 for runtimes that have no judge.

The internal agent and E2B runtimes run the agent loop, whose judge reviews the
finished run and whose steps execute their own tests. Every other runtime
(Claude Code, Hermes, Goose, Aider, ...) returns prose, so on its own its work
can only wait for a person. This module is the independent verifier for them:

1. find the pull request the runtime opened (a GitHub PR link in its output or
   metadata);
2. check that PR out in a fresh E2B sandbox, byte-compile the changed Python
   files and run their matching tests there (agent/empirical_verify.py);
3. serve changed web pages from the sandbox and screenshot them in the
   Browserbase browser (agent/ui_evidence.py);
4. ask a reviewer model, through the shared failover client, to judge the diff
   against the task with that evidence in hand.

The result has the same shape as an agent-loop run, so ``verification_from_run``
applies the same rules: approval counts only when tests ran and passed, and a
UI change only with a screenshot of every changed page. Failing tests are a
FAIL whatever the reviewer says. Gated by the live
``TASK_INDEPENDENT_VERIFIER`` control (default on).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

log = logging.getLogger("qwen-proxy")

PR_RE = re.compile(r"https://github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)")
# These runtimes run the agent loop, which has its own judge and checks.
SELF_JUDGED = frozenset({"internal_agent", "e2b"})
VERIFIER = "agent:verifier"
_OUTPUT_CHARS = 3000
_TIMEOUT_S = 600.0

_JUDGE_PROMPT = (
    "You are an independent verifier. Another agent did the work below; you did "
    "not. Decide whether the work accomplishes the task: for a code task, the change "
    "and its checks; for a task that needed no code, the report itself. REJECT when "
    "it does not do what the task asks, when the checks failed, when it removes or rewrites "
    "working code the task did not ask to change, or when it invents URLs, names or "
    "identifiers. Respond with ONLY a JSON object with keys: verdict (APPROVED, "
    "APPROVED_WITH_CONDITIONS, or REJECTED), security (PASS, WARN, or FAIL), "
    "correctness (PASS, WARN, or FAIL), notes (string)."
)


def enabled() -> bool:
    """Read the live ``TASK_INDEPENDENT_VERIFIER`` control."""
    from packages.config import settings

    return bool(getattr(settings, "task_independent_verifier", True))


def needs_independent_check(runtime_id: str | None, raw_result: Any) -> bool:
    """True when nothing in this run judged the work."""
    if (runtime_id or "") in SELF_JUDGED:
        return False
    return not (isinstance(raw_result, dict) and isinstance(raw_result.get("judge"), dict))


def find_pull_request(result: Any) -> tuple[str, int] | None:
    """The first GitHub pull request the runtime's output or metadata links to."""
    texts = [str(getattr(result, "output", "") or "")]
    metadata = getattr(result, "metadata", None) or {}
    texts += [str(v) for v in metadata.values() if isinstance(v, (str, int))]
    texts += [json.dumps(a, default=str) for a in (getattr(result, "artifacts", None) or [])]
    for text in texts:
        m = PR_RE.search(text)
        if m:
            return f"https://github.com/{m.group(1)}/{m.group(2)}", int(m.group(3))
    return None


def _token_for(repo_url: str) -> str | None:
    """The platform's GitHub token, only for the repository it belongs to."""
    try:
        import agent.agency as ag

        repo, token = ag._gh_repo(), ag._gh_token()
    except Exception:  # noqa: BLE001 - anonymous clone still works for public repos
        return None
    return token if repo and repo_url.rstrip("/").lower().endswith("/" + repo.lower()) else None


async def _exercise(pr: tuple[str, int]) -> dict[str, Any]:
    """Check the PR out in a sandbox; run its tests; screenshot its pages."""
    from agent import empirical_verify, ui_evidence
    from services.e2b_config import resolve_e2b_config
    from services.e2b_sandbox import E2BSandboxSession

    if resolve_e2b_config() is None:
        return {"gap": "E2B is not configured, so the change could not be run"}
    session = E2BSandboxSession()
    try:
        await session.open()
        change = await session.checkout_pull_request(pr[0], pr[1], _token_for(pr[0]))
        files = change["changed_files"]
        py = [f for f in files if f.endswith(".py")]
        checks = await empirical_verify.verify_in_sandbox(session, py) if py else empirical_verify.CheckOutcome()
        steps = [{"status": "applied", "changed_files": files}]
        shots = await ui_evidence.capture(session, steps)
        return {"files": files, "diff": change["diff"], "checks": checks, "ui": shots}
    except Exception as exc:  # noqa: BLE001 - a broken sandbox is a gap, not a verdict
        log.warning("Independent verifier could not exercise %s#%s: %s", pr[0], pr[1], exc)
        return {"gap": f"the pull request could not be checked out and run ({str(exc)[:200]})"}
    finally:
        await session.close()


def _brief(task: Any, result: Any, pr: tuple[str, int] | None, ev: dict[str, Any]) -> str:
    checks = ev.get("checks")
    lines = [
        f"Task: {getattr(task, 'title', '')}",
        f"Details: {str(getattr(task, 'description', '') or '')[:1500]}",
        f"Runtime: {getattr(result, 'runtime_id', '')}",
        f"Runtime's own report:\n{str(getattr(result, 'output', '') or '')[:_OUTPUT_CHARS]}",
        f"Pull request: {pr[0]}/pull/{pr[1]}" if pr else "Pull request: none found",
    ]
    if ev.get("gap"):
        lines.append(f"Could not run the change: {ev['gap']}")
    if checks is not None:
        lines.append("Checks passed: " + ("; ".join(checks.checks) or "none ran"))
        lines.append("Checks failed: " + ("; ".join(i[:800] for i in checks.issues) or "none"))
    for shot in ev.get("ui") or []:
        lines.append(f"Page {shot.get('page')}: " + ("screenshot taken" if shot.get("shot_id") else str(shot.get("error"))))
    if ev.get("diff"):
        lines.append(f"Diff (may be cut):\n{ev['diff']}")
    return "\n\n".join(lines)


def _parse_json(text: str) -> dict[str, Any] | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) and data.get("verdict") else None


async def _judge(brief: str) -> dict[str, Any] | None:
    """Ask the reviewer model for a verdict; None when it gives no usable one."""
    from agent.loop import _resolve_role_model
    from packages.ai.failover_client import failover_chat_completion

    payload = {
        "model": _resolve_role_model("judge"),
        "messages": [{"role": "system", "content": _JUDGE_PROMPT}, {"role": "user", "content": brief}],
        "stream": False,
    }
    for _ in range(3):
        try:
            fo = await failover_chat_completion(payload, timeout_sec=120.0)
        except Exception as exc:  # noqa: BLE001 - no provider: no verdict, the task waits
            log.warning("Independent verifier: no reviewer model available: %s", exc)
            return None
        parsed = _parse_json(fo.text or "")
        if parsed:
            return parsed
    return None


def _as_run(judge: dict[str, Any], pr: tuple[str, int] | None, ev: dict[str, Any], runtime: str) -> dict[str, Any]:
    checks = ev.get("checks")
    files = ev.get("files") or []
    step: dict[str, Any] = {
        "description": f"change made by the {runtime} runtime",
        "status": "applied" if files else "reported",
        "changed_files": files,
        "executed_checks": list(checks.checks) if checks else [],
    }
    if checks and checks.issues:
        # Tests that fail are a FAIL, whatever the reviewer concluded.
        judge = {**judge, "verdict": "REJECTED",
                 "notes": "Tests failed on the change: " + " | ".join(i[:300] for i in checks.issues)}
    return {"judge": judge, "steps": [step], "ui_evidence": ev.get("ui") or [],
            "pr_url": f"{pr[0]}/pull/{pr[1]}" if pr else None, "commits": []}


async def verify(task: Any, result: Any) -> dict[str, Any] | None:
    """Verify a runtime's work; return an agent-loop-shaped result or None.

    None means no verdict could be formed (no reviewer model answered), so the
    task waits for a person as before. Never raises.
    """
    try:
        return await asyncio.wait_for(_verify(task, result), timeout=_TIMEOUT_S)
    except Exception as exc:  # noqa: BLE001 - verification must never break task completion
        log.warning("Independent verifier failed for %s: %s", getattr(task, "task_id", "?"), exc)
        return None


async def _verify(task: Any, result: Any) -> dict[str, Any] | None:
    pr = find_pull_request(result)
    ev = await _exercise(pr) if pr else {"gap": "the runtime did not link a pull request"}
    judge = await _judge(_brief(task, result, pr, ev))
    if judge is None:
        return None
    run = _as_run(judge, pr, ev, str(getattr(result, "runtime_id", "runtime")))
    if ev.get("gap"):
        run["verifier_gap"] = ev["gap"]
    return run
