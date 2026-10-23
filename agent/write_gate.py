"""agent/write_gate.py — file writes chosen in the executor's tool loop pass the Verifier first.

The step's main edit path checks syntax, safety and the Verifier before
``apply_diff`` (CLAUDE.md rules 16 and 18). The tool loop also offers
``edit_file`` / ``write_file`` / ``apply_diff``, and those used to write
straight to disk. This gate gives them the same order: build the proposed
content without writing, check it, and only on a ``pass`` dispatch the real
write through ``AgentRunner._run_tool`` (governance, sandbox routing).

Code Mode phase 6: while ``AGENT_CODE_MODE_WRITES_ENABLED`` is on (default
off), a ``run_code`` program may call ``edit_file`` / ``write_file``. Those
calls write nothing: each is queued as a proposal (at most
``MAX_PROPOSALS``), and after the program ends every proposal goes through
this gate *and* a human approval in the governance approval store, whatever
the policy mode. An approval that nobody answers expires, and that is a denial.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("qwen-proxy")

WRITE_TOOLS = frozenset({"edit_file", "write_file", "apply_diff"})
# The writes a run_code program may propose (phase 6); apply_diff stays a direct call.
PROPOSAL_TOOLS = frozenset({"edit_file", "write_file"})
MAX_PROPOSALS = 5
PREVIEW_MAX_CHARS = 2_000_000
# The approval store scrubs each string to 2,000 chars and each list to 50 items, so a
# diff travels as chunks; a larger one is refused rather than shown in part.
_DIFF_CHUNK = 1800
_MAX_DIFF_CHUNKS = 50


def code_mode_writes_enabled() -> bool:
    """Read AGENT_CODE_MODE_WRITES_ENABLED at call time (live control); off when unreadable."""
    try:
        from packages.config import settings

        return settings.agent_code_mode_writes
    except Exception as exc:  # noqa: BLE001 - unreadable setting keeps writes off
        log.debug("AGENT_CODE_MODE_WRITES_ENABLED unreadable: %s", exc)
        return False


def queue_proposal(proposals: list[dict[str, Any]], tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """What a program's write call returns: a receipt, never a write."""
    from agent.code_mode import CodeModeError

    if len(proposals) >= MAX_PROPOSALS:
        raise CodeModeError(f"at most {MAX_PROPOSALS} proposed writes per program")
    proposals.append({"tool": tool, "args": dict(args)})
    return {
        "proposal": len(proposals), "status": "queued", "path": str(args.get("path", "")),
        "note": "applied after the program, only if the verifier passes it and a human approves",
    }


@dataclass
class GateOutcome:
    """What the tool loop records: the observation, and the path when a write landed."""

    result: Any
    applied_path: str | None = None


def proposed_content(tool: str, args: dict[str, Any], original: str) -> tuple[str | None, str]:
    """The file as the write would leave it, or ``(None, error)``; nothing is written."""
    if tool == "edit_file":
        from agent.tools import plan_string_edit

        updated = plan_string_edit(original, str(args.get("old_string", "")), str(args.get("new_string", "")))
        if updated is None:
            return None, "old_string not found; check indentation and whitespace and try again"
        return updated, ""
    key = "content" if tool == "write_file" else "new_content"
    if key not in args:
        return None, f"{tool} needs a {key!r} argument"
    return str(args[key]), ""


class PreviewUnavailable(Exception):
    """The current file could not be read, so the write cannot be checked against it."""


_NOT_FOUND_MARKERS = ("not found", "notfound", "no such file", "does not exist")


async def _governed(runner: Any, tool: str, args: dict[str, Any], thunk: Any) -> Any:
    """Run *thunk* behind the governance gate under *tool*/*args*, as ``_dispatch_tool`` does.

    Used for sandbox I/O the gate performs directly, so policy is checked against the
    operation the agent asked for (``edit_file``), not the transport (``write_file``).
    """
    import time

    from packages.governance.enforcement import get_gate, governance_enabled, resolve_identity_for_runner

    if not governance_enabled():
        return await thunk()
    gate = get_gate()
    identity = resolve_identity_for_runner(runner, source_ip=None)
    guard = await gate.guard(identity, tool, args)
    if not guard.allowed:
        return guard.denial_message
    started, result, error = time.monotonic(), None, None
    try:
        result = await thunk()
        return result
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        gate.record_result(identity, tool, args, guard.decision, result=str(result)[:200],
                           error=error, duration_ms=(time.monotonic() - started) * 1000)


async def _sandbox_text(runner: Any, path: str) -> str:
    """The sandbox's own copy, never the host fallback the dispatcher would use."""
    try:
        text = await _governed(runner, "read_file", {"path": path},
                               lambda: runner._mcp.call_tool("read_file", {"path": path}))
    except Exception as exc:  # noqa: BLE001 - only a confirmed absence is an empty baseline
        if any(m in str(exc).lower() for m in _NOT_FOUND_MARKERS):
            return ""
        raise PreviewUnavailable(f"the sandbox could not read it: {str(exc)[:160]}") from exc
    return text


async def _current_text(runner: Any, path: str) -> str:
    """The file's whole current text, read through the governed, sandbox-aware dispatch.

    Only a file that is confirmed absent reads as ''. A governance denial, a tool
    error or a file too large to preview raises :class:`PreviewUnavailable`, so a
    write is never verified (or shown to an approver) against a blank or partial
    baseline, and a denied read never leaks content into the Verifier prompt.
    """
    try:
        if getattr(runner, "_mcp", None) is not None:
            text = await _sandbox_text(runner, path)
        else:
            text = await runner._dispatch_tool("read_file", {"path": path, "max_chars": PREVIEW_MAX_CHARS + 1})
    except PreviewUnavailable:
        raise
    except FileNotFoundError:
        return ""
    except Exception as exc:  # noqa: BLE001 - any other failure is "cannot check", never "empty"
        raise PreviewUnavailable(str(exc)[:200]) from exc
    if not isinstance(text, str) or text.startswith(("[governance]", "[tool error")):
        raise PreviewUnavailable(str(text)[:200])
    if len(text) > PREVIEW_MAX_CHARS:
        raise PreviewUnavailable(f"the file is larger than {PREVIEW_MAX_CHARS} characters")
    return text


