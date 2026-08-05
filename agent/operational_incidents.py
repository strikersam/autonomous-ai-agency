"""agent/operational_incidents.py — recurring operational failures, auto-diagnosed.

Closes the last hop of the self-heal chain: the one an operator was walking by
hand.

``agent/log_monitor.py`` turns application ERROR logs into fix tasks, but it
deliberately drops everything matching ``_OPERATIONAL_PATTERNS`` — timeouts,
"blocked after N dispatch attempts", "all runtimes failed", rate limits. That
filter is correct as far as it goes: an LLM editing source files cannot fix a
saturated free tier, and filing one fix task per timeout is the documented
"timeout → fix task → slow run → timeout" amplification loop.

But dropping them entirely left no path at all. A failure mode that recurred
every few minutes for hours produced exactly zero signal inside the platform —
the only way anyone learned about it was a human reading the dashboard and
pasting logs into a chat. That is the gap this module fills.

The distinction it draws is *one occurrence* versus *a pattern*:

  * a single timeout is noise — a slow provider, a cold model, one bad minute,
  * the same failure ``INCIDENT_THRESHOLD`` times inside ``WINDOW_SECONDS`` is
    an incident, and an incident deserves a diagnosis.

On crossing that line the tracker gathers the evidence a human would have
gathered — the Render logs around the event, including the ``phase_start`` /
``phase_end`` markers that name which agent phase stalled — and files **one**
issue through ``ImprovementLoop.register_external_issue``, the same intake
``services/render_ops.py`` already uses. No second pipeline, no fix task per
occurrence, and the anti-storm properties are kept as hard bounds: a recurrence
threshold, a per-signature cooldown, and an hourly cap.

Signature normalisation is what makes the threshold reachable at all. The
log monitor keys on ``message[:120]`` verbatim, so ``Task task_c7022c0b… timed
out`` and ``Task task_e2d70c78… timed out`` hash differently and each looks
like a first occurrence forever. Here the volatile parts — task ids, job ids,
hex digests, bare numbers — are collapsed first, so repetitions of one failure
mode actually accumulate.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

log = logging.getLogger("qwen-agent")

# Occurrences of one normalised signature inside WINDOW_SECONDS before the
# pattern is treated as an incident. Below this it is indistinguishable from a
# transient blip, and filing would recreate the storm the log-monitor filter
# exists to prevent.
INCIDENT_THRESHOLD: int = int(os.environ.get("OPS_INCIDENT_THRESHOLD", "4"))

# Rolling window the threshold is counted over.
WINDOW_SECONDS: int = int(os.environ.get("OPS_INCIDENT_WINDOW_SECONDS", "1800"))  # 30m

# Don't re-file the same signature within this window, however often it recurs.
COOLDOWN_SECONDS: int = int(os.environ.get("OPS_INCIDENT_COOLDOWN_SECONDS", "21600"))  # 6h

# Hard ceiling on incidents filed per rolling hour, across all signatures.
MAX_INCIDENTS_PER_HOUR: int = int(os.environ.get("OPS_INCIDENT_MAX_PER_HOUR", "3"))

# How far back to pull Render logs when building the evidence bundle.
EVIDENCE_LOOKBACK_MINUTES: int = int(os.environ.get("OPS_INCIDENT_LOOKBACK_MINUTES", "20"))

# Max Render log lines fetched per incident. Bounds both API cost and the size
# of the issue body.
EVIDENCE_LOG_LIMIT: int = 200

# Log lines quoted into the filed issue. The fetch is wider than the quote so
# the phase-marker analysis below sees more than the excerpt does.
EVIDENCE_QUOTE_LINES: int = 25

# Volatile substrings replaced before hashing, so repetitions of one failure
# mode collapse onto a single signature instead of scattering across ids.
_NORMALISERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\btask_[0-9a-f]{6,}\b", re.I), "task_<id>"),
    (re.compile(r"\bjob_[0-9a-f]{6,}\b", re.I), "job_<id>"),
    (re.compile(r"\bdir_[0-9a-f]{6,}\b", re.I), "dir_<id>"),
    (re.compile(r"\bcycle_[0-9a-f]{6,}\b", re.I), "cycle_<id>"),
    (
        re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I
        ),
        "<uuid>",
    ),
    (re.compile(r"\b[0-9a-f]{12,}\b", re.I), "<hex>"),
    (re.compile(r"\d+"), "<n>"),
)


def normalise(message: str) -> str:
    """Collapse the volatile parts of *message* so recurrences group together.

    ``Task task_c7022c0bd20258b3 Execution timed out after 600s`` and
    ``Task task_e2d70c78bf8c35b2 Execution timed out after 600s`` both become
    ``Task task_<id> Execution timed out after <n>s`` — one signature, two
    occurrences, which is the whole point.
    """
    text = (message or "").strip()
    for pattern, replacement in _NORMALISERS:
        text = pattern.sub(replacement, text)
    return text[:200]


def signature_for(logger_name: str, message: str) -> str:
    """Stable dedup key over the *normalised* message."""
    raw = f"{logger_name}:{normalise(message)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class OperationalIncident:
    """One failure mode that recurred often enough to warrant diagnosis."""

    signature: str
    logger_name: str
    normalised: str
    sample: str
    count: int
    window_seconds: int
    first_seen: str
    last_seen: str
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def title(self) -> str:
        return (
            f"Recurring operational failure ({self.count}x in "
            f"{self.window_seconds // 60}m): {self.normalised[:90]}"
        )


class OperationalIncidentTracker:
    """Count operational failures; diagnose and file the ones that persist.

    Every method is safe to call from a logging handler on any thread: nothing
    here raises, and nothing blocks on I/O. The evidence gathering that does
    touch the network is handed to the event loop as a background task.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._occurrences: dict[str, list[float]] = {}
        self._samples: dict[str, tuple[str, str]] = {}  # sig → (logger, sample)
        self._first_seen: dict[str, float] = {}
        self._filed: dict[str, float] = {}  # sig → last filed (monotonic)
        self._filed_times: list[float] = []  # rolling hour of filings
        self._incidents_filed = 0
        self._cap_warned = False

    # ── public API ────────────────────────────────────────────────────────────

    def record(self, logger_name: str, message: str) -> bool:
        """Note one operational failure. Returns True when it filed an incident.

        Called synchronously from the log-monitor's operational branch, which
        runs inside a ``logging.Handler`` — so this must never raise and never
        block.
        """
        try:
            return self._record(logger_name, message)
        except Exception as exc:  # noqa: BLE001 - never break the logging path
            log.debug("OperationalIncidents: record failed: %s", exc)
            return False

    def get_stats(self) -> dict[str, Any]:
        """Live counters, for the diagnostics endpoint and tests."""
        with self._lock:
            return {
                "tracked_signatures": len(self._occurrences),
                "incidents_filed": self._incidents_filed,
                "threshold": INCIDENT_THRESHOLD,
                "window_seconds": WINDOW_SECONDS,
                "active_cooldowns": len(self._filed),
            }

    def reset(self) -> None:
        """Drop all state. Used by tests."""
        with self._lock:
            self._occurrences.clear()
            self._samples.clear()
            self._first_seen.clear()
            self._filed.clear()
            self._filed_times.clear()
            self._incidents_filed = 0
            self._cap_warned = False

    # ── internals ─────────────────────────────────────────────────────────────

    def _record(self, logger_name: str, message: str) -> bool:
        sig = signature_for(logger_name, message)
        now = time.monotonic()

        with self._lock:
            hits = [t for t in self._occurrences.get(sig, []) if t > now - WINDOW_SECONDS]
            hits.append(now)
            self._occurrences[sig] = hits
            self._samples[sig] = (logger_name, (message or "")[:1000])
            self._first_seen.setdefault(sig, now)

            if len(hits) < INCIDENT_THRESHOLD:
                return False
            if not self._may_file(sig, now):
                return False

            incident = OperationalIncident(
                signature=sig,
                logger_name=logger_name,
                normalised=normalise(message),
                sample=(message or "")[:1000],
                count=len(hits),
                window_seconds=WINDOW_SECONDS,
                first_seen=_iso_from_monotonic(self._first_seen[sig], now),
                last_seen=_utcnow_iso(),
            )

        log.warning(
            "OperationalIncidents: %r recurred %dx in %dm — diagnosing and filing",
            incident.normalised[:80], incident.count, WINDOW_SECONDS // 60,
        )
        _schedule(_diagnose_and_file(incident))
        return True

    def _may_file(self, sig: str, now: float) -> bool:
        """Cooldown + hourly cap. Caller must hold the lock."""
        last = self._filed.get(sig)
        if last is not None and now - last < COOLDOWN_SECONDS:
            return False

        cutoff = now - 3600.0
        self._filed_times = [t for t in self._filed_times if t >= cutoff]
        if MAX_INCIDENTS_PER_HOUR > 0 and len(self._filed_times) >= MAX_INCIDENTS_PER_HOUR:
            if not self._cap_warned:
                log.warning(
                    "OperationalIncidents: hourly cap (%d) reached — "
                    "further incidents suppressed this hour.",
                    MAX_INCIDENTS_PER_HOUR,
                )
                self._cap_warned = True
            return False

        self._filed_times.append(now)
        self._filed[sig] = now
        self._incidents_filed += 1
        self._cap_warned = False
        return True


