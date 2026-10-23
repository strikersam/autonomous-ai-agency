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


async def _current_text(runner: Any, path: str) -> str:
    """The file's current text through the runner's own read path (sandbox-aware); '' when absent."""
    try:
        text = await runner._dispatch_tool("read_file", {"path": path})
    except Exception:  # noqa: BLE001 - a new file has no current text
        return ""
    return text if isinstance(text, str) else ""


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
    store = get_approval_store()
    request = store.create(
        agent_id=str(getattr(identity, "agent_id", "agent:unknown")),
        owner=str(getattr(identity, "owner", "system")),
        session_id=str(getattr(identity, "session_id", "")),
        surface="filesystem", action=f"code_mode.{tool}",
        reason="a run_code program proposed this write (Code Mode phase 6)",
        rule_id="code_mode.writes.require_approval",
        arguments={"path": path, "diff": diff[:4000]},
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
    original = await _current_text(runner, path)
    new, error = proposed_content(tool, args, original)
    if new is None:
        return GateOutcome({"path": path, "diff": "", "error": error} if tool == "edit_file" else f"[{tool} not applied: {error}]")
    passed, issues = await _verifier_verdict(runner, verifier_model, goal, step, path, original, new)
    if not passed:
        listed = "; ".join(str(i) for i in issues[:5]) or "no reason given"
        return GateOutcome(f"[{tool} not applied: verification did not pass — {listed}]")
    if require_approval:
        approved, ref = await human_approval(runner, tool, path, original, new)
        if not approved:
            return GateOutcome(f"[{tool} not applied: approval {ref}]")
    result = await runner._run_tool(tool, args, user_id=user_id, memory_store=memory_store)
    failed = isinstance(result, str) and result.startswith(("[tool error", "[governance]"))
    errored = isinstance(result, dict) and result.get("error")
    return GateOutcome(result, None if failed or errored else path)
