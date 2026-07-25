"""services/ceo_micromanager.py — the CEO's micro-management brain.

This module gives the CEO the three capabilities it was missing: it *splits*
work into subtasks small enough to actually finish, it *assigns* each subtask
to the cheapest tier that can plausibly do it, and it *refuses to accept slop*
— a subtask whose result fails the quality gate is re-delegated one tier up
instead of being silently recorded as done.

The design follows the MicroManager orchestration pattern (a delegating
orchestrator plus a ladder of implementer tiers), mapped onto the runtimes and
roles this repository already has:

    Tier ladder      intern → junior → midlevel → senior
    Runtime routing  ``runtimes.manager.RuntimeManager`` (unchanged)
    Role routing     ``services.ceo_dispatcher.ROLE_RUNTIME_PREFERENCE``

Nothing here executes work. ``CEODispatcher`` owns execution; this module owns
the decisions: *what* the subtasks are, *who* gets each one, *whether* the
result is good enough, and *what happens* when it is not.

Configuration boundary
----------------------
Per the repository constitution, environment access is centralised: every
``os.environ`` read for micro-management lives in :class:`MicroManagerConfig`
and nowhere else in this package.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("agency.ceo.micromanager")


# ── Tier ladder ───────────────────────────────────────────────────────────────


class Tier(str, Enum):
    """Implementer tiers, ordered cheapest-and-narrowest to most-capable.

    A subtask starts at the lowest tier that can plausibly complete it and is
    escalated one rung at a time when it fails or produces slop.
    """

    INTERN = "intern"
    JUNIOR = "junior"
    MIDLEVEL = "midlevel"
    SENIOR = "senior"


#: The escalation order. ``next_tier`` walks this list; it is also the hard cap
#: on how many attempts a single subtask can ever consume.
TIER_LADDER: list[Tier] = [Tier.INTERN, Tier.JUNIOR, Tier.MIDLEVEL, Tier.SENIOR]


@dataclass(frozen=True)
class TierProfile:
    """Execution envelope for one tier.

    ``runtimes`` is a preference list handed to ``RuntimeManager`` as
    ``provider_preference``; the manager falls back through its own policy when
    the preferred runtime is unhealthy, so an unavailable runtime degrades
    rather than fails.
    """

    tier: Tier
    runtimes: list[str]
    max_steps: int
    #: Soft ceiling on how many files one subtask at this tier may touch. The
    #: decomposer uses it to decide when to split further.
    max_files: int
    #: Human-readable brief describing how much latitude the tier has. Injected
    #: into the subtask brief so the executing agent knows its own remit.
    remit: str


TIER_PROFILES: dict[Tier, TierProfile] = {
    Tier.INTERN: TierProfile(
        tier=Tier.INTERN,
        runtimes=["internal_agent"],
        max_steps=3,
        max_files=1,
        remit=(
            "You implement exactly what the brief specifies and nothing else. "
            "Do not redesign, refactor neighbouring code, or expand the scope. "
            "If the brief is ambiguous or you cannot finish, stop and report "
            "precisely what blocked you — a clear failure report is a success."
        ),
    ),
    Tier.JUNIOR: TierProfile(
        tier=Tier.JUNIOR,
        runtimes=["internal_agent", "hermes"],
        max_steps=6,
        max_files=1,
        remit=(
            "You implement the brief and fix errors you cause along the way. "
            "You may choose the details of the implementation, but not the "
            "scope. If the same error recurs three times, stop and report it "
            "with the exact message rather than continuing to guess."
        ),
    ),
    Tier.MIDLEVEL: TierProfile(
        tier=Tier.MIDLEVEL,
        runtimes=["hermes", "internal_agent", "claude_code"],
        max_steps=10,
        max_files=3,
        remit=(
            "You implement the brief across the files it names, choosing your "
            "own approach within the stated scope. You are expected to read "
            "surrounding code before editing it and to keep existing behaviour "
            "intact. Report anything you found that the brief did not "
            "anticipate."
        ),
    ),
    Tier.SENIOR: TierProfile(
        tier=Tier.SENIOR,
        runtimes=["claude_code", "hermes", "internal_agent"],
        max_steps=20,
        max_files=10,
        remit=(
            "You own this outcome. Read as much of the codebase as you need to "
            "understand the real problem before changing anything, work across "
            "as many files as correctness requires, and leave the change fully "
            "tested. If earlier attempts failed, diagnose why they failed "
            "before re-attempting the same approach."
        ),
    ),
}


def tier_profile(tier: Tier | str) -> TierProfile:
    """Return the :class:`TierProfile` for *tier*, defaulting to MIDLEVEL."""
    if isinstance(tier, str):
        try:
            tier = Tier(tier.strip().lower())
        except ValueError:
            tier = Tier.MIDLEVEL
    return TIER_PROFILES[tier]


def next_tier(current: Tier | str) -> Tier | None:
    """Return the next tier up the ladder, or ``None`` at the top.

    ``None`` means the subtask has exhausted the ladder: the CEO must stop
    escalating and record a hard failure rather than loop.
    """
    if isinstance(current, str):
        try:
            current = Tier(current.strip().lower())
        except ValueError:
            return Tier.SENIOR
    idx = TIER_LADDER.index(current)
    if idx + 1 >= len(TIER_LADDER):
        return None
    return TIER_LADDER[idx + 1]


def resolve_runtime(role: str, tier: Tier | str, role_preference: dict[str, list[str]]) -> str:
    """Pick the runtime for a subtask from its role and its tier.

    Routing stays role-driven — ``ROLE_RUNTIME_PREFERENCE`` remains the single
    source of truth for which runtimes can serve which role, so a security
    subtask never lands somewhere a security subtask should not go. The tier
    only chooses *within* that list: the two junior tiers take the cheapest
    entry (``internal_agent`` when the role permits it), and midlevel and above
    take the role's first and most capable preference.

    Deriving the runtime from the tier alone would have silently re-routed
    every dev subtask away from ``claude_code``, which is a routing change
    nobody asked for.
    """
    prefs = role_preference.get(role) or role_preference.get("dev") or ["internal_agent"]
    if isinstance(tier, str):
        try:
            tier = Tier(tier.strip().lower())
        except ValueError:
            tier = Tier.MIDLEVEL
    if tier in (Tier.INTERN, Tier.JUNIOR):
        return "internal_agent" if "internal_agent" in prefs else prefs[-1]
    return prefs[0]


def starting_tier(complexity: str, role: str = "dev") -> Tier:
    """Pick the entry rung for a subtask.

    Read-only reconnaissance is cheap and starts at the bottom. Security work
    starts at the top because a cheap wrong answer there is expensive. Everything
    else keys off the classifier's complexity.
    """
    role = (role or "dev").strip().lower()
    if role in {"scout", "researcher"}:
        return Tier.INTERN
    if role == "security":
        return Tier.SENIOR
    return {
        "low": Tier.JUNIOR,
        "medium": Tier.MIDLEVEL,
        "high": Tier.SENIOR,
    }.get((complexity or "medium").strip().lower(), Tier.MIDLEVEL)


# ── Configuration ─────────────────────────────────────────────────────────────


def _env_int(name: str, default: int, *, low: int, high: int) -> int:
    """Read a bounded int from the environment, clamping out-of-range values.

    Clamping rather than raising matters here: these knobs bound token spend on
    a loop that runs unattended, so a typo in a deploy env var must not be able
    to uncap the fan-out.
    """
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
class MicroManagerConfig:
    """All micro-management tunables, resolved from the environment once.

    Every bound here exists to stop an unattended 24x7 loop from running away.
    Changing a default is a spend decision, not a style decision.
    """

    #: Hard cap on subtasks produced by one decomposition.
    max_subtasks: int = 6
    #: Hard cap on attempts for a single subtask, across all tiers.
    max_attempts_per_subtask: int = 3
    #: Minimum characters of output before a result is considered substantive.
    min_output_chars: int = 24
    #: Penalise a code-writing subtask that changed source files but no tests.
    require_tests_for_code: bool = True
    #: Ask the brain to decompose. Falls back to the deterministic split when
    #: disabled or when the brain is unreachable.
    llm_decomposition: bool = True
    #: Seconds allowed for the decomposition call before falling back.
    decomposition_timeout_s: float = 45.0
    #: Master switch for re-delegating rejected subtasks up the tier ladder.
    #: Disabling it keeps the quality verdicts (they still land in the ledger)
    #: but stops the CEO from spending a second and third attempt on them.
    escalation_enabled: bool = True

    @classmethod
    def from_env(cls) -> "MicroManagerConfig":
        # Brain-driven decomposition is off under TESTING so unit tests get the
        # deterministic split without reaching for a provider. Production is
        # unaffected — TESTING is only set by conftest.
        testing = _env_flag("TESTING", False)
        return cls(
            max_subtasks=_env_int("CEO_MAX_SUBTASKS", 6, low=1, high=12),
            max_attempts_per_subtask=_env_int(
                "CEO_MAX_ATTEMPTS_PER_SUBTASK", 3, low=1, high=len(TIER_LADDER)
            ),
            min_output_chars=_env_int("CEO_MIN_OUTPUT_CHARS", 24, low=0, high=4000),
            require_tests_for_code=_env_flag("CEO_REQUIRE_TESTS_FOR_CODE", True),
            llm_decomposition=_env_flag("CEO_LLM_DECOMPOSITION", not testing),
            decomposition_timeout_s=float(
                _env_int("CEO_DECOMPOSITION_TIMEOUT_S", 45, low=5, high=300)
            ),
            escalation_enabled=_env_flag("CEO_ESCALATION_ENABLED", True),
        )


def get_config() -> MicroManagerConfig:
    """Resolve config fresh on each call so env changes take effect on redeploy."""
    return MicroManagerConfig.from_env()


# ── Subtask brief ─────────────────────────────────────────────────────────────


@dataclass
class SubtaskPlan:
    """One unit of delegated work, before it has been briefed or executed."""

    subtask_id: str
    title: str
    #: What the executing agent must accomplish, in the CEO's words.
    scope: str
    #: Observable end state the CEO will check the result against.
    outcome: str
    role: str = "dev"
    tier: Tier = Tier.MIDLEVEL
    #: Files the CEO expects to be touched. Advisory — used for the anti-slop
    #: check and to keep subtasks small, not enforced as a hard boundary.
    files: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    #: True when the subtask is expected to modify source files. Read-only
    #: research subtasks set this False so the anti-slop gate does not demand
    #: file changes from them.
    writes_code: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "subtask_id": self.subtask_id,
            "title": self.title,
            "scope": self.scope,
            "outcome": self.outcome,
            "role": self.role,
            "tier": self.tier.value,
            "files": list(self.files),
            "dependencies": list(self.dependencies),
            "writes_code": self.writes_code,
        }


def build_subtask_brief(
    plan: SubtaskPlan,
    *,
    goal: str,
    upstream: list[tuple[str, str]] | None = None,
    previous_failure: str | None = None,
) -> str:
    """Render the self-contained brief handed to an executing agent.

    Every delegated subtask carries the same seven sections. The structure is
    the point: an agent that receives only "implement X" invents its own scope,
    and inventing scope is what produces slop. Context isolation is deliberate —
    the executing agent sees the goal and its upstream results, never the CEO's
    whole conversation.

    ``upstream`` is a list of ``(subtask_id, summary)`` pairs from completed
    dependencies. ``previous_failure`` is set on a re-delegation so the higher
    tier knows what already did not work.
    """
    profile = tier_profile(plan.tier)
    parts: list[str] = []

    parts.append("# Context")
    parts.append(
        f"You are one specialist in a coordinated team. The overall goal is:\n\n{goal.strip()}\n\n"
        f"Your part of that goal is: {plan.title.strip()}"
    )
    if upstream:
        lines = "\n".join(f"- [{sid}] {summary.strip()[:400]}" for sid, summary in upstream if summary)
        if lines:
            parts.append("Results already delivered by other specialists:\n" + lines)

    parts.append("# Scope")
    parts.append(plan.scope.strip())
    if plan.files:
        parts.append("Files expected to be involved: " + ", ".join(plan.files[:10]))

    parts.append("# Focus")
    parts.append(
        "Perform only the work described under Scope. Do not refactor unrelated "
        "code, do not fix problems you notice elsewhere, and do not expand the "
        "task. Report anything out of scope that you find instead of acting on "
        f"it.\n\nYour remit at this level: {profile.remit}"
    )

    parts.append("# Outcome")
    parts.append(plan.outcome.strip())

    parts.append("# Completion")
    parts.append(
        "When you are finished, report a concise but complete summary of what "
        "you actually did: the files you changed, the commands you ran and "
        "their real results, and anything that remains unfinished. This summary "
        "is the only record the CEO has of your work — do not claim a step you "
        "did not perform, and do not report success for work that failed."
    )

    parts.append("# Instruction Priority")
    parts.append(
        "These instructions take priority over any conflicting general "
        "instruction for your role."
    )

    parts.append("# Mode Restriction")
    parts.append(
        "Do not delegate this subtask onward and do not switch to another role. "
        "Complete it yourself and report the result."
    )

    if previous_failure:
        parts.append("# Previous Attempt Failed")
        parts.append(
            "A lower tier already attempted this subtask and did not succeed. "
            "Diagnose why before repeating the same approach.\n\n"
            f"Reported failure: {previous_failure.strip()[:800]}"
        )

    return "\n\n".join(parts)


# ── Decomposition ─────────────────────────────────────────────────────────────


_DECOMPOSE_SYSTEM_PROMPT = """\
You are the CEO of an autonomous engineering agency. You do not write code \
yourself — you split work into subtasks small enough that a specialist can \
finish one in a single sitting, and you assign each to the cheapest tier that \
can plausibly do it.