# ── evidence gathering ────────────────────────────────────────────────────────


async def gather_render_evidence() -> dict[str, Any]:
    """Pull recent Render logs and summarise them for the issue body.

    This is the manual step being automated: instead of an operator opening the
    Render dashboard and copying a log window, the incident carries its own.

    Degrades rather than fails. Without ``RENDER_API_KEY`` the Render MCP client
    is unavailable, and the incident is still filed — with a note saying the
    platform view was unreachable, which is itself useful.
    """
    try:
        from packages.config import settings
        from packages.integrations.render_mcp import get_render_mcp
    except Exception as exc:  # noqa: BLE001 - optional dependency
        return {"available": False, "reason": f"render integration unavailable: {exc}"}

    if not settings.is_render_mcp_configured:
        return {
            "available": False,
            "reason": "RENDER_API_KEY / RENDER_MCP_URL not configured",
        }

    now = datetime.now(timezone.utc)
    try:
        client = get_render_mcp()
        # Honours the RENDER_SERVICE_IDS allow-list, falling back to workspace
        # discovery — the same resolution the Render ops loop uses.
        service_ids = await client.resolve_service_ids()
        if not service_ids:
            return {"available": False, "reason": "no Render services resolved"}
        logs = await client.list_logs(
            service_ids,
            start_time=(now - timedelta(minutes=EVIDENCE_LOOKBACK_MINUTES)).isoformat(),
            end_time=now.isoformat(),
            limit=EVIDENCE_LOG_LIMIT,
        )
    except Exception as exc:  # noqa: BLE001 - diagnosis must not raise
        return {"available": False, "reason": f"log fetch failed: {exc}"}

    messages = [str(entry.get("message", "")) for entry in (logs or [])]
    return {
        "available": True,
        "line_count": len(messages),
        "window_minutes": EVIDENCE_LOOKBACK_MINUTES,
        "phases": summarise_phases(messages),
        "excerpt": "\n".join(m[:220] for m in messages[-EVIDENCE_QUOTE_LINES:]),
    }


