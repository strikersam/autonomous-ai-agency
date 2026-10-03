"""agent/sam_orchestrator.py — SAM's grounded agency-orchestration actions.

SAM fronts the agency the way the CEO loop runs it. Beyond the alerts bell
(``agent.sam_actions``), an admin can ask SAM to:

* ``delegate`` — "create a task to …", "get the team to …": queue one agent
  task through ``TaskWorkflowService``, so the same outward-facing gate the CEO
  uses still parks deploys/auth work for a human.
* ``triage``   — "triage the queue", "approve what doesn't need me": run the
  CEO's own rule-based triage (``tasks.autonomy_triage``) once, now.
* ``brief``    — "brief me", "sitrep": a live, non-LLM report of the CEO loop,
  the task queue and the approval gate.

Like ``sam_actions``, intent detection is keyword-based on purpose: anything
that creates or approves work must not hinge on a free-tier LLM choosing to.

``OPERATOR_PRINCIPLES`` is how SAM decides "like the operator": it restates the
standing directives the operator has already encoded in this repo (CLAUDE.md,
the CEO triage policy) so the LLM path reasons from them, not from a generic
assistant persona.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time

log = logging.getLogger("qwen-proxy")

OPERATOR_PRINCIPLES = """## How the Commander decides (apply these, don't recite them)
- Keep the agency moving on its own. Only ask the Commander at merge time, or for
  deploys, auth, secrets, migrations and anything outward-facing.
- Act, don't deflect: when something is broken, queue the fix; never tell the
  Commander to do it themselves.
- Challenge a weak assumption before agreeing with it. Say what is missing.
- Never report a check that was not run. Separate what you know from what you guess.
- Short, plain answers. No filler, no flattery.
- Production first: never weaken auth, never expose secrets, never bypass CI.
"""

_DELEGATE_RE = re.compile(
    r"\b(?:create|add|open|queue|make)\s+(?:a\s+|an\s+|one\s+)?(?:new\s+)?task\s+"
    r"(?:to|for|that|:)\s*(?P<what>.+)"
    r"|\b(?:get|have|tell|ask)\s+(?:the\s+)?(?:team|agents?|agency|ceo)\s+to\s+(?P<what2>.+)"
    r"|\bdelegate\s*:?\s*(?P<what3>.+)",
    re.IGNORECASE | re.DOTALL,
)
_TRIAGE_TERMS = (
    "triage", "approve what", "clear the approval", "clear the queue",
    "unblock the queue", "approve the parked", "approve parked",
)
_BRIEF_TERMS = (
    "brief me", "briefing", "sitrep", "status report", "agency status",
    "what's going on", "what is going on", "how is the agency", "how's the agency",
)
_DELEGATED_TAG = "sam-delegated"
# Free text has no task_type, so ``tasks.service._is_outward_facing`` cannot see
# that "deploy the service" leaves the repo. Classification fails closed: a
# delegated task runs unattended only when it opens with an internal
# engineering verb AND matches no outward pattern. Everything else is gated —
# a false positive costs one approval tap, a miss runs unattended.
_OUTWARD_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b(?:deploy\w*|roll\s*back|rollback|go\s+live|prod|production|restart\w*|reboot\w*|"
     r"shut\s*down|scale\s+(?:up|down)|stop\s+the|kill\s+the|live\s+(?:site|server|service))\b", "deploy"),
    (r"\b(?:release\w*|publish\w*|ship\s+it|tag\s+v?\d)", "release"),
    (r"\b(?:secrets?|credentials?|tokens?|api[\s_-]?keys?|passwords?|auth\w*|oauth\w*|permissions?|"
     r"access|invite\w*|revok\w*|grant\w*|ban|suspend\w*)\b", "external-write"),
    (r"\b(?:migrat\w*|delet\w*|destroy\w*|drop|truncat\w*|wipe\w*|purg\w*|eras\w*|"
     r"remove\s+(?:\w+\s+)?(?:accounts?|users?|customers?|data|records?|backups?|repos?\w*|branch\w*))\b",
     "irreversible"),
    (r"\b(?:e-?mail\w*|tweet\w*|slack|discord|telegram|sms|whatsapp|post\s+to|send\w*|message\w*|"
     r"notify\w*|announce\w*|customers?|clients?|pay\w*|charg\w*|refund\w*|invoic\w*|"
     r"purchas\w*|buy\w*|billing\s+account|dns|domain)\b", "external-write"),
    (r"\b(?:transfer\w*|wire\w*|withdraw\w*|deposit\w*|payout\w*|remit\w*|money|funds?|"
     r"balances?|bank\w*|wallets?|crypto\w*|bitcoin|eth|usdc|stripe|paypal|iban|swift)\b", "external-write"),
)
_INTERNAL_VERBS = re.compile(
    r"^(?:please\s+)?(?:fix|add|implement|refactor|write|document|improve|investigate|research|"
    r"analy[sz]e|review|test|clean\s+up|tidy|rename|optimi[sz]e|debug|audit|draft|plan|"
    r"summari[sz]e|build|design|update|upgrade|speed\s+up|cover|explain|profile|reduce|simplify)\b",
)
_UNCLASSIFIED_TAG = "risk:unclassified"


def outward_facing_tags(instruction: str) -> list[str]:
    """Gating tags *instruction* earns (fail closed); empty only for clearly internal work.

    ``risk:unclassified`` marks text that is neither recognisably outward nor
    recognisably internal engineering work — ``_is_outward_facing`` gates any
    ``risk:*`` tag, so unknown intent parks for approval instead of running.
    """
    lower = instruction.lower().strip()
    tags: list[str] = []
    for pattern, tag in _OUTWARD_PATTERNS:
        if re.search(pattern, lower) and tag not in tags:
            tags.append(tag)
    if not tags and not _INTERNAL_VERBS.match(lower):
        tags.append(_UNCLASSIFIED_TAG)
    return tags


_STATE_TIMEOUT_SEC = 8.0
_ADMIN_ONLY_REPLY = (
    "That one runs the agency, Commander, so it needs an admin account. "
    "I can still read you the alerts or answer questions."
)


def detect_orchestration_intent(text: str) -> str | None:
    """Return ``"delegate"``, ``"triage"``, ``"brief"`` or ``None``."""
    lower = f" {text.lower().strip()} "
    if _DELEGATE_RE.search(text):
        return "delegate"
    if any(term in lower for term in _TRIAGE_TERMS):
        return "triage"
    if any(term in lower for term in _BRIEF_TERMS):
        return "brief"
    return None


def extract_instruction(text: str) -> str:
    """Pull the work item out of a delegate utterance ("create a task to X" -> X)."""
    match = _DELEGATE_RE.search(text)
    if not match:
        return ""
    what = match.group("what") or match.group("what2") or match.group("what3") or ""
    return what.strip().rstrip(".!?").strip()


async def delegate_task(instruction: str, owner_id: str) -> str:
    """Queue *instruction* as an agent task and return SAM's spoken report."""
    from tasks.models import Task, TaskPriority
    from tasks.service import TaskWorkflowService
    from tasks.store import get_task_store

    if len(instruction) < 4:
        return "What should the team work on, Commander? Say 'create a task to' and the job."
    store = get_task_store()
    day = time.strftime("%Y-%m-%d", time.gmtime())
    digest = hashlib.sha256(f"{instruction.lower()}|{day}".encode()).hexdigest()[:16]
    source_id = f"sam-delegate:{digest}"
    existing = await store.find_by_source_id(source_id)
    if existing is not None:
        return f"That's already queued, Commander: {existing.title}. Track it under Work."
    outward = outward_facing_tags(instruction)
    task = Task(
        owner_id=owner_id or "sam-voice",
        title=instruction[:120],
        description=f"Delegated by the Commander through SAM.\n\nInstruction:\n{instruction}",
        prompt=instruction[:32000],
        priority=TaskPriority.MEDIUM,
        tags=["sam-voice", _DELEGATED_TAG, *outward],
        source="sam-voice",
        source_id=source_id,
        requires_approval=bool(outward),
    )
    await TaskWorkflowService(store=store).create_task(task, actor=f"sam:{owner_id}")
    stored = await store.get(task.task_id)
    if stored is not None and stored.requires_approval and not stored.execution_approved:
        return (f"Queued: {task.title}. It touches something outward-facing, "
                "so it's parked for your approval under Work.")
    return f"Queued: {task.title}. The agents will pick it up. Track it under Work."