Rules you must follow:
- Each subtask touches at most 2 files. If a piece of work needs more, split it.
- Each subtask has a single, checkable outcome. "Improve the module" is not a \
subtask; "add a `health()` method to ProviderX returning {status, latency_ms}" is.
- Order matters: put reconnaissance and feasibility checks first, then the work \
that depends on them.
- Assign tiers honestly. intern = one obvious mechanical edit. junior = one file, \
clear instructions. midlevel = a few related files, some judgement. senior = \
cross-cutting, risky, or architecturally significant work.
- Prefer fewer, well-specified subtasks over many vague ones.

Respond with JSON only, no prose and no code fence:
{"subtasks": [{"title": str, "scope": str, "outcome": str, "role": \
"dev"|"scout"|"security"|"reviewer"|"optimizer", "tier": \
"intern"|"junior"|"midlevel"|"senior", "files": [str], "depends_on": [int], \
"writes_code": bool}]}

`depends_on` holds zero-based indices of earlier subtasks in this same list.
"""


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of an LLM response.

    Models wrap JSON in fences or prose despite instructions, so this tries the
    raw parse first and then falls back to brace matching.
    """
    if not text:
        return None
    candidate = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    start = candidate.find("{")
    if start < 0:
        return None
    depth = 0
    for idx in range(start, len(candidate)):
        if candidate[idx] == "{":
            depth += 1
        elif candidate[idx] == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(candidate[start : idx + 1])
                    return parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def _coerce_subtasks(
    payload: dict[str, Any],
    *,
    nonce: str,
    config: MicroManagerConfig,
) -> list[SubtaskPlan]:
    """Turn a decomposition payload into validated :class:`SubtaskPlan` objects.

    Anything malformed is dropped rather than repaired: a subtask with no scope
    would be delegated as an empty instruction, which is worse than not
    delegating it at all.
    """
    raw = payload.get("subtasks")
    if not isinstance(raw, list):
        return []
    plans: list[SubtaskPlan] = []
    index_to_id: dict[int, str] = {}
    for idx, item in enumerate(raw[: config.max_subtasks]):
        if not isinstance(item, dict):
            continue
        scope = str(item.get("scope") or "").strip()
        if not scope:
            continue
        title = str(item.get("title") or scope[:60]).strip()
        subtask_id = f"ceo-{nonce}-{idx + 1}"
        index_to_id[idx] = subtask_id
        role = str(item.get("role") or "dev").strip().lower()
        try:
            tier = Tier(str(item.get("tier") or "midlevel").strip().lower())
        except ValueError:
            tier = Tier.MIDLEVEL
        files = [str(f).strip() for f in (item.get("files") or []) if str(f).strip()]
        deps_raw = item.get("depends_on") or []
        dependencies = [
            index_to_id[d]
            for d in deps_raw
            if isinstance(d, int) and d in index_to_id and d < idx
        ]
        plans.append(
            SubtaskPlan(
                subtask_id=subtask_id,
                title=title[:120],
                scope=scope,
                outcome=str(item.get("outcome") or "").strip()
                or "The scope above is fully implemented and verified.",
                role=role,
                tier=tier,
                files=files[:10],
                dependencies=dependencies,
                writes_code=bool(item.get("writes_code", role not in {"scout", "reviewer"})),
            )
        )
    return plans