def summarise_phases(messages: list[str]) -> dict[str, Any]:
    """Find agent phases that started but never finished.

    ``agent/loop.py::_timed_phase`` brackets every LLM call and tool dispatch
    with ``phase_start <phase> …`` / ``phase_end <phase> … elapsed_s=…``. A
    phase with more starts than ends in the same window is one that never
    returned — which names the stuck call outright instead of leaving only the
    outer "Execution timed out after 600s".
    """
    starts: dict[str, int] = {}
    ends: dict[str, int] = {}
    last_start_at: dict[str, int] = {}
    for position, message in enumerate(messages):
        for marker, bucket in (("phase_start ", starts), ("phase_end ", ends)):
            idx = message.find(marker)
            if idx == -1:
                continue
            rest = message[idx + len(marker):].strip()
            phase = rest.split(" ", 1)[0] if rest else "?"
            bucket[phase] = bucket.get(phase, 0) + 1
            if bucket is starts:
                last_start_at[phase] = position

    unfinished = {
        phase: count - ends.get(phase, 0)
        for phase, count in starts.items()
        if count - ends.get(phase, 0) > 0
    }
    # The phases nest: `execute_step` wraps `tool_dispatch`, so an inner call
    # that never returns leaves *both* unfinished. The innermost one is the
    # actual stall, and it is the one whose `phase_start` came last — ranking
    # by count instead would tie and pick the outer wrapper, naming the
    # symptom rather than the cause.
    stuck = max(unfinished, key=lambda p: last_start_at.get(p, -1)) if unfinished else None
    return {
        "started": starts,
        "finished": ends,
        "unfinished": unfinished,
        "likely_stuck_phase": stuck,
    }


async def _diagnose_and_file(incident: OperationalIncident) -> None:
    """Attach evidence to *incident*, then hand it to the existing intake."""
    try:
        incident.evidence = await gather_render_evidence()
    except Exception as exc:  # noqa: BLE001 - file it even without evidence
        incident.evidence = {"available": False, "reason": str(exc)}
    _file_incident(incident)