async def _verifier_verdict(runner: Any, model: str, goal: str, step: dict[str, Any],
                            path: str, original: str, new: str) -> tuple[bool, list[str]]:
    from agent.models import VerificationResult
    from agent.prompts import build_verification_prompt

    issues = runner._local_syntax_check(path, new) + runner._local_safety_check(path, new)
    if issues:
        return False, issues
    try:
        raw = await runner._chat_json(model, build_verification_prompt(
            goal=goal, step=step, target_file=path,
            original_content=original, new_content=new, syntax_issues=[],
        ))
        verdict = VerificationResult.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 - no verdict is not a pass
        log.warning("write gate: verifier gave no usable verdict for %s: %s", path, exc)
        return False, ["the verifier did not return a usable verdict"]
    return verdict.status == "pass", list(verdict.issues)


async def human_approval(runner: Any, tool: str, path: str, original: str, new: str) -> tuple[bool, str]:
    """Hold for a named person's decision in the governance approval store (timeout denies)."""
    import difflib

    from packages.config import settings
    from packages.governance.approvals import ApprovalStatus, get_approval_store
    from packages.governance.enforcement import resolve_identity_for_runner

    if settings.governance_auto_approve:
        # The same configured, audited, off-by-default escape hatch the governance gate honours.
        return True, "auto-approve"
    identity = resolve_identity_for_runner(runner, source_ip=None)
    diff = "\n".join(difflib.unified_diff(original.splitlines(), new.splitlines(), f"a/{path}", f"b/{path}", lineterm=""))
    chunks = [diff[i:i + _DIFF_CHUNK] for i in range(0, len(diff), _DIFF_CHUNK)] or [""]
    if len(chunks) > _MAX_DIFF_CHUNKS:
        return False, f"not requested: the diff is too large to review in full ({len(diff)} chars); propose smaller edits"
    store = get_approval_store()
    request = store.create(
        agent_id=str(getattr(identity, "agent_id", "agent:unknown")),
        owner=str(getattr(identity, "owner", "system")),
        session_id=str(getattr(identity, "session_id", "")),
        surface="filesystem", action=f"code_mode.{tool}",
        reason="a run_code program proposed this write (Code Mode phase 6)",
        rule_id="code_mode.writes.require_approval",
        arguments={"path": path, "diff_chunks": chunks},
        task_id=getattr(identity, "task_id", None), repo=getattr(identity, "repo", None),
        branch=getattr(identity, "branch", None), ttl_s=settings.governance_approval_ttl_s,
    )
    status = await store.wait(request.approval_id)
    return status is ApprovalStatus.APPROVED, f"{request.approval_id} {status.value}"


async def gated_write(runner: Any, tool: str, args: dict[str, Any], *, goal: str, step: dict[str, Any],
                      verifier_model: str, user_id: str | None, memory_store: Any,
                      require_approval: bool = False) -> GateOutcome:
    """Verify a write (and, for a program's proposal, get a human's yes), then perform it.

    A refusal at any stage is an observation, never a write.
    """
    path = str(args.get("path", "")).strip()
    if not path:
        return GateOutcome(f"[{tool} not applied: a path is required]")
    try:
        original = await _current_text(runner, path)
    except PreviewUnavailable as exc:
        return GateOutcome(f"[{tool} not applied: the current file could not be read to check the change — {exc}]")
    new, error = proposed_content(tool, args, original)
    if new is None:
        return GateOutcome({"path": path, "diff": "", "error": error} if tool == "edit_file" else f"[{tool} not applied: {error}]")
    passed, issues = await _verifier_verdict(runner, verifier_model, goal, step, path, original, new)
    if not passed:
        listed = "; ".join(str(i) for i in issues[:5]) or "no reason given"
        return GateOutcome(f"[{tool} not applied: verification did not pass — {listed}]")
    if require_approval:
        try:
            approved, ref = await human_approval(runner, tool, path, original, new)
        except Exception as exc:  # noqa: BLE001 - no decision is a denial, never a write
            log.warning("write gate: approval for %s failed, denying: %s", path, exc)
            approved, ref = False, "could not be requested"
        if not approved:
            return GateOutcome(f"[{tool} not applied: approval {ref}]")
    if getattr(runner, "_mcp", None) is not None:
        # In a sandbox, write the exact verified bytes into the sandbox itself: the registry's
        # edit_file/apply_diff would hit the host copy, and the dispatcher would fall back to it.
        # Policy is checked against the operation asked for, not the transport.
        try:
            result = await _governed(runner, tool, args, lambda: runner._mcp.call_tool(
                "write_file", {"path": path, "content": new}))
        except Exception as exc:  # noqa: BLE001 - a failed sandbox write is reported, never retried on the host
            result = f"[tool error: sandbox write failed: {str(exc)[:160]}]"
    else:
        result = await runner._run_tool(tool, args, user_id=user_id, memory_store=memory_store)
    failed = isinstance(result, str) and result.startswith(("[tool error", "[governance]"))
    errored = isinstance(result, dict) and result.get("error")
    return GateOutcome(result, None if failed or errored else path)