async def run_triage() -> str:
    """Run the CEO triage pass once and report what it decided."""
    from tasks.autonomy_triage import triage_gated_tasks

    result = await triage_gated_tasks()
    if not (result.approved or result.rejected or result.left_for_human):
        return "Nothing is parked at the approval gate, Commander. The queue is moving."
    parts = [f"Triage done: approved {result.approved}, rejected {result.rejected} as duplicates."]
    if result.left_for_human:
        parts.append(f"{result.left_for_human} need you — deploys, auth or work you gated on purpose.")
    return " ".join(parts)


async def _queue_counts() -> tuple[int, int]:
    from tasks.store import get_task_store

    store = get_task_store()
    pending = await store.list_pending(limit=200)
    parked = await store.list_awaiting_approval(limit=200)
    return len(pending), len(parked)


async def build_brief() -> str:
    """Live agency report: CEO loop, queue depth, approval gate. No LLM."""
    from agent.agency import get_agency

    parts: list[str] = []
    agency = get_agency()
    if agency is None or not agency.get_status().get("running"):
        parts.append("The CEO loop is off, so nothing is being planned on its own.")
    else:
        status = agency.get_status()
        parts.append(f"The CEO loop is running, {status.get('cycle_count', 0)} cycles so far, "
                     f"{status.get('pending_directives', 0)} directives pending.")
    try:
        pending, parked = await asyncio.wait_for(_queue_counts(), timeout=_STATE_TIMEOUT_SEC)
        parts.append(f"{pending} tasks in the queue, {parked} waiting on approval.")
        if parked:
            parts.append("Say 'triage the queue' and I'll clear what doesn't need you.")
    except Exception:
        log.warning("SAM brief: task store unavailable", exc_info=True)
        parts.append("I couldn't read the task queue just now.")
    return " ".join(parts)


async def handle_orchestration_command(text: str, owner_id: str, *, is_admin: bool) -> str | None:
    """Run the orchestration action *text* asks for, or return None if none."""
    intent = detect_orchestration_intent(text)
    if intent is None:
        return None
    if not is_admin:
        return _ADMIN_ONLY_REPLY
    try:
        if intent == "delegate":
            return await delegate_task(extract_instruction(text), owner_id)
        if intent == "triage":
            return await run_triage()
        return await build_brief()
    except Exception:
        log.exception("SAM orchestration action %s failed", intent)
        return "That didn't go through, Commander. The task store isn't answering — try again shortly."