def _file_incident(incident: OperationalIncident) -> bool:
    """Register the incident through ``ImprovementLoop.register_external_issue``.

    Deliberately the same intake ``services/render_ops.py`` uses: one issue
    pipeline, one dedup path, one set of persistence rules.
    """
    try:
        from agent.improvement_loop import (
            DetectedIssue, IssueCategory, IssueSeverity, get_improvement_loop,
        )
    except Exception as exc:  # noqa: BLE001 - intake is optional
        log.debug("OperationalIncidents: ImprovementLoop unavailable (%s)", exc)
        return False

    loop = get_improvement_loop()
    if loop is None:
        log.info(
            "OperationalIncidents: %s (not filed, ImprovementLoop idle)", incident.title
        )
        return False

    issue = DetectedIssue(
        issue_id=f"ops-{incident.signature}",
        category=IssueCategory.PERFORMANCE,
        severity=IssueSeverity.HIGH,
        title=incident.title,
        description=_format_incident(incident),
    )
    try:
        return bool(loop.register_external_issue(issue))
    except Exception as exc:  # noqa: BLE001 - never break the tracker
        log.warning("OperationalIncidents: could not register issue: %s", exc)
        return False


def _format_incident(incident: OperationalIncident) -> str:
    """Build the issue body: what recurred, plus the gathered evidence."""
    evidence = incident.evidence or {}
    parts = [
        f"An operational failure recurred **{incident.count} times** in the last "
        f"{incident.window_seconds // 60} minutes.",
        "",
        f"**Logger:** `{incident.logger_name}`",
        f"**Normalised signature:** `{incident.normalised}`",
        f"**First seen:** {incident.first_seen}  ",
        f"**Last seen:** {incident.last_seen}",
        "",
        "**Sample message:**",
        f"```\n{incident.sample[:800]}\n```",
    ]

    phases = evidence.get("phases") or {}
    stuck = phases.get("likely_stuck_phase")
    if stuck:
        unfinished = phases.get("unfinished", {})
        parts += [
            "",
            f"**Likely stuck phase: `{stuck}`** — it logged "
            f"{unfinished.get(stuck)} more `phase_start` than `phase_end` in the "
            "window, meaning that call never returned "
            "(`agent/loop.py::_timed_phase`).",
            f"Unfinished phases: `{unfinished}`",
        ]
    elif phases:
        parts += [
            "",
            "No unbalanced `phase_start`/`phase_end` pair in the window — the "
            "stall is likely outside the agent loop's instrumented phases.",
        ]

    if evidence.get("available"):
        parts += [
            "",
            f"**Render logs** (last {evidence.get('window_minutes')}m, "
            f"{evidence.get('line_count')} lines):",
            f"```\n{evidence.get('excerpt', '')[:2500]}\n```",
        ]
    else:
        parts += [
            "",
            f"_Render platform logs unavailable: {evidence.get('reason', 'unknown')}._",
        ]

    parts += [
        "",
        "**Source:** operational-incident tracker (`agent/operational_incidents.py`). "
        "This is an infrastructure/behaviour failure, not necessarily a code defect — "
        "diagnose before editing, and prefer a configuration or bound change over a "
        "source edit when the cause is capacity or latency.",
    ]
    return "\n".join(parts)


# ── helpers ───────────────────────────────────────────────────────────────────


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_from_monotonic(then: float, now: float) -> str:
    """Best-effort wall-clock for a monotonic timestamp taken earlier."""
    delta = max(0.0, now - then)
    return (datetime.now(timezone.utc) - timedelta(seconds=delta)).isoformat()


def _schedule(coro: Any) -> None:
    """Run *coro* without blocking the caller, from any thread.

    The caller is a logging handler, which may be on the event loop thread, a
    worker thread, or a process with no loop at all.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        threading.Thread(target=asyncio.run, args=(coro,), daemon=True).start()
        return
    loop.create_task(coro)


# ── singleton ─────────────────────────────────────────────────────────────────

_tracker: OperationalIncidentTracker | None = None


def get_operational_incident_tracker() -> OperationalIncidentTracker:
    """Return the shared tracker, creating it on first use."""
    global _tracker
    if _tracker is None:
        _tracker = OperationalIncidentTracker()
    return _tracker


def reset_operational_incident_tracker() -> None:
    """Drop the cached tracker. Used by tests."""
    global _tracker
    _tracker = None


def record_operational_error(logger_name: str, message: str) -> bool:
    """Module-level entry point used by ``agent/log_monitor.py``."""
    return get_operational_incident_tracker().record(logger_name, message)