def fallback_decomposition(
    request: str,
    *,
    complexity: str = "medium",
    role: str = "dev",
    nonce: str | None = None,
) -> list[SubtaskPlan]:
    """Deterministic recon-then-implement split used when the brain is unavailable.

    This is intentionally conservative — it is the safety net, not the strategy.
    It preserves the shape of the previous hardcoded CEO decomposition (a
    read-only scout pass feeding a dev pass) so behaviour degrades to the known
    baseline rather than to nothing.
    """
    nonce = nonce or f"{int(time.time() * 1000) & 0xFFFFFF:x}"
    scout_id = f"ceo-{nonce}-1"
    dev_id = f"ceo-{nonce}-2"
    return [
        SubtaskPlan(
            subtask_id=scout_id,
            title="Analyse the request",
            scope=(
                f"Analyse this request without changing any files:\n\n{request[:1500]}\n\n"
                "Report the scope, the files likely affected, the risks, and the "
                "acceptance criteria. Keep it under 300 words."
            ),
            outcome="A written analysis naming the affected files and the acceptance criteria.",
            role="scout",
            tier=Tier.INTERN,
            writes_code=False,
        ),
        SubtaskPlan(
            subtask_id=dev_id,
            title="Implement the request",
            scope=(
                f"Implement this request:\n\n{request}\n\n"
                "Follow the existing project conventions. Add or update tests in "
                "tests/. Add an entry to docs/changelog.md under ## [Unreleased]."
            ),
            outcome=(
                "The request is implemented, tests covering it exist and pass, and "
                "the changelog records the change."
            ),
            role=role,
            tier=starting_tier(complexity, role),
            dependencies=[scout_id],
            writes_code=True,
        ),
    ]


