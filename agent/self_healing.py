"""agent/self_healing.py — Self-Healing Agent (closed-loop, Autonomy Charter G2)

Translates external failure signals (CI webhooks, GitHub issue events, manual
dashboard reports, backend log errors) into improvement tasks dispatched through
ImprovementLoop — and then **closes the loop**: a heal is only marked
``resolved`` after its error signature stops recurring for a verification
window. If the signature recurs while verifying, the heal ``regressed`` and is
retried; after ``HEAL_MAX_ATTEMPTS`` it escalates to a human via Telegram.

Flow:
    CI failure webhook   → on_ci_failure()   → _dispatch_fix()  → state=fixing
    GitHub bug issue     → on_github_issue()  → _dispatch_fix()  → state=fixing
    Dashboard bug report → on_manual_report() → _dispatch_fix()  → state=fixing
    Backend log ERROR    → on_manual_report(signature=...)        → state=fixing

Closed loop (G2):
    fix believed applied → mark_fix_landed(sig)   → state=verifying (window opens)
    signature recurs     → note_recurrence(sig)   → state=regressed → retry / escalate
    window elapses quiet → sweep()                → state=resolved

States: detected → fixing → verifying → resolved | regressed | awaiting_human
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("qwen-proxy")

# ── Config (env-overridable) ────────────────────────────────────────────────
# Quiet window a heal must stay recurrence-free before it is marked resolved.
HEAL_VERIFY_WINDOW_SEC = int(os.environ.get("HEAL_VERIFY_WINDOW_SEC", "1800"))  # 30 min
# Re-fix attempts before escalating to a human.
HEAL_MAX_ATTEMPTS = int(os.environ.get("HEAL_MAX_ATTEMPTS", "3"))
# How often the background sweeper resolves quiet verifying heals.
HEAL_SWEEP_INTERVAL_SEC = int(os.environ.get("HEAL_SWEEP_INTERVAL_SEC", "300"))  # 5 min


class FailureCategory(Enum):
    """Classified failure types for targeted self-healing (E2)."""
    SYNTAX_ERROR = "syntax_error"
    TEST_FAILURE = "test_failure"
    LINT_ERROR = "lint_error"
    TIMEOUT = "timeout"
    IMPORT_ERROR = "import_error"
    OOM = "out_of_memory"
    NETWORK = "network_error"
    UNKNOWN = "unknown"


class HealState(str, Enum):
    """Lifecycle of a heal (Autonomy Charter G2 closed loop)."""
    DETECTED = "detected"
    FIXING = "fixing"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    REGRESSED = "regressed"
    AWAITING_HUMAN = "awaiting_human"


# States in which a heal is "active" — a new signal for the same signature must
# NOT spawn a duplicate heal (dedup guard).
_ACTIVE_STATES = {HealState.DETECTED, HealState.FIXING, HealState.VERIFYING, HealState.REGRESSED}


def heal_signature(*parts: str) -> str:
    """Stable signature for an error/heal, used to dedup and detect recurrence.

    Mirrors ``agent.log_monitor._sig`` semantics (sha256 of the joined parts,
    truncated) so a backend log error and its heal share one signature.
    """
    raw = ":".join((p or "")[:120] for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class HealingEvent:
    event_id: str
    source: str       # "ci" | "github_issue" | "manual"
    title: str
    description: str
    severity: str     # "critical" | "high" | "medium" | "low"
    created_at: str
    task_id: str | None = None
    resolved: bool = False
    # ── G2 closed-loop fields ──
    signature: str = ""
    state: str = HealState.DETECTED.value
    attempts: int = 0
    landed_at: str | None = None
    resolved_at: str | None = None
    last_recurrence_at: str | None = None
    # monotonic deadline after which a quiet verifying heal resolves (0 = unset)
    _verify_deadline: float = field(default=0.0, repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source": self.source,
            "title": self.title,
            "severity": self.severity,
            "created_at": self.created_at,
            "resolved": self.resolved,
            "task_id": self.task_id,
            "signature": self.signature,
            "state": self.state,
            "attempts": self.attempts,
            "landed_at": self.landed_at,
            "resolved_at": self.resolved_at,
            "last_recurrence_at": self.last_recurrence_at,
        }


class SelfHealingAgent:
    """Translate external failure signals into improvement tasks and verify the
    fix actually held before declaring the heal resolved (Autonomy Charter G2).

    Usage::

        healer = SelfHealingAgent()
        healer.start()                     # launches the verification sweeper
        await healer.on_ci_failure({"test": "test_router", "error": "..."})
        healer.note_recurrence(sig)        # called by LogMonitor on every error
        healer.mark_fix_landed(sig)        # called when the fix is applied/merged
    """

    def __init__(self) -> None:
        self._events: list[HealingEvent] = []
        self._by_signature: dict[str, HealingEvent] = {}
        self._lock = threading.RLock()
        self._sweeper: threading.Thread | None = None
        self._running = False

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Launch the background sweeper that resolves quiet verifying heals."""
        if self._running:
            return
        self._running = True
        self._sweeper = threading.Thread(
            target=self._sweep_loop, name="heal-sweeper", daemon=True
        )
        self._sweeper.start()
        log.info("SelfHealingAgent: verification sweeper started (window=%ds)", HEAL_VERIFY_WINDOW_SEC)

    def stop(self) -> None:
        self._running = False

    # ── Public API ────────────────────────────────────────────────────────────

    async def on_ci_failure(self, failure_info: dict[str, Any]) -> HealingEvent:
        """Called when a CI workflow fails."""
        test_name = failure_info.get("test", "unknown-test")
        error = failure_info.get("error", "")
        workflow = failure_info.get("workflow", "ci")
        test_file = failure_info.get("file", "")
        category = self._classify_failure(error)
        hint = self._failure_category_hint(category.value)

        description_parts = [
            f"Test `{test_name}` failed in workflow `{workflow}`.",
            "",
            f"**Failure category:** {category.value}",
            f"**Suggested fix:** {hint}",
        ]
        if test_file:
            description_parts.append(f"**File:** `{test_file}`")
        if error:
            description_parts.append(f"\n**Error details:**\n```\n{error[:6000]}\n```")

        sig = heal_signature("ci", test_name, workflow)
        existing = self._dedup(sig)
        if existing is not None:
            return existing

        event = self._make_event(
            source="ci",
            title=f"CI failure: {test_name} in {workflow}",
            description="\n".join(description_parts),
            severity="high",
            signature=sig,
        )
        log.info("SelfHealingAgent: CI failure — %s", event.title)
        await self._dispatch_fix(event)
        return event

    async def on_github_issue(self, issue: dict[str, Any]) -> HealingEvent:
        """Called when a GitHub issue with a bug label is opened."""
        title = issue.get("title", "Unknown issue")
        body = issue.get("body", "")
        labels = [la.get("name", "") for la in issue.get("labels", [])]
        severity = "high" if any(l in labels for l in ("critical", "P0")) else "medium"
        sig = heal_signature("github_issue", title)
        existing = self._dedup(sig)
        if existing is not None:
            return existing
        event = self._make_event(
            source="github_issue",
            title=f"Bug: {title}",
            description=f"GitHub issue: {title}\n\n{body[:2000]}",
            severity=severity,
            signature=sig,
        )
        log.info("SelfHealingAgent: GitHub issue — %s", title)
        if any(l in labels for l in ("bug", "fix")):
            await self._dispatch_fix(event)
        return event

    async def on_manual_report(
        self,
        title: str,
        description: str,
        severity: str = "medium",
        signature: str | None = None,
    ) -> HealingEvent:
        """Called from the v4 dashboard 'Report Bug' form and the LogMonitor.

        ``signature`` lets the caller (e.g. LogMonitor) supply a stable error
        signature so recurrences map back to the same heal; otherwise one is
        derived from the title.
        """
        sig = signature or heal_signature("manual", title)
        existing = self._dedup(sig)
        if existing is not None:
            return existing
        event = self._make_event(
            source="manual", title=title, description=description,
            severity=severity, signature=sig,
        )
        log.info("SelfHealingAgent: manual report — %s", title)
        await self._dispatch_fix(event)
        return event

    def note_recurrence(self, signature: str) -> bool:
        """Record that an error with *signature* was just seen again.

        Called by the LogMonitor on **every** matching error (even within its
        task-creation cooldown). If the heal is currently ``verifying``, the
        recurrence means the fix did not hold → mark ``regressed`` and retry (or
        escalate after ``HEAL_MAX_ATTEMPTS``). Returns True if a known heal was
        updated.
        """
        with self._lock:
            event = self._by_signature.get(signature)
            if event is None:
                return False
            event.last_recurrence_at = _now()
            if event.state == HealState.VERIFYING.value:
                log.info(
                    "SelfHealingAgent: signature %s recurred during verification — "
                    "heal %s REGRESSED", signature[:8], event.event_id,
                )
                self._regress(event)
            return True

    def mark_fix_landed(self, signature: str) -> bool:
        """Signal that the fix for *signature* has been applied/merged.

        Transitions the heal ``fixing → verifying`` and opens the quiet window.
        The heal resolves only if no recurrence arrives before the deadline.
        Returns True if a matching active heal was found.
        """
        with self._lock:
            event = self._by_signature.get(signature)
            if event is None or event.state not in (
                HealState.FIXING.value, HealState.REGRESSED.value, HealState.DETECTED.value,
            ):
                return False
            event.state = HealState.VERIFYING.value
            event.landed_at = _now()
            event._verify_deadline = time.monotonic() + HEAL_VERIFY_WINDOW_SEC
            log.info(
                "SelfHealingAgent: heal %s fix landed — verifying for %ds",
                event.event_id, HEAL_VERIFY_WINDOW_SEC,
            )
            return True

    def mark_fix_landed_by_event(self, event_id: str) -> bool:
        """Same as :meth:`mark_fix_landed` but keyed by event/issue id (the id
        the ImprovementLoop tracks)."""
        with self._lock:
            for event in self._events:
                if event.event_id == event_id and event.signature:
                    return self.mark_fix_landed(event.signature)
        return False

    def sweep(self) -> int:
        """Resolve any verifying heal whose quiet window has elapsed.

        Returns the number of heals resolved this sweep. Safe to call from any
        thread / opportunistically; the background sweeper calls it periodically.
        """
        now = time.monotonic()
        resolved = 0
        with self._lock:
            for event in self._events:
                if (
                    event.state == HealState.VERIFYING.value
                    and event._verify_deadline
                    and now >= event._verify_deadline
                ):
                    event.state = HealState.RESOLVED.value
                    event.resolved = True
                    event.resolved_at = _now()
                    resolved += 1
                    log.info(
                        "SelfHealingAgent: heal %s RESOLVED — no recurrence for %ds",
                        event.event_id, HEAL_VERIFY_WINDOW_SEC,
                    )
                    self._mark_improvement_resolved(event)
        return resolved

    def get_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return [e.as_dict() for e in self._events]

    # ── Internal ──────────────────────────────────────────────────────────────

    def _dedup(self, signature: str) -> HealingEvent | None:
        """Return the existing active heal for *signature*, if any (so a repeat
        signal does not spawn a duplicate heal — G2 'exactly one active heal')."""
        with self._lock:
            event = self._by_signature.get(signature)
            if event is not None and event.state in {s.value for s in _ACTIVE_STATES}:
                event.last_recurrence_at = _now()
                log.debug(
                    "SelfHealingAgent: signal for active heal %s (sig=%s) deduped",
                    event.event_id, signature[:8],
                )
                return event
            return None

    def _make_event(
        self, *, source: str, title: str, description: str, severity: str,
        signature: str = "",
    ) -> HealingEvent:
        event = HealingEvent(
            event_id="he_" + secrets.token_hex(6),
            source=source,
            title=title,
            description=description,
            severity=severity,
            created_at=_now(),
            signature=signature,
        )
        with self._lock:
            self._events.append(event)
            if signature:
                self._by_signature[signature] = event
        return event

    @staticmethod
    def _classify_failure(description: str) -> FailureCategory:
        """E2: Classify a failure from its description text.

        Order matters: specific checks (syntax_error, import_error,
        lint_error, timeout, OOM, network) are evaluated before the
        generic test_failure check to avoid mis-classification.
        """
        lowered = description.lower()
        if "syntax error" in lowered or "syntaxerror" in lowered:
            return FailureCategory.SYNTAX_ERROR
        if "modulenotfound" in lowered or "importerror" in lowered or "no module" in lowered:
            return FailureCategory.IMPORT_ERROR
        if "lint" in lowered or "flake8" in lowered or "mypy" in lowered or "type error" in lowered:
            return FailureCategory.LINT_ERROR
        if "timeout" in lowered or "timed out" in lowered:
            return FailureCategory.TIMEOUT
        if "memory" in lowered or "oom" in lowered or "killed" in lowered:
            return FailureCategory.OOM
        if "network" in lowered or "connection" in lowered or "unreachable" in lowered:
            return FailureCategory.NETWORK
        if "test fail" in lowered or "assertion" in lowered or ("test_" in lowered and "fail" in lowered):
            return FailureCategory.TEST_FAILURE
        return FailureCategory.UNKNOWN

    @staticmethod
    def _failure_category_hint(category: str) -> str:
        """E2: Return a corrective hint for each failure category."""
        hints = {
            "syntax_error": "Fix the syntax error. Run `python -m py_compile <file>` to verify.",
            "test_failure": "Fix the failing test. Run `pytest -x <test>` to verify the fix.",
            "lint_error": "Fix the lint/type error. Run the linter to verify.",
            "timeout": "The operation timed out. Add retry logic or increase the timeout.",
            "import_error": "Fix the import. Check that the module exists and the path is correct.",
            "out_of_memory": "Reduce memory usage. Split large operations or free resources.",
            "network_error": "The network request failed. Add retry with backoff or check the endpoint.",
            "unknown": "Investigate the failure and apply the minimum fix.",
        }
        return hints.get(category, hints["unknown"])

    async def _dispatch_fix(self, event: HealingEvent) -> None:
        from agent.improvement_loop import (
            DetectedIssue,
            IssueCategory,
            IssueSeverity,
            get_improvement_loop,
        )

        with self._lock:
            event.state = HealState.FIXING.value
            event.attempts += 1

        loop = get_improvement_loop()
        if not loop:
            log.warning("SelfHealingAgent: ImprovementLoop not available — fix not dispatched")
            return

        sev = IssueSeverity.HIGH if event.severity in ("critical", "high") else IssueSeverity.MEDIUM
        cat = IssueCategory.TEST_FAILURE if event.source == "ci" else IssueCategory.TODO_FIXME
        issue = DetectedIssue(
            issue_id=event.event_id,
            category=cat,
            severity=sev,
            title=event.title,
            description=event.description,
        )
        loop._register_issue(issue)
        loop._schedule_fix(issue)
        log.info(
            "SelfHealingAgent: fix dispatched for %s (attempt %d/%d)",
            event.event_id, event.attempts, HEAL_MAX_ATTEMPTS,
        )

    def _regress(self, event: HealingEvent) -> None:
        """Handle a recurrence during verification: retry or escalate.

        Caller must hold ``self._lock``.
        """
        event.state = HealState.REGRESSED.value
        event._verify_deadline = 0.0
        if event.attempts >= HEAL_MAX_ATTEMPTS:
            self._escalate(event)
            return
        # Re-dispatch the fix (async). NOTE: this runs after the caller releases
        # ``self._lock``. A re-dispatch failure must NOT silently strand the heal in
        # REGRESSED forever (``_verify_deadline`` is 0.0 so the sweeper won't touch
        # it) — on failure we escalate to a human so the heal always reaches a
        # terminal/observable state.
        import asyncio

        async def _redispatch() -> None:
            try:
                await self._dispatch_fix(event)
            except Exception as exc:  # noqa: BLE001 - re-dispatch must never strand a heal
                with self._lock:
                    log.warning(
                        "SelfHealingAgent: re-dispatch failed for heal %s (%s) — escalating",
                        event.event_id, exc,
                    )
                    self._escalate(event)

        def _on_redispatch_done(task: "asyncio.Task[None]") -> None:
            if task.cancelled():
                return
            exc = task.exception()
            if exc is not None:
                log.warning(
                    "SelfHealingAgent: re-dispatch task error for heal %s: %s",
                    event.event_id, exc,
                )

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(_redispatch())
            task.add_done_callback(_on_redispatch_done)
        except RuntimeError:
            threading.Thread(target=asyncio.run, args=(_redispatch(),), daemon=True).start()
        log.info(
            "SelfHealingAgent: heal %s regressed — re-dispatching fix (attempt %d)",
            event.event_id, event.attempts + 1,
        )

    def _escalate(self, event: HealingEvent) -> None:
        """Escalate a heal that exhausted its retries to a human via Telegram.

        Caller must hold ``self._lock``.
        """
        event.state = HealState.AWAITING_HUMAN.value
        log.warning(
            "P1: heal %s could not be auto-fixed after %d attempts — escalating to human: %s",
            event.event_id, event.attempts, event.title,
        )
        try:
            from packages.notifications.service import NotificationDispatcher
            NotificationDispatcher().send_manual_notification(self._format_escalation(event))
        except Exception as exc:  # noqa: BLE001 - escalation notify is best-effort
            log.warning("SelfHealingAgent: escalation notify failed (non-fatal): %s", exc)

    @staticmethod
    def _format_escalation(event: HealingEvent) -> str:
        """Build a *self-contained, actionable* escalation message.

        The previous message was just an opaque id + title, forcing the operator
        to relay it back to an agent to understand. This version carries the
        context inline (what failed + the suggested fix, lifted from the heal's
        description) and clickable links to act on it — derived from the
        ``GITHUB_REPOSITORY`` and ``PUBLIC_URL`` env vars when set, so it works
        without coupling to any specific deploy.
        """
        from urllib.parse import quote

        # Inline context: the heal description already holds the error block and
        # the category-based suggested fix. Strip code fences (Telegram Markdown-v1
        # mangles nested back-ticks) and truncate so the page stays readable.
        ctx = (event.description or "").replace("```", "").strip()
        if len(ctx) > 700:
            ctx = ctx[:700].rstrip() + " …"

        lines = [
            "🔴 *Self-heal escalation* — needs a human",
            "",
            f"*{event.title[:160]}*",
            f"severity: {event.severity} · source: {event.source} · "
            f"attempts: {event.attempts}/{HEAL_MAX_ATTEMPTS}",
        ]
        if ctx:
            lines += ["", ctx]

        # Actionable links (only those we can actually build from the env).
        repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
        public = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
        link_lines: list[str] = []
        if repo:
            q = quote(event.title[:80])
            link_lines.append(f"🔗 Issues/PRs: https://github.com/{repo}/issues?q={q}")
            if event.source == "ci":
                link_lines.append(f"🔗 CI runs: https://github.com/{repo}/actions")
        if public:
            link_lines.append(f"🔗 Dashboard: {public}/admin")
        if link_lines:
            lines += [""] + link_lines

        lines += ["", f"`heal {event.event_id} · sig {event.signature[:8]}`"]
        return "\n".join(lines)

    def _mark_improvement_resolved(self, event: HealingEvent) -> None:
        """Best-effort: reflect a verified heal back into the ImprovementLoop
        state so the dashboard's resolved-count is accurate."""
        try:
            from agent.improvement_loop import get_improvement_loop
            loop = get_improvement_loop()
            if loop:
                loop.mark_resolved(event.event_id)
        except Exception as exc:  # noqa: BLE001 - state sync is best-effort
            log.debug("SelfHealingAgent: improvement-loop resolve sync failed: %s", exc)

    def _sweep_loop(self) -> None:
        while self._running:
            try:
                self.sweep()
            except Exception as exc:  # noqa: BLE001 - sweeper must never die
                log.warning("SelfHealingAgent: sweep error: %s", exc)
            time.sleep(HEAL_SWEEP_INTERVAL_SEC)


# ── Singleton ─────────────────────────────────────────────────────────────────

_healer_instance: SelfHealingAgent | None = None


def set_self_healing_agent(instance: SelfHealingAgent) -> None:
    global _healer_instance
    _healer_instance = instance


def get_self_healing_agent() -> SelfHealingAgent | None:
    return _healer_instance


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