async def decompose(
    request: str,
    *,
    goal: str = "",
    complexity: str = "medium",
    domain: str = "general",
    role: str = "dev",
    config: MicroManagerConfig | None = None,
) -> tuple[list[SubtaskPlan], str]:
    """Split *request* into subtasks. Returns ``(plans, strategy)``.

    ``strategy`` is ``"llm"`` when the brain produced the split and
    ``"fallback"`` when the deterministic split was used — the caller records it
    so a brain outage is visible in the ledger rather than silently degrading
    the agency to two-subtask batches forever.
    """
    config = config or get_config()
    nonce = f"{int(time.time() * 1000) & 0xFFFFFF:x}"

    if not config.llm_decomposition:
        return fallback_decomposition(request, complexity=complexity, role=role, nonce=nonce), "fallback"

    try:
        import asyncio

        from backend.server import call_llm

        user_prompt = (
            f"Domain: {domain}\nAssessed complexity: {complexity}\n"
            + (f"Goal: {goal}\n" if goal else "")
            + f"\nRequest to decompose:\n{request[:4000]}\n\n"
            f"Produce at most {config.max_subtasks} subtasks."
        )
        text = await asyncio.wait_for(
            call_llm(
                [
                    {"role": "system", "content": _DECOMPOSE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
            ),
            timeout=config.decomposition_timeout_s,
        )
        payload = _extract_json_object(text or "")
        if payload:
            plans = _coerce_subtasks(payload, nonce=nonce, config=config)
            if plans:
                log.info("CEO: decomposed request into %d subtask(s) via brain", len(plans))
                return plans, "llm"
        log.warning("CEO: decomposition response unusable; using deterministic split")
    except Exception as exc:  # noqa: BLE001 — decomposition must never hard-fail
        log.warning("CEO: brain decomposition unavailable (%s); using deterministic split", exc)

    return fallback_decomposition(request, complexity=complexity, role=role, nonce=nonce), "fallback"


# The quality gate and the escalation ladder live in ``services.ceo_quality``,
# which imports *from* this module. They are deliberately NOT re-exported here:
# a bottom-of-file `from services.ceo_quality import ...` creates a genuine
# import cycle — importing ``services.ceo_quality`` first runs this module to
# the bottom, which then imports back from the still-initialising quality
# module and raises ImportError. Import them from ``services.ceo_quality``.

__all__ = [
    "MicroManagerConfig", "SubtaskPlan", "TIER_LADDER", "TIER_PROFILES", "Tier",
    "TierProfile", "build_subtask_brief", "decompose", "fallback_decomposition",
    "get_config", "next_tier", "resolve_runtime", "starting_tier", "tier_profile",
]
